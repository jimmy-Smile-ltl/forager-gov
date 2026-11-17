# 中国政府网站体系（forager-gov）

> 中国政权架构（人民政权机构）官方网站的完整梳理 —— **上下体系、条条块块**。
> 块（行政区划）× 条（垂直系统）双维树形数据，配 **列表 / 树状图 / 地图** 三视图。
> 只收录真实官网（官方页面真实 HTML 提取）；无官网者**列名展示（u=""）**，零猜测。

- **在线站点**：https://forager-gov.pages.dev （Cloudflare Pages）
- **代码仓库**：https://github.com/jimmy-Smile-ltl/forager-gov

---

## 一、项目内容

| 维度 | 说明 |
|---|---|
| 块视图 | 中央 → 省级（31 省区市 + 新疆兵团）→ 地级市 → 区县；每级「人民政府 + 并列机关（党委/人大/政协/监委/法院/检察院/群团）」 |
| 条视图 | 18 个垂直/半垂直系统：人大、政协、法院、检察院、纪委、外交、财经、国务院垂直管理、群团组织、药监、烟草、邮政、铁路、医疗（卫生健康）等 |
| 规模 | 树节点 34,000+（含列名节点）；块条共用网站注册表，一个机构一条记录 |
| 数据源 | 上级机构官网名录栏目 > 同级政府门户导航 > 机构官网互链；SERP 仅作发现线索，必须回官方页面做 title 严格验证并留痕 |

核心数据文件：

| 文件 | 作用 |
|---|---|
| `data/tree.json` | 存库层唯一事实源（块树 + 条树，节点 schema `{n,l,k,c,u,x,s,m,ks}`） |
| `data/site_registry.json` | 网站注册表（主数据：URL / 来源等级 / 健康状态 / 信息公开专栏） |
| `data/extraction_rules.json` | 提取规则（键 = 机构/区划，`method` 留痕来源） |
| `gov_data.js` | 展示层唯一入口 `window.__GOV_DATA__ = {meta, block, tiao, records}`（p22 自动生成） |

> 说明：本项目用于政权架构机构名录与官网入口的整理展示。所有 URL 均来自官方页面
> 真实 HTML；未收录的机构在树中保留名称、官网为空（列名），宁缺毋滥。

---

## 二、URL 覆盖率与缺失率（省 / 市 / 县 × 系统）

「缺失」= 树中该机构**无官网**（`u=""`，列名展示），不代表官网失效——死链状态由
`data/site_registry.json` 巡检 `status` 字段单独承载。统计脚本
`data/p221_url_stats.py`（p22 管线自动调用），完整报告见
[`data/URL_STATS.md`](data/URL_STATS.md)，站点「数据健康」面板同步展示。

### 分等级

| 等级 | 机构数 | 有官网 | 缺失 | 缺失率 |
|---|---:|---:|---:|---:|
| 省级 | 2,252 | 1,913 | 339 | 15.05% |
| 市级 | 12,607 | 11,675 | 932 | 7.39% |
| 县级 | 19,584 | 6,307 | 13,277 | 67.80% |
| **合计** | **34,443** | **19,895** | **14,548** | **42.24%** |

### 分系统 × 等级 缺失率

| 系统 | 省级 | 市级 | 县级 | 合计 |
|---|---:|---:|---:|---:|
| 政府门户 | 0.00% | 0.25% | 2.65% | 2.33% |
| 政府部门（厅局 / 市局） | 0.16% | 0.00% | — | 0.02% |
| 人大 | 0.00% | 22.47% | 98.13% | 87.65% |
| 政协 | 0.00% | 40.00% | 98.52% | 90.20% |
| 监委 / 纪委 | 0.00% | 31.36% | 93.67% | 84.91% |
| 法院 | 0.00% | 12.84% | 28.97% | 26.66% |
| 检察院 | 0.00% | 23.21% | 55.70% | 51.07% |
| 党委 | 100.00% | 100.00% | 100.00% | 100.00% |
| 群团 | 45.04% | 0.00% | — | 33.89% |
| 民主党派 | 24.70% | — | — | 24.70% |

> 读法：缺口的绝大多数是**体制性无官网**，不是采集未完成——党委机关不单设门户
> 网站（故 100%）；县级人大 / 政协 / 监委极少建站（区县一级多由本级党委政府
> 门户代管栏目）；市级政协、纪委建站率天然低于法院系统。政府门户与政府部门
> 已基本全覆盖（缺失率 ≤2.65%）。每个缺口节点的 `m` 字段留有具体原因留痕。

---

## 三、仓库结构

