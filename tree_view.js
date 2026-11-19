/* 树图渲染共享库 v2 —— 美化版（2026-11-09 参考 jsmind/simple-mind-map 专题研究）。
   设计要点: Flat UI 色板实色节点+白字 · 轻阴影 hover 浮起 · 圆形展开器
   · 类型图标 · 2.2px 曲线连线 · 点阵画布 · 根节点放大 · 选中光环。 */
window.TreeViz=(function(){
  const NS="http://www.w3.org/2000/svg";
  // 彩虹 7 色（同级兄弟按序循环, 白字可读的深调彩虹）
  const RAINBOW=["#e74c3c","#e67e22","#f39c12","#27ae60","#16a085","#2980b9","#8e44ad"];
  const FLAT={root:"#5e35b1",block:"#7f8c8d"};   // 根/板块专用
  function col(t){return FLAT[t]||"#8e44ad"}
  const ICO={root:"🏛",block:"▦",gov:"🏛",govhome:"🏛",dept:"📋",rd:"🗳",zx:"🤝",
    fy:"⚖",jcy:"🔍",jw:"🛡",party:"🏴",qt:"👥",binglie:"◇",group:"▪"};
  const TYPE_CN={gov:"人民政府",dept:"内设部门",rd:"人大",zx:"政协",fy:"法院",jcy:"检察院",
    jw:"监委",party:"党委",qt:"群团",block:"板块",binglie:"并列机关",govhome:"人民政府",root:"根"};
  // 右侧档案卡类型徽章配色（与树图彩虹同源）
  const TCOL={gov:"#e53935",govhome:"#d32f2f",dept:"#f57c00",rd:"#f9a825",zx:"#c0a32c",
    fy:"#2e7d32",jcy:"#00838f",jw:"#1565c0",party:"#5e35b1",qt:"#8e24aa",
    block:"#7c4dff",root:"#7c4dff",group:"#8a7f70",binglie:"#8a7f70"};
  const NH=34,HG=46,VG=6,GG=16;
  let tree=null,container=null,svg=null,rootG=null,defs=null;
  let subRoot=null,onRootChange=null;   // 子图根（任意节点可作根单独查看）
  let expanded=new Set(),pathMap=new Map(),hl=new Set(),selPath=null;
  let scale=1,ox=0,oy=0,tipEl=null,detailEl=null,sideEl=null;
  let lastLaid=new Map();   // path → {x,y,w}（render 后坐标, 供聚焦）
  let anim=null;            // 聚焦动画句柄
  let lastMaxX=0,lastMaxY=0,mm=null,mmCtx=null;   // 小地图
  // 初始视图自适应：换树/换根/首屏展开后自动缩放到「全图入屏」，否则根节点
  // 落在画布左上角、被工具栏遮住（2026-11-19 布局修复）
  let autoFit=false,autoFitRAF=0;
  function tw(s){return Math.max(120,(s||"").length*14+44)}
  function col(t){return FLAT[t]||FLAT.group}
  function assignPaths(n,p){pathMap.set(n,p);(n.ks||[]).forEach((k,i)=>assignPaths(k,p+"/"+i))}
  function isExp(n){return expanded.has(pathMap.get(n))}
  function applyT(){
    if(rootG)rootG.setAttribute("transform",`translate(${ox},${oy}) scale(${scale})`);
    drawMinimap();
  }
  function showTip(n){
    if(!tipEl)return;
    tipEl.style.display="block";
    const tn=tipEl.querySelector(".tn"),tu=tipEl.querySelector(".tu");
    if(tn)tn.textContent=n.n;
    if(tu)tu.innerHTML=n.u?`<a href="${n.u}" target="_blank" rel="noopener">${n.u}</a>`:"（无官网）";
  }
  // 右侧详情面板（选中节点后展示: 类型徽章/名称/层级/URL/备注/操作按钮）
  function renderSide(n,deep){
    if(!sideEl)return;
    sideEl.style.display="block";
    const col=TCOL[n.t]||"#8a7f70";
    sideEl.innerHTML=`
      <div class="vsd">
        <button class="vsd-x" title="关闭">✕</button>
        <div class="vsd-badge" style="background:${col}">${ICO[n.t]||"▪"} ${TYPE_CN[n.t]||n.t}</div>
        <div class="vsd-n">${n.n}</div>
        <div class="vsd-rows">
          <div class="vsd-row"><span class="vsd-k">层级</span><span>第 ${deep+1} 层</span></div>
          <div class="vsd-row"><span class="vsd-k">官网</span>${
            n.u?`<span class="vsd-urlv"><a href="${n.u}" target="_blank" rel="noopener">${n.u}</a></span>`
              :`<span class="vsd-none">（无官网 · 列名）</span>`}</div>
        </div>
        ${n.m?`<div class="vsd-note">${n.m}</div>`:""}
        <div class="vsd-btns">
          ${n.u?`<button class="vsd-btn vsd-pri vsd-open">🔗 打开官网</button>`:""}
          <button class="vsd-btn ${n.u?"":"vsd-pri"} vsd-root">🌳 以此节点为根</button>
          <button class="vsd-btn vsd-up">↑ 返回上层</button>
        </div>
      </div>`;
    const closeBtn=sideEl.querySelector(".vsd-x");
    if(closeBtn)closeBtn.addEventListener("click",()=>{sideEl.style.display="none"});
    const rootBtn=sideEl.querySelector(".vsd-root");
    if(rootBtn)rootBtn.addEventListener("click",()=>setRoot(n));
    const openBtn=sideEl.querySelector(".vsd-open");
    if(openBtn)openBtn.addEventListener("click",()=>window.open(n.u,"_blank"));
    const upBtn=sideEl.querySelector(".vsd-up");
    if(upBtn)upBtn.addEventListener("click",()=>{
      if(subRoot)up();else setRoot(n);
    });
  }
  function showDetail(n,deep){
    renderSide(n,deep);
    if(!detailEl)return;
    if(sideEl)return;   // 右侧 side 面板已在 renderSide 呈现; 旧 #detail 同位置不再重复填（避免重叠双卡）
    detailEl.style.display="block";
    const q=(s)=>detailEl.querySelector(s);
    q(".dn").textContent=n.n;
    q(".dt").textContent=TYPE_CN[n.t]||n.t;
    q(".dl").textContent="第 "+(deep+1)+" 层";
    q(".du").innerHTML=n.u?`<a href="${n.u}" target="_blank" rel="noopener">${n.u}</a>`:"（无官网）";
    const mr=detailEl.querySelector("#mrow"),dm=detailEl.querySelector(".dm");
    if(n.m){if(mr)mr.style.display="flex";if(dm)dm.textContent=n.m}
    else if(mr)mr.style.display="none";
  }
  // 子树高度（render 与调试共用）
  function subH(n){
    if(!isExp(n)||!(n.ks||[]).length)return NH;
    let h=0;
    n.ks.forEach((k,i)=>{h+=subH(k)+(i>0?(n.ks[i-1].t!=="gov"&&k.t==="gov"?GG:VG):0)});
    return Math.max(h,NH);
  }
  function render(){
    if(!svg||!tree)return;
    svg.innerHTML="";
    defs=document.createElementNS(NS,"defs");
    svg.appendChild(defs);
    // 阴影滤镜
    const f1=document.createElementNS(NS,"filter");
    f1.setAttribute("id","tvsh1");f1.setAttribute("x","-20%");f1.setAttribute("y","-20%");
    f1.setAttribute("width","140%");f1.setAttribute("height","160%");
    f1.innerHTML=`<feDropShadow dx="0" dy="1.5" stdDeviation="1.6" flood-color="#000" flood-opacity="0.28"/>`;
    defs.appendChild(f1);
    const f2=document.createElementNS(NS,"filter");
    f2.setAttribute("id","tvsh2");f2.setAttribute("x","-20%");f2.setAttribute("y","-20%");
    f2.setAttribute("width","140%");f2.setAttribute("height","160%");
    f2.innerHTML=`<feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#000" flood-opacity="0.4"/>`;
    defs.appendChild(f2);
    // 点阵背景
    const pat=document.createElementNS(NS,"pattern");
    pat.setAttribute("id","tvdots");pat.setAttribute("width","26");pat.setAttribute("height","26");
    pat.setAttribute("patternUnits","userSpaceOnUse");
    const cd=document.createElementNS(NS,"circle");
    cd.setAttribute("cx","1.5");cd.setAttribute("cy","1.5");cd.setAttribute("r","1.5");
    cd.setAttribute("fill","var(--dotcol,#c8c2b4)");
    pat.appendChild(cd);
    defs.appendChild(pat);
    rootG=document.createElementNS(NS,"g");
    svg.appendChild(rootG);
    const laid=[];
    let maxX=0,maxY=0;
    // 定位（父节点 y = 子树垂直中心）
    function lay(n,deep,x,top,parent,idx){
      const p=pathMap.get(n),exp=isExp(n),kids=(n.ks||[]).length>0;
      const sh=subH(n);
      const y=top+(sh-NH)/2;   // 父节点垂直居中于子树
      const w=tw(n.n);
      const ccol=(n.t==="root"||n.t==="block")?col(n.t):RAINBOW[(idx||0)%7];
      n.__x=x;n.__y=y;n.__w=w;   // 坐标写回数据节点, 供连线使用
      laid.push({n,x,y,w,p,exp,parent,deep,idx,__col:ccol});
      maxX=Math.max(maxX,x+w+70);maxY=Math.max(maxY,top+sh);
      if(exp&&kids){
        let cy=top;
        n.ks.forEach((k,i)=>{
          const gap=(i>0&&n.ks[i-1].t!=="gov"&&k.t==="gov")?GG:VG;
          cy=lay(k,deep+1,x+w+HG,cy+(i>0?gap:0),n,i);   // lay 返回子树底, 直接赋值
        });
      }
      return top+sh;
    }
    lay(subRoot||tree,0,30,30,null,0);
    // 背景（动态尺寸）
    const bg=document.createElementNS(NS,"rect");
    bg.setAttribute("x","0");bg.setAttribute("y","0");
    bg.setAttribute("width",maxX);bg.setAttribute("height",maxY);
    bg.setAttribute("fill","url(#tvdots)");
    rootG.appendChild(bg);
    // 连线（2.2px 曲线, 父色）
    laid.forEach(d=>{
      if(d.parent){
        const pc=d.parent.__col,cc=d.__col;
        const pw=d.parent.__w;
        const x1=d.parent.__x+pw,y1=d.parent.__y+NH/2,x2=d.x-3,y2=d.y+NH/2,mx=(x1+x2)/2;
        // 左右彩虹: 连线从父色渐变到子色
        const gid="lg"+d.p.replace(/\//g,"_");
        const lg=document.createElementNS(NS,"linearGradient");
        lg.setAttribute("id",gid);lg.setAttribute("x1","0");lg.setAttribute("y1","0");
        lg.setAttribute("x2","1");lg.setAttribute("y2","0");
        lg.setAttribute("gradientUnits","userSpaceOnUse");
        lg.setAttribute("x1",x1);lg.setAttribute("x2",x2);
        const s1=document.createElementNS(NS,"stop");
        s1.setAttribute("offset","0%");s1.setAttribute("stop-color",pc);
        const s2=document.createElementNS(NS,"stop");
        s2.setAttribute("offset","100%");s2.setAttribute("stop-color",cc);
        lg.append(s1,s2);
        defs.appendChild(lg);
        const path=document.createElementNS(NS,"path");
        path.setAttribute("d",`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`);
        path.setAttribute("class","link");
        path.setAttribute("stroke",`url(#${gid})`);
        path.setAttribute("stroke-width","2.4");
        path.setAttribute("stroke-opacity","0.85");
        path.setAttribute("fill","none");
        rootG.appendChild(path);
      }
    });
    // 节点
    laid.forEach(d=>{
      const n=d.n,p=d.p;
      const isRoot=n.t==="root"||n.t==="block";
      const g=document.createElementNS(NS,"g");
      g.setAttribute("class","node"+(hl.has(p)?" hl":"")+(selPath===p?" sel":""));
      g.setAttribute("transform",`translate(${d.x},${d.y})`);
      const r=document.createElementNS(NS,"rect");
      r.setAttribute("width",d.w);r.setAttribute("height",NH);
      r.setAttribute("rx","8");r.setAttribute("ry","8");
      r.setAttribute("fill",d.__col);
      r.setAttribute("filter","url(#tvsh1)");
      g.appendChild(r);
      // 选中光环
      if(selPath===p){
        const ring=document.createElementNS(NS,"rect");
        ring.setAttribute("x","-3");ring.setAttribute("y","-3");
        ring.setAttribute("width",d.w+6);ring.setAttribute("height",NH+6);
        ring.setAttribute("rx","10");ring.setAttribute("ry","10");
        ring.setAttribute("fill","none");ring.setAttribute("stroke","var(--sel,#f1c40f)");
        ring.setAttribute("stroke-width","2.5");
        g.appendChild(ring);
      }
      // 类型图标 + 文本
      const fs=isRoot?16:12.5;
      const t=document.createElementNS(NS,"text");
      t.setAttribute("x","12");t.setAttribute("y",NH/2+fs*0.36);
      t.setAttribute("font-size",fs);
      t.setAttribute("font-weight",isRoot?"700":"500");
      t.setAttribute("fill","#fff");
      const ico=ICO[n.t]||"▪";
      const maxc=isRoot?26:34;
      let _nm=n.n.length>maxc?n.n.slice(0,maxc-1)+"…":n.n;
      // 2026-11-16 合署办公特别标注（树图节点名后缀, 与列表/地图一致）
      if(n.m&&/合署|区政合一|镜像/.test(n.m))_nm+=" 🤝";
      t.textContent=ico+" "+_nm;
      g.appendChild(t);
      let xo=d.w-8;
      if(n.u){
        const u=document.createElementNS(NS,"text");
        u.setAttribute("class","u");u.setAttribute("x",xo-16);u.setAttribute("y",NH/2+fs*0.36);
        u.setAttribute("font-size","11.5");u.setAttribute("fill","rgba(255,255,255,.85)");
        u.textContent="🔗";
        u.addEventListener("click",ev=>{ev.stopPropagation();window.open(n.u,"_blank")});
        g.appendChild(u);xo-=22;
      }
      if((n.ks||[]).length){
        // 圆形展开器
        const c=document.createElementNS(NS,"circle");
        c.setAttribute("cx",d.w+9);c.setAttribute("cy",NH/2);
        c.setAttribute("r","8.5");
        c.setAttribute("fill","rgba(255,255,255,.92)");
        c.setAttribute("stroke",d.__col);c.setAttribute("stroke-width","2");
        g.appendChild(c);
        const f=document.createElementNS(NS,"text");
        f.setAttribute("class","fold");f.setAttribute("x",d.w+9);f.setAttribute("y",NH/2+4);
        f.setAttribute("font-size","11");f.setAttribute("font-weight","700");
        f.setAttribute("text-anchor","middle");f.setAttribute("fill",d.__col);
        f.textContent=d.exp?"−":"+";
        g.appendChild(f);
      }
      g.addEventListener("click",()=>{
        const hadKids=(n.ks||[]).length>0;
        if(hadKids){
          expanded.has(p)?expanded.delete(p):expanded.add(p);
          render();
        }
        selPath=p;showDetail(n,d.deep);
        if(hadKids||selPath!==p)render();
        // 聚焦: 视口跟随点击位置居中（有子节点放大 1.25, 叶子放大 1.5）
        focus(p,hadKids?1.25:1.5);
      });
      g.addEventListener("dblclick",()=>{setRoot(n)});
      g.addEventListener("mouseenter",()=>{r.setAttribute("filter","url(#tvsh2)");showTip(n)});
      g.addEventListener("mouseleave",()=>{r.setAttribute("filter","url(#tvsh1)");if(tipEl)tipEl.style.display="none"});
      g.addEventListener("mousemove",e=>{
        if(tipEl){tipEl.style.left=(e.clientX+14)+"px";tipEl.style.top=(e.clientY+10)+"px"}});
      rootG.appendChild(g);
    });
    lastMaxX=maxX+40;lastMaxY=maxY+40;
    // 不设 viewBox：SVG 已由 CSS 撑满容器，viewBox 会按 meet 再缩一次，
    // 把内部 transform 的缩放乘成两倍（2026-11-19 树图错位修复）
    lastLaid.clear();
    laid.forEach(d=>lastLaid.set(d.p,{x:d.x,y:d.y,w:d.w}));
    applyT();
    drawMinimap();
    if(autoFit)tryAutoFit();
  }
  // 初始自适应（瞬时，不做动画）：全图缩放居中；容器尚无尺寸（隐藏/未布局）时
  // 每帧重试，等 Trees 面板真正可见再落位
  function tryAutoFit(){
    if(!autoFit||!container)return;
    const vw=container.clientWidth||0,vh=container.clientHeight||0;
    if(vw<20||vh<20){
      if(autoFitRAF)cancelAnimationFrame(autoFitRAF);
      autoFitRAF=requestAnimationFrame(tryAutoFit);
      return;
    }
    autoFit=false;
    if(autoFitRAF){cancelAnimationFrame(autoFitRAF);autoFitRAF=0}
    const TOP=48;                       // 顶部悬浮工具条留白
    const vh2=Math.max(80,vh-TOP);
    const s0=Math.min(vw/lastMaxX,vh2/lastMaxY);
    if(s0>=0.45){
      // 全图基本装得下 → 整体缩放居中（根在左上、被工具栏压住的老问题）
      scale=Math.min(1.15,s0);
      ox=(vw-scale*lastMaxX)/2;
      oy=TOP+(vh2-scale*lastMaxY)/2;
    }else{
      // 图太高（展开到 32 省）：不缩成看不清的蚂蚁图，按可读比例把「根节点」
      // 钉在视区左上；根在子树里是垂直居中的，直接贴 (0,0) 会把根甩到屏外。
      // 需要看全时用「适应窗口」按钮。
      const rt=subRoot||tree;
      const rx=rt.__x==null?30:rt.__x, ry=rt.__y==null?30:rt.__y;
      scale=Math.max(0.5,Math.min(0.9,vw/lastMaxX));
      ox=16-rx*scale;
      oy=TOP+10-ry*scale;
    }
    applyT();
  }
  function mount(cont,t,opts){
    container=cont;tree=t;tipEl=opts&&opts.tip;detailEl=opts&&opts.detail;
    onRootChange=opts&&opts.onRoot;subRoot=null;
    sideEl=opts&&opts.sidePanel||null;
    mm=opts&&opts.minimap||null;
    if(mm){
      const cv=document.createElement("canvas");
      cv.width=mm.clientWidth||170;cv.height=mm.clientHeight||110;
      cv.style.width="100%";cv.style.height="100%";cv.style.cursor="crosshair";
      mm.innerHTML="";mm.appendChild(cv);
      mmCtx=cv.getContext("2d");
      cv.addEventListener("click",e=>{
        const p=mmPosToView(e);
        if(!p)return;
        const vw=container.clientWidth||900,vh=container.clientHeight||600;
        ox=vw/2-scale*p.wx;oy=vh/2-scale*p.wy;applyT();
      });
    }
    container.innerHTML="";
    svg=document.createElementNS(NS,"svg");
    svg.setAttribute("id",opts&&opts.id||"tvsvg");
    // 不撑满容器的话 svg 会按 viewBox 宽高比撑出 2000px+ 高的空白滚动区
    // （2026-11-19 树图布局修复）
    svg.style.width="100%";
    svg.style.height="100%";
    svg.style.display="block";
    container.appendChild(svg);
    assignPaths(tree,"root");
    expanded.clear();hl.clear();selPath=null;scale=1;ox=0;oy=0;
    if(tipEl)tipEl.style.display="none";   // 首屏不残留悬浮提示框
    autoFit=true;
    let dragging=false,sx=0,sy=0;
    svg.addEventListener("wheel",e=>{
      e.preventDefault();
      scale=Math.min(3,Math.max(.2,scale*(e.deltaY<0?1.12:.89)));applyT();
    },{passive:false});
    svg.addEventListener("mousedown",e=>{
      if(e.target.closest(".node"))return;
      dragging=true;sx=e.clientX-ox;sy=e.clientY-oy;svg.classList.add("drag");
    });
    window.addEventListener("mousemove",e=>{if(dragging){ox=e.clientX-sx;oy=e.clientY-sy;applyT()}});
    window.addEventListener("mouseup",()=>{dragging=false;svg.classList.remove("drag")});
    if(onRootChange)onRootChange(rootPath());
    svg.addEventListener("dblclick",e=>{
      if(e.target.closest(".node"))return;
      if(anim)cancelAnimationFrame(anim);anim=null;
      scale=1;ox=0;oy=0;applyT();
    });
    render();
  }
  function setTree(t){
    tree=t;
    subRoot=null;
    pathMap.clear();assignPaths(tree,"root");
    expanded.clear();hl.clear();selPath=null;scale=1;ox=0;oy=0;autoFit=true;
    if(svg)render();
    if(onRootChange)onRootChange(rootPath());
  }
  function findParent(node){
    function dfs(n){for(const k of n.ks||[]){if(k===node)return n;const f=dfs(k);if(f)return f}return null}
    return subRoot?dfs(tree):null;
  }
  function rootPath(){
    const parts=[subRoot?subRoot.n:tree.n];
    let p=subRoot?findParent(subRoot):null;
    while(p&&p!==tree){parts.unshift(p.n);p=findParent(p)}
    if(p===tree&&subRoot)parts.unshift(tree.n);
    return parts;
  }
  // 以任意节点为根单独显示子图
  function setRoot(node){
    subRoot=node;
    pathMap.clear();assignPaths(node,"root");
    expanded.clear();
    expanded.add("root");
    if((node.ks||[]).length)expanded.add("root/0");   // 默认展开第一层
    hl.clear();selPath=null;scale=1;ox=0;oy=0;autoFit=true;
    if(svg)render();
    if(onRootChange)onRootChange(rootPath());
  }
  function up(){
    if(!subRoot)return;
    const p=findParent(subRoot);
    if(p)setRoot(p);
  }
  function backToRoot(){if(subRoot)setRoot(tree)}
  // 适应视口: 自动缩放使全图装入屏幕（32 省一屏看全）
  function fitView(){
    if(!container)return;
    const vw=container.clientWidth||900,vh=container.clientHeight||600;
    const ts=Math.min(vw/lastMaxX,vh/lastMaxY);
    const s=Math.min(1.2,Math.max(0.15,ts));
    if(anim)cancelAnimationFrame(anim);
    const fx=ox,fy=oy,fs=scale,t0=performance.now(),dur=260;
    const tx=(vw-s*lastMaxX)/2,ty=(vh-s*lastMaxY)/2;
    function step(t){
      const k=Math.min(1,(t-t0)/dur);
      const e=k<0.5?4*k*k*k:1-Math.pow(-2*k+2,3)/2;
      ox=fx+(tx-fx)*e;oy=fy+(ty-fy)*e;scale=fs+(s-fs)*e;
      applyT();
      if(k<1)anim=requestAnimationFrame(step);else anim=null;
    }
    anim=requestAnimationFrame(step);
  }
  // 小地图: 全图缩略 + 视口框 + 点击定位
  function drawMinimap(){
    if(!mm||!mmCtx)return;
    const W=mm.clientWidth||170,H=mm.clientHeight||110;
    const dpr=window.devicePixelRatio||1;
    if(mmCtx.canvas.width!==W*dpr||mmCtx.canvas.height!==H*dpr){
      mmCtx.canvas.width=W*dpr;mmCtx.canvas.height=H*dpr;
      mmCtx.setTransform(dpr,0,0,dpr,0,0);
    }
    mmCtx.clearRect(0,0,W,H);
    const sx=W/lastMaxX,sy=H/lastMaxY;
    // 节点画实色小块（清晰微型树）
    lastLaid.forEach(d=>{
      const c=d.__col||"#8e44ad";
      mmCtx.fillStyle=c;
      mmCtx.globalAlpha=.85;
      mmCtx.fillRect(d.x*sx,d.y*sy,Math.max(1.2,d.w*sx),Math.max(1.2,NH*sy));
    });
    mmCtx.globalAlpha=1;
    // 视口框
    if(container){
      const vw=container.clientWidth||900,vh=container.clientHeight||600;
      const vx=-ox/scale,vy=-oy/scale,vw2=vw/scale,vh2=vh/scale;
      mmCtx.strokeStyle="rgba(37,99,235,.9)";mmCtx.lineWidth=1.4;
      mmCtx.strokeRect(vx*sx,vy*sy,vw2*sx,vh2*sy);
    }
  }
  function mmPosToView(e){
    if(!mm)return null;
    const r=mm.getBoundingClientRect();
    const W=mm.clientWidth||170,H=mm.clientHeight||110;
    const wx=(e.clientX-r.left)*lastMaxX/W;
    const wy=(e.clientY-r.top)*lastMaxY/H;
    return {wx,wy};
  }
  // 聚焦: 点击位置自动居中（平滑动画）
  function focus(path,targetScale){
    const pos=lastLaid.get(path);
    if(!pos||!container)return;
    if(anim)cancelAnimationFrame(anim);
    const vw=container.clientWidth||900,vh=container.clientHeight||600;
    const ts=Math.min(2.2,Math.max(0.9,targetScale||scale));
    // 节点中心世界坐标 → 视口中心: o = 视口半高 - ts × 世界坐标
    const tx=vw/2-ts*(pos.x+pos.w/2);
    const ty=vh/2-ts*(pos.y+NH/2);
    const fx=ox,fy=oy,fs=scale,t0=performance.now(),dur=280;
    function step(t){
      const k=Math.min(1,(t-t0)/dur);
      const e=k<0.5?4*k*k*k:1-Math.pow(-2*k+2,3)/2;   // easeInOutCubic
      ox=fx+(tx-fx)*e;oy=fy+(ty-fy)*e;scale=fs+(ts-fs)*e;
      applyT();
      if(k<1)anim=requestAnimationFrame(step);else anim=null;
    }
    anim=requestAnimationFrame(step);
  }
  function setExpanded(paths){expanded=new Set(paths);autoFit=true;if(svg)render()}
  function zoom(f){if(anim)cancelAnimationFrame(anim);anim=null;scale=Math.min(3,Math.max(.2,scale*f));applyT()}
  function fit(){if(anim)cancelAnimationFrame(anim);anim=null;scale=1;ox=0;oy=0;applyT()}
  function focusNode(path,ts){focus(path,ts)}
  window.__tvDebug={subH,pathMap,expanded};
  return {mount,setTree,setExpanded,refresh:render,zoom,fit,focus:focusNode,setRoot,up,backToRoot,rootPath,fitView};
})();
