/* 中国行政区划地图视图（2026-11-11）。
   三级下钻: 全国省界 → 点击省看市级图 → 点击市看县级图 → 点击县出详情；
   无县级边界文件的区划（直辖市区/省直管县）点击直接出详情。
   热力色=区划官网覆盖率；点击区划 → onSelect(name) 回调（页面层填详情）。
   数据: geo/china.js（省界）+ geo/geo_{adcode}.js（市/县界, 按需加载）+
   geo/geo_index.js（市级下钻清单 __GEO_CITY_FILES__）。 */
window.MapViz=(function(){
  const NS="http://www.w3.org/2000/svg";
  let el=null,svg=null,rootG=null,labelG=null;
  let tree=null,onSelect=null,onLevelChange=null,onTypeChange=null,onRegion=null;
  let stats=new Map();          // name → {u:有官网, total}
  let features=[],level="china",curProv=null,curProvCode="",curCity=null,curCityCode="";
  const CITY_FILES=new Set(window.__GEO_CITY_FILES__||[]);   // 有县级边界文件的市级 adcode（无则点击=直接看详情）
  let curType="gov";   // 当前机构类型（地图按该类型 URL 覆盖着色）
  let mode="block";     // block=块视图(区划×机关类型) | tiao=条视图(垂直系统×区划)
  const TYPES=[{k:"gov",n:"人民政府"},{k:"rd",n:"人大"},{k:"zx",n:"政协"},
    {k:"fy",n:"法院"},{k:"jcy",n:"检察院"},{k:"jw",n:"监委"}];
  let scale=1,ox=0,oy=0,proj=null,selName=null;
  const MINLON=73,MAXLON=136,MINLAT=3,MAXLAT=54;
  let range={minLon:MINLON,maxLon:MAXLON,minLat:MINLAT,maxLat:MAXLAT};   // 当前投影范围（下钻后切省界）

  // 统计各区划覆盖率（块树 DFS, 深聚合: 区划辖域内该类型机构的建站率,
  // 省级图=全省该类型机构 市级图=全市 县级图=全县——各级都有差异才有彩虹）。
  // 注意: 省级节点是 t="group" 挂 u（省门户）, 市级/县级才是 t="gov"——
  // 区划识别须兼容 group 形态（有门户且含 t=gov 子区划）。
  function isRegion(nd){
    return nd.t==="gov"||nd.t==="govhome"||
      (nd.t==="group"&&nd.u&&(nd.ks||[]).some(k=>k.t==="gov"));
  }
  function calcStats(t){
    stats.clear();
    provU.clear();
    (function w(n){
      if(isRegion(n)){
        // 区划节点: 递归整棵子树, 按类型统计叶子机构
        const m={};
        function cnt(nd){
          const ty=nd.t;
          const isLeaf=!(nd.ks&&nd.ks.length);
          if(isLeaf){
            if(ty&&ty!=="group"&&ty!=="binglie"&&ty!=="block"&&ty!=="root"){
              const s=m[ty]||{u:0,total:0};
              s.total++;if(nd.u)s.u++;
              m[ty]=s;
            }
            return;
          }
          // 区划门户节点自身计入 gov 类型
          if(ty==="gov"||ty==="govhome"||(ty==="group"&&nd.u&&(nd.ks||[]).some(k=>k.t==="gov"))){
            const s=m.gov||{u:0,total:0};
            s.total++;if(nd.u)s.u++;
            m.gov=s;
          }
          for(const k of nd.ks)cnt(k);
        }
        cnt(n);
        // 2026-11-13 用户指令「省级 url 缺失也应该是灰色的」:
        // 省级机构的自身 URL 单独记录（省人大/省政协/省监委/省法院/省检察院
        // 在「并列机关」组下, t=rd/zx/jw/fy/jcy）——全国图该省判灰须看
        // 省级机构自身 u, 而不是只看辖域市县级深聚合。
        if(n.l==="省"){
          const pu={};
          for(const k of n.ks||[]){
            if(k.t==="binglie"){
              for(const o of k.ks||[]){
                if(o.t&&!pu[o.t])pu[o.t]=o.u||"";
              }
            }
          }
          pu.gov=n.u||"";
          provU.set(n.n,pu);
        }
        // 综合: 全类型合计
        let du=0,dt=0;
        for(const k in m){du+=m[k].u;dt+=m[k].total;}
        m.all={u:du,total:dt};
        stats.set(n.n,m);
      }
      for(const k of n.ks||[])w(k);
    })(t);
    rebuildBaseIndex();
  }
  let adcByName=null;   // csv 桥: 统计局区划名 → adcode
  // 简称/全名归一（匹配层）: 剥行政区后缀 + 民族修饰 → 基底名
  // （木里藏族自治县→木里, 西昌市→西昌, 石河子市→石河子）
  const ETH_END=/(哈萨克族?|维吾尔族?|柯尔克孜族?|朝鲜族?|蒙古族?|藏族?|回族?|壮族?|苗族?|黎族?|侗族?|满族?|白族?|傣族?|彝族?|哈尼族?|拉祜族?|傈僳族?|佤族?|水族?|羌族?|布依族?|仡佬族?|仫佬族?|毛南族?|瑶族?|畲族?|土家族?|锡伯族?|达斡尔族?|鄂温克族?|鄂伦春族?|赫哲族?|俄罗斯族?|塔塔尔族?|乌孜别克族?|塔吉克族?|撒拉族?|保安族?|裕固族?|东乡族?|纳西族?|景颇族?|阿昌族?|普米族?|怒族?|德昂族?|独龙族?|基诺族?|门巴族?|珞巴族?|京族?|自治)$/;
  function baseName(nm){
    let t=(nm||"").replace(/[（(][^（）)]*[）)]$/,"")   // 尾注剥离: 中西区（区议会分区）→中西区
                   .replace(/(自治州|自治县|自治旗|地区|盟|市|县|区|旗)$/,"");
    for(let i=0;i<8;i++){
      const t2=t.replace(ETH_END,"");
      if(t2===t||t2.length<2)break;   // 单字保护: 北京→京族?剥成「北」等撞车源
      t=t2;
    }
    return t;
  }
  let baseIndex=null;   // 基底名 → stats 规范名（geo 特征名与树节点名 简称/全名 互通）
  function rebuildBaseIndex(){
    baseIndex=new Map();
    for(const nm of stats.keys()){
      const b=baseName(nm);
      if(b&&!baseIndex.has(b))baseIndex.set(b,nm);
    }
  }
  function covOf(name){
    let m=stats.get(name);
    if(!m&&baseIndex){
      const c=baseIndex.get(baseName(name));
      if(c)m=stats.get(c);
    }
    if((!m||!m.gov)&&adcByName){
      const a=adcByName.get(name);
      if(a){
        for(const [n,aa] of adcByName){
          if(aa===a&&stats.has(n)){m=stats.get(n);break}
        }
      }
    }
    if(!m)return -1;
    if(mode==="tiao"){           // 条模式: 扁平 {u,total}
      if(!m.total)return -2;
      return m.u/m.total;
    }
    if(curType==="all"){         // 综合: 全类型深聚合
      if(!m.all||!m.all.total)return -2;
      return m.all.u/m.all.total;
    }
    const s=m[curType];
    if(!s||!s.total)return -2;   // 该类型机构不存在
    return s.u/s.total;
  }
  let rankCache=new Map(),covCache=new Map(),fillCache=new Map();   // fillCache=着色用（降级时=综合值）, covCache=浮层/详情用（真实类型值）
  let provU=new Map();   // 省级机构自身 u: 省名 → {gov,rd,zx,jw,fy,jcy}（全国图判灰用）
  let degraded=false;   // 当前类型本级无差异 → 已降级为综合覆盖着色
  let shiftDefs=new Map();   // 县级图层: 县名 → 同档色相微调渐变 id（县与县颜色区分）
  const NCLS=7;
  // 矿物莫兰迪 7 档（低→高, 白天=明亮鲜润, 夜晚=温润低亮）; 深浅两套
  const PAL_LIGHT=["#4f9ee0","#3eb8a8","#7cc75f","#d3c549","#f0a33c","#ef7d4e","#e25550"];
  const PAL_DARK =["#6b95c9","#6aa88e","#93b57e","#c4b56a","#d29c54","#c97f63","#b45f52"];
  const GRAY_LIGHT={nodata:"#eae5d9",noorg:"#f2f0e9",zero:"#ddd7c8"};
  const GRAY_DARK ={nodata:"#27241d",noorg:"#211f1a",zero:"#3a342a"};
  const OCEAN_LIGHT=["#fbfaf6","#ece8dc"];
  const OCEAN_DARK=["#1e1c15","#121009"];
  let theme="light";
  // 2026-11-16 配色方案（用户指令「浅一点 + 可自选」）: 图例区圆点点选,
  // localStorage 持久化; 每方案=色相范围(起点+跨度)×饱和×亮度, 黄金角
  // 在该范围内展开——「每区划独立色」机制不变, 只换色系。夜晚主题亮度
  // 自动 -11 保持温润低亮。
  let schemeId="pastel";
  try{schemeId=localStorage.getItem("govMapScheme")||"pastel"}catch(e){}
  if(!({pastel:1,rainbow:1,teal:1,warm:1,morandi:1})[schemeId])schemeId="pastel";
  const SCHEMES={
    pastel:{name:"粉彩",start:0,span:360,sat:38,lum:72},
    rainbow:{name:"彩虹",start:0,span:360,sat:56,lum:64},
    teal:{name:"青绿",start:150,span:180,sat:50,lum:62},
    warm:{name:"暖阳",start:340,span:150,sat:56,lum:62},
    morandi:{name:"莫兰迪",start:0,span:360,sat:22,lum:61},
  };
  function schemeVal(){
    const s=SCHEMES[schemeId]||SCHEMES.pastel;
    return theme==="dark"
      ?{start:s.start,span:s.span,sat:Math.min(100,s.sat+8),lum:s.lum-11}
      :{start:s.start,span:s.span,sat:s.sat,lum:s.lum};
  }
  function shade(hex,f){
    const n=parseInt(hex.slice(1),16);
    let r=n>>16,g=(n>>8)&255,b=n&255;
    if(f>=0){r+=(255-r)*f;g+=(255-g)*f;b+=(255-b)*f;}
    else{r*=(1+f);g*=(1+f);b*=(1+f);}
    return `rgb(${r|0},${g|0},${b|0})`;
  }
  function hexToHsl(hex){
    const n=parseInt(hex.slice(1),16);
    let r=((n>>16)&255)/255,g=((n>>8)&255)/255,b=(n&255)/255;
    const mx=Math.max(r,g,b),mn=Math.min(r,g,b),l=(mx+mn)/2;
    let h=0,s=0;
    if(mx!==mn){
      const d=mx-mn;
      s=l>0.5?d/(2-mx-mn):d/(mx+mn);
      if(mx===r)h=(g-b)/d+(g<b?6:0);
      else if(mx===g)h=(b-r)/d+2;
      else h=(r-g)/d+4;
      h/=6;
    }
    return [h*360,s*100,l*100];
  }
  function hslToHex(h,s,l){
    h=((h%360)+360)%360/360;s/=100;l/=100;
    const f=(n)=>{const k=(n+h*12)%12,a=l-s*Math.min(l,1-l)*Math.max(-1,Math.min(k-3,9-k,1));
      return Math.round(a*255);};
    return "#"+[f(0),f(8),f(4)].map(x=>x.toString(16).padStart(2,"0")).join("");
  }
  function shiftHue(hex,deg){
    const [h,s,l]=hexToHsl(hex);
    return hslToHex(h+deg,s,l);
  }
  function hsh(s){
    let h=0;
    for(let i=0;i<s.length;i++){h=(h*31+s.charCodeAt(i))>>>0;}
    return h;
  }
  function readTheme(){
    // gov-tree 用 --bg, 模板用 --ground; 3 位缩写须展开（parseInt("fff")=4095 会算成暗色）
    const cs=getComputedStyle(el);
    let bg=cs.getPropertyValue("--bg").trim()||cs.getPropertyValue("--ground").trim()||"#ffffff";
    if(/^#[0-9a-fA-F]{3}$/.test(bg))bg="#"+bg[1]+bg[1]+bg[2]+bg[2]+bg[3]+bg[3];
    const n=parseInt(bg.replace("#",""),16);
    if(isNaN(n))return "light";
    const lum=(0.299*((n>>16)&255)+0.587*((n>>8)&255)+0.114*(n&255))/255;
    return lum>0.5?"light":"dark";
  }
  const PAL=()=>theme==="dark"?PAL_DARK:PAL_LIGHT;
  const GRAY=()=>theme==="dark"?GRAY_DARK:GRAY_LIGHT;
  const OCEAN=()=>theme==="dark"?OCEAN_DARK:OCEAN_LIGHT;
  function colorOf(name){
    const c=fillCache.get(name);
    if(c===undefined||c===-1)return "url(#mzg0)";   // 非行政区划（无数据）
    if(c===-2)return "url(#mzg1)";                  // 该类型机构不存在
    if(c===0)return "url(#mzg2)";                   // 机构全无官网
    if(shiftDefs.has(name))return "url(#"+shiftDefs.get(name)+")";
    const k=rankCache.has(name)?rankCache.get(name):3;
    return "url(#mzcls"+k+")";
  }
  function project(f){
    // 适配容器: 保持纵横比居中
    const W=el.clientWidth||900,H=el.clientHeight||600;
    const {minLon,maxLon,minLat,maxLat}=range;
    const kx=W/(maxLon-minLon),ky=H/(maxLat-minLat);
    const k=Math.min(kx,ky)*0.94;
    const ox0=(W-(maxLon-minLon)*k)/2,oy0=(H-(maxLat-minLat)*k)/2;
    return ([lon,lat])=>[
      ox0+(lon-minLon)*k,
      oy0+(maxLat-lat)*k
    ];
  }
  function pathOf(geom,pr){
    // Polygon: [ring[pt]]; MultiPolygon: [poly[ring[pt]]]
    let d="";
    function addRing(ring){
      let first=true;
      for(const pt of ring){
        const [x,y]=pr(pt);
        d+=(first?"M":"L")+x.toFixed(1)+","+y.toFixed(1);
        first=false;
      }
      d+="Z";
    }
    if(geom.type==="Polygon"){
      for(const ring of geom.coordinates) addRing(ring);
    }else if(geom.type==="MultiPolygon"){
      for(const poly of geom.coordinates)
        for(const ring of poly) addRing(ring);
    }
    return d;
  }
  function render(){
    if(!el||!features.length)return;
    theme=readTheme();
    svg.innerHTML="";
    const W=el.clientWidth||900,H=el.clientHeight||600;
    // ---- defs: 每档上亮下深的纵向渐变 + 海洋径向渐变 ----
    const defs=document.createElementNS(NS,"defs");
    svg.appendChild(defs);
    function grad(id,c0,c1,cx,cy,r){
      const g=document.createElementNS(NS,r?"radialGradient":"linearGradient");
      g.setAttribute("id",id);
      if(r){g.setAttribute("cx",cx);g.setAttribute("cy",cy);g.setAttribute("r",r);}
      else{g.setAttribute("x1","0");g.setAttribute("y1","0");g.setAttribute("x2","0");g.setAttribute("y2","1");}
      for(const [o,c] of [["0",c0],["1",c1]]){
        const s=document.createElementNS(NS,"stop");
        s.setAttribute("offset",o);s.setAttribute("stop-color",c);
        g.appendChild(s);
      }
      defs.appendChild(g);
      return "url(#"+id+")";
    }
    const P=PAL(),G=GRAY(),O=OCEAN();
    for(let k=0;k<NCLS;k++)grad("mzcls"+k,shade(P[k],0.14),shade(P[k],-0.16));
    grad("mzg0",shade(G.nodata,0.06),shade(G.nodata,-0.08));
    grad("mzg1",shade(G.noorg,0.05),shade(G.noorg,-0.06));
    grad("mzg2",shade(G.zero,0.05),shade(G.zero,-0.08));
    // 海洋: 中心亮边缘深的暗角
    const oce=document.createElementNS(NS,"rect");
    oce.setAttribute("x","0");oce.setAttribute("y","0");
    oce.setAttribute("width",W);oce.setAttribute("height",H);
    oce.setAttribute("fill",grad("mzocean",O[0],O[1],"50%","40%","78%"));
    svg.appendChild(oce);
    // ---- 经纬网（微弱格线, 仅作氛围）----
    pr=project(features[0]);
    const gr=document.createElementNS(NS,"g");
    gr.setAttribute("stroke",theme==="dark"?"rgba(216,209,190,0.07)":"rgba(82,72,52,0.07)");
    gr.setAttribute("stroke-width","0.6");
    const parts=[];
    for(let lon=Math.ceil(range.minLon/10)*10;lon<=range.maxLon;lon+=10){
      const a=pr([lon,range.minLat]),b=pr([lon,range.maxLat]);
      parts.push(`M${a[0].toFixed(1)},${a[1].toFixed(1)}L${b[0].toFixed(1)},${b[1].toFixed(1)}`);
    }
    for(let lat=Math.ceil(range.minLat/10)*10;lat<=range.maxLat;lat+=10){
      const a=pr([range.minLon,lat]),b=pr([range.maxLon,lat]);
      parts.push(`M${a[0].toFixed(1)},${a[1].toFixed(1)}L${b[0].toFixed(1)},${b[1].toFixed(1)}`);
    }
    const gpath=document.createElementNS(NS,"path");
    gpath.setAttribute("d",parts.join(""));
    gr.appendChild(gpath);
    svg.appendChild(gr);
    rootG=document.createElementNS(NS,"g");
    svg.appendChild(rootG);
    labelG=document.createElementNS(NS,"g");   // 标注顶层组（置于全部多边形之上, 文字不被遮挡）
    // ---- 覆盖率缓存 + 7 级分位数分级（非零值按排名分档; 灰态不参与）----
    covCache=new Map();
    for(const f of features){
      const c=covOf(f.properties&&f.properties.name);
      covCache.set(f.properties&&f.properties.name,c);
    }
    const computeRanks=(cache)=>{
      rankCache=new Map();
      let first=null,mono=true;
      // 2026-11-12 市级绝对覆盖率分档（用户指正「都应该是五颜六色的, url缺失
      // 的是灰色的, 不能只有一个颜色」）: 视图内等分位数会让同值城市全落同档,
      // 且跨市不可比; 市级改为绝对档 7 级（0=灰, (0,1/7]=1, …, (6/7,1]=6）。
      // 全国/省级保留等分位数（大聚合有真实离散度, 全国图 7 色用满）。
      const abs=level==="city";
      for(const f of features){
        const nm=f.properties&&f.properties.name;
        const c=cache.get(nm);
        if(c===undefined||c===null||c<=0)continue;
        if(first===null)first=c;else if(c!==first)mono=false;
        rankCache.set(nm,abs?Math.min(NCLS-1,Math.max(0,Math.floor(c*NCLS))):0);
      }
      if(!abs){
        const arr=[];
        for(const f of features){
          const nm=f.properties&&f.properties.name;
          const c=cache.get(nm);
          if(c>0)arr.push([nm,c]);
        }
        arr.sort((a,b)=>a[1]-b[1]);
        for(let i=0;i<arr.length;i++){
          rankCache.set(arr[i][0],Math.min(NCLS-1,Math.floor(i*NCLS/arr.length)));
        }
        return !arr.length||arr[0][1]===arr[arr.length-1][1];
      }
      return mono;
    };
    degraded=false;
    const mono=computeRanks(covCache);
    fillCache=covCache;
    // 2026-11-13 用户指令「省级 url 缺失也应该是灰色的」: 全国图（省级层）
    // 该类型的**省级机构自身** u 缺失 → 强制灰（仅改着色缓存, covCache 保留
    // 辖域真实覆盖率供浮层/详情展示）——省监委无官网的省必须灰, 即使辖域
    // 内有县级监委有官网。
    const applyProvGray=(cache)=>{
      if(level!=="china"||curType==="all")return cache;
      const fc=new Map(cache);
      for(const f of features){
        const nm=f.properties&&f.properties.name;
        const pu=provU.get(nm);
        if(pu&&!pu[curType])fc.set(nm,0);
      }
      return fc;
    };
    fillCache=applyProvGray(fillCache);
    if(mono&&curType!=="all"&&mode==="block"){
      // 末级单类型天然二元（区县该类型机构只有 1 个: 有/无官网）——
      // 无差异可显时降级为综合覆盖着色, 保持地图信息量（tooltip 仍显示该类型真实值）
      // 2026-11-13 用户指正: 降级仅在该类型**全县都有官网**（全 >0）时才有
      // 「单值无差异」的意义; 部分有部分无（廊坊 10 县仅文安有 gov）时
      // 不得降级——0 值县必须保持灰色（「没有 url 是灰色的」硬规则）,
      // 有值县显示该类型真实色。mono 只统计非零值, 不能作降级依据。
      let allHas=true;
      for(const f of features){
        const c=covCache.get(f.properties&&f.properties.name);
        if(!(c>0)){allHas=false;break;}
      }
      if(mono&&allHas){
      const allCache=new Map();
      for(const f of features){
        const nm=f.properties&&f.properties.name;
        let m=stats.get(nm);
        // 2026-11-13 米林市灰根因: geo 特征旧名「米林县」vs 树节点「米林市」——
        // 降级块此前直查 stats 无 baseName 回退, 米林 allCache=-1 灰。
        // 与 covOf/statOf 同款基底回退（木里县↔木里藏族自治县同一套规则）。
        if(!m&&baseIndex){
          const c=baseIndex.get(baseName(nm));
          if(c)m=stats.get(c);
        }
        allCache.set(nm,(m&&m.all&&m.all.total)?m.all.u/m.all.total:-1);
      }
      computeRanks(allCache);
      fillCache=allCache;
      fillCache=applyProvGray(fillCache);
      degraded=true;
      }
    }
    // 2026-11-16 相邻区分度重构（终版, 全层级统一）:
    // 每区划独立色 = 覆盖率升序 × 黄金角(137.508°) 在 360° 全环展开——
    // 覆盖率相邻(空间上往往相邻)的区划色距恒 137.5°, 新疆 24 州市/34 省/
    // 大市 20+ 县不再出现同档大片同色; 灰=无官网/无机构不变, 覆盖率由
    // 浮层/档案卡承载。
    shiftDefs=new Map();
    const sc=schemeVal();
    {
      const names=[];
      for(const f of features){
        const nm=f.properties&&f.properties.name;
        const c=fillCache.get(nm);
        if(c===undefined||c===null||c<=0)continue;
        names.push([nm,c]);
      }
      names.sort((a,b)=>a[1]-b[1]);
      const n=names.length;
      for(let i=0;i<n;i++){
        const deg=sc.start+(n>1?(i*137.508)%sc.span:sc.span/2);
        const base=hslToHex(deg,sc.sat,sc.lum);
        const id="mzx"+i;
        grad(id,shade(base,0.10),shade(base,-0.12));
        shiftDefs.set(names[i][0],id);
      }
    }
    const BORD=theme==="dark"?"#17150f":"#fdfbf5";
    const LABEL=theme==="dark"?"#ddd5c0":"#453e30";
    const HALO=O[1];
    // 地名处理: 全国层只剥行政后缀（民族后缀不剥——「西藏」以「藏」结尾
    // 会被 藏族? 误剥成「西」、「内蒙古」→「内」、「北京」→「北」,
    // 2026-11-16 曾因此全国图大量单字标注）; 省/县级再循环剥民族后缀,
    // 剥到剩 1 字即停。不截断——长名分两行(≤5字/行)完整展示, >10 字才截。
    function labelOf(name){
      if(level==="china")return [name.replace(/(省|市|自治区|维吾尔|壮族|回族|特别行政区)/g,"")];
      let t=name.replace(level==="city"
        ?/(自治县|自治州|县|区|市|旗)$/
        :/(自治州|地区|盟|自治县|市|县|区|旗)$/,"");
      // 单字名保护（香港「北区」→剥「区」剩「北」单字不美观）: 回退用原名剥括号
      if(t.length<2)t=name.replace(/[（(][^（）)]*[）)]$/,"");
      for(let i=0;i<8;i++){
        const t2=t.replace(ETH_END,"");
        if(t2===t||t2.length<2)break;
        t=t2;
      }
      if(t.length<=5)return [t];
      if(t.length<=10){
        const m=Math.ceil(t.length/2);
        return [t.slice(0,m),t.slice(m)];
      }
      return [t.slice(0,5),t.slice(5,10)];
    }
    const placed=[];   // 已放置标注包围盒（防重叠: 大区域优先）
    const insetFeats=features.filter(f=>(f.properties||{}).name==="三沙市");
    // ---- 第一遍: 建组+路径 ----
    const built=[];
    for(const f of features){
      if((f.properties||{}).name==="三沙市")continue;
      const p=f.properties||{};
      const name=p.name;
      const g=document.createElementNS(NS,"g");
      g.setAttribute("class","mz");
      const path=document.createElementNS(NS,"path");
      path.setAttribute("d",pathOf(f.geometry,pr));
      path.setAttribute("fill",colorOf(name));
      path.setAttribute("stroke",BORD);
      path.setAttribute("stroke-width",level==="china"?1.5:1.1);
      path.setAttribute("stroke-opacity","1");
      path.setAttribute("stroke-linejoin","round");
      g.appendChild(path);
      // 2026-11-16 小区域点击热区: 天津/上海/澳门等在全国图上仅十几像素,
      // 用户放大后仍难点中——小区域额外加透明宽描边热区 path(仅描边命中,
      // 视觉不变), 点击/悬停范围扩大到 10px 外扩。面积判断用经纬度跨度×
      // 投影系数估算(创建时 getBBox 未布局=0×0, 会误判全部为小区域)
      if(level!=="city"){
        const kEst=Math.min(W/(range.maxLon-range.minLon),H/(range.maxLat-range.minLat))*0.94;
        const g0=f.geometry;
        const polys=g0.type==="Polygon"?[g0.coordinates]:g0.coordinates;
        let mnLo=999,mxLo=-999,mnLa=999,mxLa=-999;
        for(const poly of polys)for(const ring of poly)for(const pt of ring){
          if(pt[0]<mnLo)mnLo=pt[0];if(pt[0]>mxLo)mxLo=pt[0];
          if(pt[1]<mnLa)mnLa=pt[1];if(pt[1]>mxLa)mxLa=pt[1];
        }
        if((mxLo-mnLo)*kEst*(mxLa-mnLa)*kEst<600){
          const hit=document.createElementNS(NS,"path");
          hit.setAttribute("d",pathOf(f.geometry,pr));
          hit.setAttribute("fill","none");
          hit.setAttribute("stroke","transparent");
          hit.setAttribute("stroke-width","10");
          hit.setAttribute("pointer-events","stroke");
          g.insertBefore(hit,path);
          g.style.cursor="pointer";
        }
      }
      const applySel=()=>{
        if(selName===name){
          path.setAttribute("stroke","#e7b93c");path.setAttribute("stroke-width","2.6");
          path.setAttribute("stroke-opacity","1");
          path.setAttribute("filter","drop-shadow(0 0 5px rgba(231,185,60,.75))");
        }else{
          path.setAttribute("stroke",BORD);
          path.setAttribute("stroke-width",level==="china"?1.5:1.1);
          path.setAttribute("stroke-opacity","1");
          path.removeAttribute("filter");
        }
      };
      applySel();
      g.addEventListener("mousemove",e=>{
        if(selName!==name){path.setAttribute("stroke","#e7b93c");path.setAttribute("stroke-width","2");path.setAttribute("stroke-opacity","1")}
        const c=covCache.get(name);
        let cov;
        if(c===undefined||c===-1)cov="暂无数据";
        else if(c===-2)cov="无该类机构";
        else if(c===0)cov="暂无官网";
        else cov="覆盖率 "+(c*100).toFixed(1)+"%";
        const ad=typeof p.adcode==="number"?String(p.adcode):p.adcode;
        const act=(level==="china"&&ad)||(level==="province"&&ad&&CITY_FILES.has(ad))
          ?"点击下钻":(level!=="city"?"点击看详情":"");
        const t=ensureTip();
        // 2026-11-16 用户指令: 合署办公特别标注（tooltip 层, 与列表/树图一致）
        const mm=_mOf(name);
        t.textContent=name+(mm?" 🤝合署":"")+" · "+cov+(act?" · "+act:"");
        t.style.display="block";
        const r=el.getBoundingClientRect();
        let x=e.clientX-r.left+14,y=e.clientY-r.top+12;
        if(x+t.offsetWidth>r.width-8)x=e.clientX-r.left-t.offsetWidth-14;
        if(y+t.offsetHeight>r.height-8)y=e.clientY-r.top-t.offsetHeight-12;
        t.style.left=Math.max(4,x)+"px";t.style.top=Math.max(4,y)+"px";
      });
      g.addEventListener("mouseleave",()=>{if(tip)tip.style.display="none";applySel()});
      g.addEventListener("click",()=>{
        selName=name;
        const ad=typeof p.adcode==="number"?String(p.adcode):p.adcode;
        if(level==="china"&&ad){
          // 全国 → 省图（市级）
          render();
          loadProvince(ad,name);
        }else if(level==="province"&&ad&&CITY_FILES.has(ad)){
          // 省图 → 市图（县级）；无县级文件的区划（直辖市区/省直管县）直接看详情
          render();
          loadCity(ad,name);
        }else{
          render();
          if(onSelect)onSelect(name);
        }
      });
      rootG.appendChild(g);
      const bb=path.getBBox();
      built.push({g,path,p,name,area:bb.width*bb.height});
    }
    rootG.appendChild(labelG);   // 标注层最后挂载 → 永远在最上层
    // ---- 第二遍: 标注（大区域优先, 防重叠, 碰撞时逐级缩小字号, 过小不标）----
    built.sort((a,b)=>b.area-a.area);
    const minArea=level==="city"?8:level==="province"?20:36;
    for(const it of built){
      const {g,p,name}=it;
      // 2026-11-16 全国图港澳入口: 香港/澳门多边形极小被面积阈值跳过,
      // 用户找不到入口——港澳台豁免阈值强制标注（文字可偏移到区外）
      const FORCE=level==="china"&&/(香港|澳门|台湾)/.test(name);
      if(it.area<minArea&&!FORCE)continue;   // 过小区划不标名（hover 浮层可见）
      if(!(p.centroid||p.center))continue;
      const [cx,cy]=pr(p.centroid||p.center||[0,0]);
      const t=document.createElementNS(NS,"text");
      t.setAttribute("text-anchor","middle");
      t.setAttribute("fill",LABEL);t.setAttribute("font-weight","600");
      t.setAttribute("paint-order","stroke");t.setAttribute("stroke",HALO);
      t.setAttribute("pointer-events","none");
      labelG.appendChild(t);
      const base=level==="china"?12:level==="province"?11:10;
      // 2026-11-16 标注三改: ①字号 +1 且下限 5.5→7(太小看不见); ②描边 2.2px
      // →1.5px、小字号 1.1px(厚描边吃字形=模糊主因); ③偏移候选 21→48 组
      // 螺旋外扩, 显示率提升
      const offs=[[0,0],[0,-8],[0,8],[10,0],[-10,0],[8,-6],[-8,-6],[8,6],[-8,6],
                  [0,-15],[0,15],[17,0],[-17,0],[15,-9],[-15,-9],[15,9],[-15,9],
                  [0,-23],[0,23],[26,0],[-26,0],[22,-12],[-22,-12],[22,12],[-22,12],
                  [0,-31],[0,31],[35,0],[-35,0],[30,-16],[-30,-16],[30,16],[-30,16],
                  [0,-40],[0,40],[45,0],[-45,0],[38,-20],[-38,-20],[38,20],[-38,20]];
      let ok=false;
      const setLines=(lines,lh,f)=>{
        while(t.firstChild)t.removeChild(t.firstChild);
        for(let i=0;i<lines.length;i++){
          const ts=document.createElementNS(NS,"tspan");
          if(i>0)ts.setAttribute("dy",lh);
          ts.textContent=lines[i];
          t.appendChild(ts);
        }
        t.setAttribute("font-size",f);
        t.setAttribute("stroke-width",f<=7.5?"1.1px":"1.5px");
      };
      const tryPlace=(lines,fs)=>{
        for(let f=fs;f>=7;f-=0.5){
          setLines(lines,f+2.2,f);
          for(const [ox,oy] of offs){
            t.setAttribute("x",Math.round((cx+ox)*2)/2);t.setAttribute("y",Math.round((cy+3+oy)*2)/2);
            const bb=t.getBBox(),pad=2;
            const box=[bb.x-pad,bb.y-pad,bb.width+2*pad,bb.height+2*pad];
            let hit=false;
            for(const q of placed){
              if(!(box[0]>q[0]+q[2]||box[0]+box[2]<q[0]||box[1]>q[1]+q[3]||box[1]+box[3]<q[1])){hit=true;break}
            }
            if(!hit){
              placed.push(box);
              // 2026-11-16 密集区引线: 重庆九龙坡等质心被占时标注偏移较远,
              // 偏移>16px 画虚线引线回质心, 归属一目了然
              const dist=Math.hypot(ox,oy);
              if(dist>16){
                const ln=document.createElementNS(NS,"line");
                const bbx=t.getBBox();
                ln.setAttribute("x1",bbx.x+bbx.width/2);ln.setAttribute("y1",bbx.y+bbx.height/2);
                ln.setAttribute("x2",cx);ln.setAttribute("y2",cy);
                ln.setAttribute("stroke",LABEL);ln.setAttribute("stroke-width","0.7");
                ln.setAttribute("stroke-dasharray","2,2");ln.setAttribute("opacity","0.5");
                ln.setAttribute("pointer-events","none");
                labelG.insertBefore(ln,t);
              }
              return true;
            }
          }
        }
        return false;
      };
      ok=tryPlace(labelOf(name),base);
      // 全名放不下 → 简称重试（武侯区→武侯, 江岸区→江岸）; 仍失败才弃
      if(!ok&&level==="city"){
        const short=name.replace(/(自治县|自治旗|林区|矿区|县|市|区|旗)$/,"");
        if(short&&short!==name)ok=tryPlace([short],Math.max(7.5,base-1));
      }
      if(!ok&&t.parentNode)t.parentNode.removeChild(t);   // t 在 labelG 顶层组, 非原 g 组（曾 g.removeChild(t) 抛 NotFoundError 中断下钻）
    }
    // ---- 南海诸岛插图（三沙市: 主图右下角小框）----
    drawInset(insetFeats,LABEL,HALO,O[1]);
    refreshLegend();
    // 下钻/切视图淡入
    rootG.style.opacity="0";
    requestAnimationFrame(()=>{
      rootG.style.transition="opacity .45s ease";
      rootG.style.opacity="1";
    });
  }
  // 南海诸岛插图: 三沙市单独画在主图右下角小框（常规制图做法,
  // 避免南海海域把海南岛主图压缩成小点）
  function drawInset(feats,LABEL,HALO,bgcol){
    if(!feats.length)return;
    const W=el.clientWidth||900,H=el.clientHeight||600;
    const IW=Math.min(200,W*0.28),IH=Math.min(135,H*0.26);
    const ix=W-IW-10,iy=H-IH-10;
    const bg=document.createElementNS(NS,"rect");
    bg.setAttribute("x",ix);bg.setAttribute("y",iy);bg.setAttribute("width",IW);bg.setAttribute("height",IH);
    bg.setAttribute("rx","7");bg.setAttribute("fill",bgcol);
    bg.setAttribute("stroke",theme==="dark"?"rgba(216,209,190,.28)":"rgba(82,72,52,.25)");
    bg.setAttribute("stroke-width","1");
    svg.appendChild(bg);
    let mnLo=999,mxLo=-999,mnLa=999,mxLa=-999;
    for(const f of feats){
      const g0=f.geometry;
      const polys=g0.type==="Polygon"?[g0.coordinates]:g0.coordinates;
      for(const poly of polys)for(const ring of poly)for(const pt of ring){
        if(pt[0]<mnLo)mnLo=pt[0];if(pt[0]>mxLo)mxLo=pt[0];
        if(pt[1]<mnLa)mnLa=pt[1];if(pt[1]>mxLa)mxLa=pt[1];
      }
    }
    const pad=8;
    const kx=(IW-2*pad)/(mxLo-mnLo||1),ky=(IH-2*pad)/(mxLa-mnLa||1);
    const k=Math.min(kx,ky);
    const ox0=ix+(IW-(mxLo-mnLo)*k)/2,oy0=iy+(IH-(mxLa-mnLa)*k)/2;
    const pr2=([lon,lat])=>[ox0+(lon-mnLo)*k,oy0+(mxLa-lat)*k];
    for(const f of feats){
      const p=f.properties||{},name=p.name;
      const g=document.createElementNS(NS,"g");
      g.setAttribute("class","mz");
      const path=document.createElementNS(NS,"path");
      path.setAttribute("d",pathOf(f.geometry,pr2));
      path.setAttribute("fill",colorOf(name));
      path.setAttribute("stroke",theme==="dark"?"#2e2a22":"#fbf8f0");
      path.setAttribute("stroke-width","0.7");
      path.setAttribute("stroke-opacity",".9");
      path.setAttribute("stroke-linejoin","round");
      g.appendChild(path);
      g.addEventListener("mousemove",e=>{
        path.setAttribute("stroke","#e7b93c");path.setAttribute("stroke-width","1.6");
        const c=covCache.get(name);
        const t=ensureTip();
        t.textContent=name+" · "+(c>0?"覆盖率 "+(c*100).toFixed(1)+"%":c===0?"暂无官网":"无该类机构")+" · 点击看详情";
        t.style.display="block";
        const r=el.getBoundingClientRect();
        let x=e.clientX-r.left+14,y=e.clientY-r.top+12;
        if(x+t.offsetWidth>r.width-8)x=e.clientX-r.left-t.offsetWidth-14;
        if(y+t.offsetHeight>r.height-8)y=e.clientY-r.top-t.offsetHeight-12;
        t.style.left=Math.max(4,x)+"px";t.style.top=Math.max(4,y)+"px";
      });
      g.addEventListener("mouseleave",()=>{
        if(tip)tip.style.display="none";
        path.setAttribute("stroke",theme==="dark"?"#2e2a22":"#fbf8f0");path.setAttribute("stroke-width","0.7");
      });
      g.addEventListener("click",()=>{render();if(onSelect)onSelect(name)});
      svg.appendChild(g);
    }
    const tt=document.createElementNS(NS,"text");
    tt.setAttribute("x",ix+7);tt.setAttribute("y",iy+13);
    tt.setAttribute("font-size","8.5");tt.setAttribute("fill",LABEL);
    tt.setAttribute("paint-order","stroke");tt.setAttribute("stroke",bgcol);tt.setAttribute("stroke-width","3px");
    tt.setAttribute("pointer-events","none");
    tt.textContent="南海诸岛（三沙市）";
    svg.appendChild(tt);
  }
  let lastRegion=null;   // 当前层级所属区划名（层级/类型切换时右侧详情跟随刷新）
  function loadChina(){
    level="china";curProv=null;curProvCode="";curCity=null;curCityCode="";selName=null;lastRegion=null;
    range={minLon:MINLON,maxLon:MAXLON,minLat:MINLAT,maxLat:MAXLAT};
    features=window.__GEO_CHINA__?window.__GEO_CHINA__.features:[];
    render();
    if(onLevelChange)onLevelChange(level,{});
    try{if(onRegion)onRegion(null)}catch(e){console.warn(e)}
  }
  function loadProvince(adcode,name,next){
    if(window["__GEO_"+adcode+"__"]){
      setProvince(adcode,name);
      if(next)next();
      return;
    }
    if(onLevelChange)onLevelChange("loading",{adcode,name});
    const s=document.createElement("script");
    s.src="data/geo/geo_"+adcode+".js?v=20261111c";
    s.onload=()=>{setProvince(adcode,name);if(next)next();};
    s.onerror=()=>{
      console.warn("省数据加载失败: "+adcode);
      render();
      if(onLevelChange)onLevelChange(level,{prov:curProv,city:curCity});
      if(onSelect)onSelect(name);   // 无市级边界数据的省（台湾/港澳）→ 直接看详情
    };
    document.head.appendChild(s);
  }
  function loadCity(adcode,name,next){
    if(window["__GEO_"+adcode+"__"]){
      setCity(adcode,name);
      if(next)next();
      return;
    }
    if(onLevelChange)onLevelChange("loading",{adcode,name});
    const s=document.createElement("script");
    s.src="data/geo/geo_"+adcode+".js?v=20261111c";
    s.onload=()=>{setCity(adcode,name);if(next)next();};
    s.onerror=()=>{
      console.warn("市数据加载失败: "+adcode);
      if(onLevelChange)onLevelChange("error",{adcode,name});
    };
    document.head.appendChild(s);
  }
  function setProvince(adcode,name){
    curProvCode=adcode;curProv=name;curCity=null;curCityCode="";
    level="province";selName=null;lastRegion=name;
    setGeo(adcode);
    try{if(onRegion)onRegion(name)}catch(e){console.warn(e)}
  }
  function setCity(adcode,name){
    curCityCode=adcode;curCity=name;
    level="city";selName=null;lastRegion=name;
    setGeo(adcode);
    try{if(onRegion)onRegion(name)}catch(e){console.warn(e)}
  }
  function setGeo(adcode){
    const d=window["__GEO_"+adcode+"__"];
    features=d&&d.features?d.features:[];
    // 省图重投影: 按该省边界范围适配
    let mnLo=999,mxLo=-999,mnLa=999,mxLa=-999;
    function scanPoly(p){
      for(const ring of p)for(const pt of ring){
        if(pt[0]<mnLo)mnLo=pt[0];if(pt[0]>mxLo)mxLo=pt[0];
        if(pt[1]<mnLa)mnLa=pt[1];if(pt[1]>mxLa)mxLa=pt[1];
      }
    }
    for(const f of features){
      const g=f.geometry;
      if((f.properties||{}).name==="三沙市")continue;   // 南海诸岛走插图, 不参与主图范围
      if(g.type==="Polygon")scanPoly(g.coordinates);
      else if(g.type==="MultiPolygon")for(const p of g.coordinates)scanPoly(p);
    }
    if(mxLo>mnLo){
      // 2026-11-16 澳门白图根因: 旧版 lat 固定 ±1° 扩展——澳门纬度跨度仅
      // 0.08°, 被 +2° 压成 15×10px 的横线（"只能看到文字看不到地图"）;
      // 改为按区域实际跨度等比扩展（lon 8% / lat 10%），小区域同样放大充满容器
      const padLo=(mxLo-mnLo)*0.08, padLa=Math.max(mxLa-mnLa,0.001)*0.10;
      range={minLon:mnLo-padLo,maxLon:mxLo+padLo,minLat:mnLa-padLa,maxLat:mxLa+padLa};
    }
    render();
    if(onLevelChange)onLevelChange(level,{adcode,prov:curProv,city:curCity});
  }
  function back(){
    if(level==="city"){loadProvince(curProvCode,curProv);}
    else if(level==="province"){loadChina()}
  }
  let tip=null,lg=null;
  // 2026-11-16 合署标注: 区划名 → 树节点 m（含 合署/区政合一/镜像 判定）
  function _mOf(name){
    if(!tree)return "";
    const b=baseName(name);
    let r="";
    (function f(n){if(r)return;if(baseName(n.n||"")===b&&n.m&&/合署|区政合一|镜像/.test(n.m)){r=n.m;return}for(const k of n.ks||[])f(k)})(tree);
    return r;
  }
  function ensureTip(){
    if(tip)return tip;
    tip=document.createElement("div");
    tip.style.cssText="position:absolute;z-index:7;pointer-events:none;display:none;"
      +"font-size:11.5px;padding:5px 9px;border-radius:7px;"
      +"background:var(--panel,#fff);border:1px solid var(--line,#e5e5e5);"
      +"color:var(--text,#333);box-shadow:0 3px 12px rgba(0,0,0,.18);"
      +"white-space:nowrap;font-weight:500";
    el.appendChild(tip);
    return tip;
  }
  function refreshLegend(){
    if(!lg)return;
    const G=GRAY(),sc=schemeVal();
    lg.style.background=theme==="dark"?"var(--panel,#1e1c16)":"var(--panel,#fff)";
    // 全层级: 每区划独立色（黄金角在方案色相范围内展开, 相邻区划色距大;
    // 灰=无官网/无机构; 右侧圆点=配色方案, 点选即换, 偏好本地保存）
    const stops=[];
    for(let i=0;i<=6;i++)stops.push(hslToHex(sc.start+sc.span*i/6,sc.sat,sc.lum));
    const dots=Object.keys(SCHEMES).map(id=>{
      const s=SCHEMES[id],on=id===schemeId;
      const cone=[0,60,120,180,240,300].map(d=>hslToHex(s.start+s.span*d/360,s.sat,s.lum)).join(",");
      return `<span data-scheme="${id}" title="${s.name}${on?"（当前）":""}" style="width:15px;height:15px;border-radius:50%;display:inline-block;vertical-align:middle;cursor:pointer;pointer-events:auto;background:conic-gradient(${cone});box-shadow:inset 0 0 0 2px ${on?"var(--accent,#b23a2e)":"rgba(128,128,128,.35)"}"></span>`;
    }).join("");
    lg.innerHTML=`<span>每区划独立色</span>`
      +`<span style="width:92px;height:8px;border-radius:4px;display:inline-block;box-shadow:inset 0 0 0 1px rgba(0,0,0,.08);background:linear-gradient(to right,${stops.join(",")})"></span>`
      +`<span style="margin-left:8px;width:10px;height:10px;border-radius:2px;background:${G.zero};display:inline-block"></span><span>无官网</span>`
      +`<span style="width:10px;height:10px;border-radius:2px;background:${G.noorg};display:inline-block"></span><span>无机构</span>`
      +`<span style="margin-left:10px;display:inline-flex;gap:6px;align-items:center">${dots}</span>`;
    lg.title=degraded
      ?"本级该类型机构均为有/无官网（无差异），按综合覆盖着色"
      :"每个区划独立颜色（黄金角展开，覆盖率见浮层/档案卡；灰=无官网/无机构；右侧圆点切换配色）";
    lg.querySelectorAll("[data-scheme]").forEach(d=>{
      d.onclick=()=>{
        schemeId=d.getAttribute("data-scheme");
        try{localStorage.setItem("govMapScheme",schemeId)}catch(e){}
        render();
      };
    });
  }
  function mount(container,t,opts){
    el=container;tree=t;onSelect=opts&&opts.onSelect;onLevelChange=opts&&opts.onLevel;onTypeChange=opts&&opts.onType;onRegion=opts&&opts.onRegion;
    if(window.__GEO_CHINA__&&!window.__GEO_CHINA__.features){window.__errs=(window.__errs||[]);}
    calcStats(t);
    if(window.__ADCODE__){
      adcByName=new Map(Object.entries(window.__ADCODE__).map(([k,v])=>[k,v.adcode]));
    }
    el.innerHTML="";
    if(getComputedStyle(el).position==="static")el.style.position="relative";
    svg=document.createElementNS(NS,"svg");
    svg.setAttribute("style","width:100%;height:100%;display:block");
    el.appendChild(svg);
    // 图例: 覆盖率 低→高 + 灰态说明（随主题刷新）
    lg=document.createElement("div");
    lg.style.cssText="position:absolute;left:10px;bottom:10px;z-index:5;display:flex;align-items:center;gap:6px;"
      +"font-size:11px;color:var(--sub,#666);opacity:.94;"
      +"padding:5px 10px;border-radius:9px;border:1px solid var(--line,#e5e5e5);box-shadow:0 2px 8px rgba(0,0,0,.12);pointer-events:none;white-space:nowrap";
    lg.title="每个区划独立颜色（黄金角色环展开，覆盖率见浮层/档案卡；灰=无官网/无机构）";
    el.appendChild(lg);
    refreshLegend();
    // 主题联动: 深浅切换时重绘
    try{
      new MutationObserver(()=>{if(features.length)render()}).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
      const mq=window.matchMedia("(prefers-color-scheme: dark)");
      if(mq.addEventListener)mq.addEventListener("change",()=>{if(features.length)render()});
    }catch(e){}
    // 滚轮缩放: 以鼠标位置为焦点（光标下的内容点缩放前后不动）
    svg.addEventListener("wheel",e=>{
      e.preventDefault();
      const r=el.getBoundingClientRect();
      zoomAt(e.clientX-r.left,e.clientY-r.top,e.deltaY<0?1.15:0.87);
    },{passive:false});
    // 拖拽平移
    let drag=false,sx=0,sy=0;
    svg.addEventListener("mousedown",e=>{
      if(e.target.closest(".mz"))return;
      drag=true;sx=e.clientX-ox;sy=e.clientY-oy;
    });
    window.addEventListener("mousemove",e=>{if(drag){ox=e.clientX-sx;oy=e.clientY-sy;clampT();applyT()}});
    window.addEventListener("mouseup",()=>{drag=false});
    loadChina();
  }
  // 以容器内 (cx,cy) 为焦点缩放: o' = p - (p-o)*k
  function zoomAt(cx,cy,f){
    const ns=Math.min(8,Math.max(1,scale*f));
    const k=ns/scale;
    ox=cx-(cx-ox)*k;
    oy=cy-(cy-oy)*k;
    scale=ns;
    clampT();
    applyT();
  }
  // 平移边界钳制: 内容放大后不许整图滑出视口（复位前不丢图）
  function clampT(){
    const W=el.clientWidth||900,H=el.clientHeight||600;
    const mw=Math.max(0,W*(scale-1)),mh=Math.max(0,H*(scale-1));
    ox=Math.min(0,Math.max(-mw,ox));
    oy=Math.min(0,Math.max(-mh,oy));
    ox=Math.round(ox*2)/2;   // 半像素对齐, 降低亚像素模糊
    oy=Math.round(oy*2)/2;
  }
  function applyT(){
    if(rootG)rootG.setAttribute("transform",`translate(${ox},${oy}) scale(${scale})`);
  }
  function setTree(t,m){
    tree=t;mode=m||"block";
    if(mode==="tiao")calcStatsTiao(t);else calcStats(t);
    if(features.length)render();
  }
  // 条模式统计: 垂直系统节点 → 区划名 → 子树聚合 URL 覆盖
  // （省级节点常含市级子级, 须向上聚合——曾只统计叶子导致全国图全灰）
  function calcStatsTiao(t){
    stats.clear();
    const STRIP=/(高级|中级)?人民法院$|人民法院$|法院$|州中院$|中院$|人民检察院$|检察院$|人大$|政协$|监察委员会$|监委$|委员会$/;
    (function w(n){
      if(n.t===curType){
        const bare=n.n.replace(STRIP,"");
        let u=0,total=0;
        if(n.ks&&n.ks.length){
          for(const k of n.ks){const sub=w(k);u+=sub.u;total+=sub.total;}
        }else{
          total=1;if(n.u)u=1;
        }
        stats.set(bare,{u,total});
        return {u,total};
      }
      let u=0,total=0;
      for(const k of n.ks||[]){const sub=w(k);u+=sub.u;total+=sub.total;}
      return {u,total};
    })(t);
    rebuildBaseIndex();
  }
  function setType(t){
    curType=t;
    if(mode==="tiao"&&tree)calcStatsTiao(tree);
    if(features.length)render();
    if(onTypeChange)onTypeChange(t);
    try{if(onRegion)onRegion(lastRegion)}catch(e){console.warn(e)}   // 类型切换时详情卡同步刷新（全国状态 lastRegion=null 也要刷）
  }
  function getType(){return curType}
  // 供页面层详情卡展示: 当前类型下该区划辖域覆盖 {u,total}（无数据→null）
  function statOf(name){
    let m=stats.get(name);
    if(!m&&baseIndex){
      const c=baseIndex.get(baseName(name));
      if(c)m=stats.get(c);
    }
    if((!m||!m.gov)&&adcByName){
      const a=adcByName.get(name);
      if(a){
        for(const [n,aa] of adcByName){
          if(aa===a&&stats.has(n)){m=stats.get(n);break}
        }
      }
    }
    if(!m)return null;
    if(mode==="tiao")return m;
    if(curType==="all")return m.all||null;
    return m[curType]||null;
  }
  function fit(){scale=1;ox=0;oy=0;clampT();applyT()}
  // 按钮缩放: 以视口中心为焦点
  function zoom(f){zoomAt((el.clientWidth||900)/2,(el.clientHeight||600)/2,f)}
  // 书签/深链: 当前层级区划信息
  function regionInfo(){return {level:level,prov:curProv,city:curCity}}
  // 书签/深链: 按名字直达 省/市 图（基底名匹配, geo 异步加载链式下钻）
  function goTo(provName,cityName,type){
    const china=(window.__GEO_CHINA__||{}).features||[];
    const pf=china.find(f=>(f.properties||{}).name===provName
      ||baseName((f.properties||{}).name)===baseName(provName));
    if(!pf)return false;
    const pad=String(pf.properties.adcode), pnm=pf.properties.name;
    const goCity=()=>{
      if(!cityName)return;
      const cf=(features||[]).find(f=>(f.properties||{}).name===cityName
        ||baseName((f.properties||{}).name)===baseName(cityName));
      if(cf){
        const ad=typeof cf.properties.adcode==="number"?String(cf.properties.adcode):cf.properties.adcode;
        if(CITY_FILES.has(ad))loadCity(ad,cf.properties.name,()=>{if(type)setType(type)});
        else if(type)setType(type);
      }else if(type)setType(type);
    };
    if(type)setType(type);
    if(!cityName&&type)setType(type);
    loadProvince(pad,pnm,goCity);
    return true;
  }
  return {mount,setTree,back,fit,zoom,level:()=>level,setType,getType,statOf,mode:()=>mode,regionInfo,goTo};
})();