```
├── 中国政府网站体系.html      # 主查看器（列表 / 树状图 / 地图）
├── gov-tree.html              # 树图 + 地图专用查看器
├── 模板.html                  # 主查看器模板（数据管线复制为上面的成品）
├── map_view.js / tree_view.js # 地图 / 树图视图（纯手写，无外部依赖）
├── gov_data.js                # 统一数据（p22 生成）
├── data_js/                   # 拆分后的数据模块（manifest / modules / rules / quality）
├── data/
│   ├── tree.json              # 事实源（块 + 条）
│   ├── site_registry.json     # 网站注册表
│   ├── extraction_rules.json  # 提取规则
│   ├── geo/                   # 行政区划边界（DataV + taiwan-atlas，惰性加载）
│   ├── URL_STATS.md           # URL 缺失率统计报告（p221 生成：省/市/县 × 系统）
│   ├── p*_*.py                # 采集 / 治理 / 管线脚本（274 个，见 data/INDEX.md）
│   └── INDEX.md               # 脚本索引
├── util/                      # 通用工具（获取层实现不随本仓库发布，见「数据来源与红线」）
├── 体系设计.md                # 架构、数据模型、权威源体系、采集纪律
├── CLAUDE.md                  # 项目内部规则（本地维护，不随仓库发布）
└── 政府信息公开官网名单.csv    # 早期导出名单
```

---

## 四、本地预览

站点是**纯静态**的，无构建依赖：

```bash
python3 -m http.server 8765
# 打开 http://localhost:8765/中国政府网站体系.html
#      http://localhost:8765/gov-tree.html
```

也可以用任意静态服务器；直接双击 HTML（`file://`）同样可用——数据按需以 `<script>` 惰性加载。

---

## 五、数据管线（每次数据改动必跑）

```bash
# 1. 拆分数据 + 生成三视图数据（p22 内部自动调用 gen_viz）
cd data && uv run python p22_split_data.py && cd ..

# 2. 重建主查看器
cp 模板.html 中国政府网站体系.html

# 3. 自检（必须 0 问题项）
uv run python data/p99_weekend_check.py

# 4. 构建发布包（可选，本地验证）
cd data && uv run python p219_build_dist.py && cd ..
```

---

## 六、部署（Cloudflare Pages）

**方式 A：关联 GitHub 仓库（推荐，push 即发布）**

Cloudflare Dashboard → Workers & Pages → Create → Pages → Connect to Git →
选择 `jimmy-Smile-ltl/forager-gov`，构建设置：

| 设置项 | 值 |
|---|---|
| Production branch | `main` |
| Build command | `python3 data/p219_build_dist.py` |
| Build output directory | `dist` |
| Root directory | `/` |

`p219_build_dist.py` 只用 Python 标准库，无需安装依赖。每次 `git push` 自动构建发布。

**方式 B：本地构建 + 直传**

```bash
npx wrangler login                          # 首次
cd data && uv run python p219_build_dist.py # 生成 dist/
npx wrangler pages deploy dist --project-name=forager-gov
```

发布包只含站点运行所需资产（两 HTML + 视图脚本 + gov_data.js + data_js + data/geo），
采集脚本、state、快照、备份一律不进发布包；`p219` 自带引用完整性、Pages 限额
（单文件 25MiB / 20000 文件）与泄漏三道校验。

---

## 七、数据来源与红线

- **禁止猜测域名**：不做拼音/缩写探测、DNS 试探或「能响应就算官网」；所有 URL 来自官方页面真实 HTML。
- **无官网列名**：`u=""` 展示名称，不降级保留探测数据。
- **SERP 仅作线索**：搜索引擎结果必须回到官方页面做标题身份验证，并在 `s` 字段留痕。
- **获取层抽象**：脚本统一调用 `smart_fetch(url)` 获取真实 HTML；获取层实现
  （浏览器/指纹/WAF 处理）不随本仓库发布。
- **不发布内容**：`.env`、cookies、`*_state.json`、snapshots、backups、dist、
  内部规则文档 CLAUDE.md。
- 数据来自各级政府公开网站，仅作机构名录与官网入口整理；如发现错漏，欢迎提 issue。

---

## 附录：地图子系统

本文档说明「中国政府网站体系」中行政区划地图（`gov-tree.html` / `中国政府网站体系.html` 的 🗺 地图视图）的 **Geo 数据来源** 与 **绘制方法**。

### 一、Geo 数据来源

地图底图使用本地化的行政区划边界数据（`data/geo/`，共 360+ 文件约 27MB），**不依赖任何运行时外链**。数据来源分两类：

#### 1. 阿里云 DataV GeoAtlas（主源，全国大陆 + 港澳）

- **地址**：`https://geo.datav.aliyun.com/areas_v3/bound/{adcode}(_full).json`
  - `{adcode}.json`：该区划**自身**的边界
  - `{adcode}_full.json`：该区划**及其全部下级**的边界集合（我们主要用这个）
- **坐标系**：GCJ-02（火星坐标，大陆范围），字段为经纬度
- **下载打包**（`data/dl_geo.py`，断点续跑、幂等）：
  | 产物 | 来源 | 内容 |
  |---|---|---|
  | `geo/china.js` | `100000_full.json` | 全国省界（35 省级特征，含港澳台省界） |
  | `geo/geo_{省}0000.js` | 各省 `_full.json` 的市级特征 | 省图 = 市级图（点省下钻显示） |
  | `geo/geo_{市}00.js` | 各市 `_full.json` 的县级特征 | 市图 = 县级图（点市下钻显示） |
  | `geo/geo_810000.js` / `geo_820000.js` | 港澳 `_full.json` | 香港 18 区 / 澳门 8 堂区（三级变两级） |
  | `geo/geo_index.js` | 由磁盘文件反查生成 | `__GEO_CITY_FILES__` 市级下钻清单（有县级文件的市级 adcode） |

- **特例处理**：
  - **直辖市**（北京/天津/上海/重庆）：省下无市级层，`geo_{直辖市}0000.js` 直接存区县（三级变两级）
  - **台湾**：DataV 无县市边界（`710000` 的 `childrenNum=0`）→ 见下文第 2 类
  - **嘉峪关市 / 新疆兵团市**：DataV 无县级边界文件（404 为正常）→ 不在 `geo_index.js` 清单，点击直接看详情
  - **海南省三沙市**：geo 文件含南海诸岛（南至北纬 3.8°），主图范围扫描时跳过，单独画右下角「南海诸岛」插图

#### 2. taiwan-atlas（台湾 22 县市）

- **仓库**：`github.com/dkaoster/taiwan-atlas`（MIT）
- **原始数据**：台湾内政部开放资料「直辖市、县市界线（TWD97 经纬度）」，经该仓库转档为 TopoJSON
- **下载**：`https://cdn.jsdelivr.net/npm/taiwan-atlas/counties-10t.json`
- **转换**（`data/p197_taiwan_geo.py`，已挂入 dl_geo.py）：
  1. TopoJSON 解码：`transform.scale/translate` 量化还原 + delta 编码弧线解码 → 绝对经纬度
  2. **繁体转简体**（縣→县、臺→台、連→连、嘉義→嘉义……22 县市名全量映射）
  3. **一个中国原则**：台湾省保持挂在全国省界下，点击下钻 22 县市（含金门县/连江县，与块树结构一致），不单独成图；文件头注释数据来源
  4. adcode 稳定表（710100 台北市起）；bbox 中心作为标注锚点
- **坐标说明**：TWD97 与 WGS84 差异 <1 米，直接并入经纬度投影，无纠偏

#### 3. 加载方式（file:// 兼容）

- 每个 geo 文件打包为 `window.__GEO_{adcode}__ = {FeatureCollection}` 的 `<script>`，地图**按需惰性加载**（`<script src>` 动态插入）——因为 `file://` 下 `fetch()` 被 CORS 拦截，不能用 AJAX
- 结构（与 DataV 一致）：`features[].properties = {adcode, name, center, centroid}`，`geometry = Polygon / MultiPolygon`

### 二、绘制地图的方法

地图由 `map_view.js`（MapViz，约 700 行）**纯手写 SVG** 绘制，无 ECharts/D3 依赖（规避 CSP 与外链限制），两个查看器共用同一份代码。

#### 1. 投影：等距圆柱投影

```js
// project(features[0]) 按当前 range（全国/省/市各自适配）计算：
// 容器宽高 W×H，经纬范围 [minLon,maxLon]×[minLat,maxLat]
k = min(W/(maxLon-minLon), H/(maxLat-minLat)) * 0.94   // 保持纵横比居中
x = ox0 + (lon - minLon) * k
y = oy0 + (maxLat - lat) * k                            // 北在上
```

下钻时 `setGeo(adcode)` 用该省/市特征的**边界框**重算 range → 每级地图自动满幅适配。

#### 2. 几何：Polygon / MultiPolygon → SVG path

`pathOf(geom, pr)`：Polygon 逐 ring、MultiPolygon 多解一层（曾因少解一层出现 `MNaN,NaNZ`），每环 `M…L…Z` 闭合。

#### 3. 渲染分层（render()）

```
svg
├── defs    渐变定义: 每区划独立色 + 灰态 + 海洋径向暗角渐变
├── rect    海洋背景（径向渐变: 中心亮、四角暗 = vignette）
├── g       经纬网氛围线（10° 一格, 6-7% 透明度, 静态不随缩放）
├── rootG   陆地组（变换目标: translate+scale 应用于此组, 海洋/网格不动）
│   ├── g.mz × N   每区划一组: path(填充/描边)
├── labelG  地名标注层（最后挂载，保证不被多边形覆盖）
└── [插图]  南海诸岛（三沙市）右下角小框（drawInset, 独立小投影）
```

#### 4. 着色管道（五步）

1. **深聚合统计** `calcStats(t)`：块树 DFS——每个区划节点递归整棵子树，按机构类型统计「有官网/总数」（省=全省辖域、市=全市、县=全县）；兼容省级节点 `t="group"` 挂 u、直辖市辖区 `c=直辖市辖区` 等形态
2. **取值** `covOf(name)`：当前类型覆盖率；名称经 `baseName` 归一（剥行政区后缀+民族修饰+「（…）」尾注）——geo 特征名、树节点名、官网简称三方互通
3. **每区划独立色**：有数据的区划按覆盖率升序 × 黄金角（137.508°）在色环展开，相邻覆盖率色距恒定；灰 = 无官网/无机构（5 套配色方案可在图例切换）
4. **末级降级**：区县级单类型数据天然二元（每县该类型机构仅 1 个, 有/无）→ 无差异可显时自动改按**综合覆盖**着色（`fillCache`），tooltip/详情仍显示该类型真实值（`covCache` 分离）
5. **填色** `colorOf`：按区划取调色板颜色；hover/选中另加描边与光晕

#### 5. 交互

| 交互 | 实现 |
|---|---|
| 三级下钻 | 全国省界 → 点省看市级 → 点市看县级（`CITY_FILES` 清单裁决：无县级文件的区划点击直接出详情）；点县出右侧档案卡 |
| 深链直达 | `MapViz.goTo(prov, city, type)`——按名（基底名匹配）找特征 → geo 异步加载链式下钻（URL hash 书签用） |
| 滚轮缩放 | `zoomAt(cx, cy, f)` 焦点缩放：`o' = p − (p−o)×k`，光标下内容点缩放前后不动 |
| 拖拽平移 | mousedown/mousemove；`clampT` 边界钳制——放大后不许整图滑出视口 |
| hover | 金色描边 + 浮层「名称 · 覆盖率% · 点击下钻/看详情」 |
| 选中 | 琥珀金描边 + 光晕（drop-shadow） |
| 切换 | 层级/类型切换时陆地组 0.45s 淡入；机构类型按钮重着色 |
| 返回 | `back()`：市→省→全国；面包屑实时跟随 |

#### 6. 地名标注（labelOf + 防重叠）

- **归一缩略**：剥行政区后缀 + 民族修饰循环剥离 + 兜底截断（木里藏族自治县→木里、伊犁哈萨克自治州→伊犁、塔什库尔干塔吉克自治县→塔什库尔干）
- **防重叠**：按区域面积降序放置 → 包围盒碰撞检测 → 碰撞时逐级缩小字号（−2.5px）+ 多组偏移候选，全失败才省略；长名拆两行；面积过小不标名（hover 浮层兜底）
- 白描边 halo（海洋色）保证深浅背景可读；`pointer-events:none` 不挡点击

#### 7. 主题（白天/夜晚双套）

- `readTheme()`：读宿主页 `--bg`/`--ground` 亮度判定（3 位 hex 缩写须展开，曾因 `parseInt("fff")=4095` 误判成暗色）
- 深浅两套调色板（白天明亮鲜润、夜晚温润低亮）+ 海洋/描边/标注色全部随主题
- 联动：`MutationObserver(data-theme)` + `matchMedia(prefers-color-scheme)` → 自动重绘；页面顶栏 🌙/☀️ 一键切换

#### 8. 数据流总览

```
tree.json（块树: 区划×机构  /  条树: 垂直系统）
  → data/gen_viz.py 重组（节点 schema {n,u,t,m,ks}）
  → gov_data.js（window.__GOV_DATA__ = {meta, block, tiao, records}）
  → MapViz.mount(容器, __TREE__/__TIAO__, {onSelect, onRegion, onLevel})
      + data/geo/*.js 惰性加载 → SVG 渲染
```

数据更新后：跑 `data/p22_split_data.py`（自动调用 gen_viz）即刷新树图/列表/地图三视图，无需手工维护。

### 附：相关文件索引

| 文件 | 作用 |
|---|---|
| `map_view.js` | 地图视图（投影/渲染/着色/交互/标注/主题/深链） |
| `data/dl_geo.py` | DataV + 港澳 + 台湾（挂 p197）边界下载打包, 断点续跑 |
| `data/p197_taiwan_geo.py` | 台湾 22 县市 TopoJSON 解码 + 繁转简 + 生成 geo_710000.js |
| `data/geo/china.js` | 全国省界 |
| `data/geo/geo_{adcode}.js` | 省→市 / 市→县 / 港澳区堂区 / 台湾县市 边界 |
| `data/geo/geo_index.js` | 市级下钻清单 `__GEO_CITY_FILES__` |
| `data/gen_viz.py` | 块/条树重组 + records 生成（p22 自动调用） |
| `tree_view.js` | 树状图视图（与地图同源数据） |
