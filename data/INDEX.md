# 提取规则脚本索引

共 295 个脚本（data/*.py）。编号 p0-p242 = 开发顺序。
按主题分类，查找某板块的处理脚本直接看对应组；p116-p200 为中期批次，见文末概览。

## 中央/并列机关（11）
- `p1_central_province.py` — 中央部委 + 省级政府 信息公开专栏 URL 解析。
- `p1d_finalize.py` — 中央/省级剩余站点最终落定（百度检索路径 + 挂靠母体 + 标准路径推断）。
- `p23_gen_central_rule.py` — v2: 生成「中央」完整提取规则。
- `p25_gen_all_central_rules.py` — 中央模块内全部分组节点的提取规则补齐。
- `p27_gen_par_org_rules.py` — 省级并列机关提取规则补齐。
- `p31_complete_central.py` — 中央政权架构完整性补缺（对照中央编办口径审计结果）。
- `p32_gen_central_supplement.py` — 为 P31 新增的中央板块生成提取规则。
- `p34_par_quntuan_render.py` — 省级群团链接浏览器渲染补采（周末收尾阶段用）。
- `p35_baidu_quntuan.py` — 省级群团官网百度 SERP 挖掘 + 连通性验证。
- `p37_verify_titles.py` — 群团命中 URL 标题验证 —— 防 SERP 挖掘误配。
- `p38_render_verify.py` — 群团「待核」URL 浏览器渲染验证（p37 的 JS 渲染补充）。
- `p252_quntuan_names.py` — **群团节点命名规范化**（2026-11-19）：块视图 16 个槽位 × 32 省一律是泛化名（「北京市 › 群团组织（17）› 省总工会」「团省委」），列表模式单行显示成「省总工会」；条视图团委是倒装名「北京市共青团委员会」、欧美同学会子节点只有裸地名。统一为全名（「北京市总工会」「共青团北京市委员会」「上海市欧美同学会」），并迁移 registry 主键——旧键 `群团|团省委` 被 31 省共用，后 30 省的团委 URL 全部丢失，改名后按省重建。`--dry` 干跑。
- `p254_quntuan_url_audit.py` — **群团 URL 树/registry 冲突复核**（2026-11-19）：两处展示的 URL 跨主域不一致共 12 条（山西省台联→浙江台联、湖南省作协→浙江作家网、云南/宁夏作协→chinawriter 文章页…）。两个候选都取真实标题判定（须含机构核心词 + 本省名、非新闻文章路径），仅单侧通过才改，两可不动列「待人工」。实测 8 条收敛（5 tree / 2 registry / 1 同站），4 条待人工。`--dry` 干跑。
- `p255_quntuan_rule_keys.py` — **群团工会命名补全 + 规则键迁移**（2026-11-19，承接 p252/p253）：① 修 p252 回归——省级群团改名后 `extraction_rules` 仍是旧键「北京市·省总工会」，544 个节点的「提取规则」页签全部消失，按新名反推旧槽位名迁移键/depts/docstring；② 市/区工会裸名「市总工会」「区总工会」（139+40）改为「{父级名}总工会」并迁移规则键；③ 晋城/淮安/嘉兴/潍坊/安康 名录里重复的「市总工会」——4 市删除重复（群团侧已有同名同 URL 节点）、淮安移入市级群团，清掉 6 个错误 registry 键。`--dry` 干跑。

## 人大（14）
- `p24_gen_child_rules.py` — 生成中央各子节点的提取规则（中共中央/国务院/人大/政协/监委/最高法/最高检）。
- `p59_rdzx_systems.py` — 构建 人大系统 + 政协系统 两条垂直系统模块。
- `p74_rd_authoritative.py` — 人大系统权威化重建（中国人大网「地方人大网站」页真实 HTML）。
- `p75_rd_shi.py` — 市级/区级人大提取（省人大官网「各区人大/市县人大」区块）。
- `p78_rd_mount.py` — 人大系统市级/区级挂载（含列名展示）+ 老系统回填。
- `p82_probe.py` — 探测：dump 福建/陕西/黑龙江/辽宁/重庆 人大页面渲染后 HTML 供结构分析。
- `p83_rd_shi_fix.py` — 补 6 省市级人大（福建/陕西/黑龙江/辽宁/青海/重庆）→ rd_shi.jsonl。
- `p84_rd_rules_sync.py` — 人大系统 rules depts 同步市级挂载 + method 更新。
- `p85_hb_rd.py` — 河北市级人大（hbrd.gov.cn 首页 select 下拉，真实 HTML）。
- `p86_js_rd.py` — 江苏市级人大（jsrd.gov.cn 首页「dis」区块，真实 HTML 验证）。
- `p87_render.py` — 批量渲染 12 省人大官网（CDP 9334），保存渲染后 HTML。
- `p88_zj_api.py` — 浙江 XHR 监听抓市县人大数据 API。
- `p89_rd_batch.py` — 批量补 12 省市级人大（真实 HTML/官网 JS 配置提取）。
- `p90_tj_rd.py` — 天津区人大（tjrd.gov.cn 首页「区人大」区块，真实 HTML）。

## 其他（31）
- `common.py` — 公共抓取模块：fetch 工具 + save_snap/save_snap_bin 页面快照（证据留痕，snapshots/ 目录）。
- `p100b_probe.py` — 内蒙古点击后 dump ul-link 内容。
- `p103b.py` — 江苏点击后 dump links 容器 HTML。
- `p103c.py` — 江苏 links 容器完整 dump。
- `p10_gen_tree.py` — v2: 生成政府信息公开体系树形数据（兵团/港澳台补齐、直辖市级别严谨化）。
- `p1c_retry.py` — p1c: WAF 站点多指纹重试 + 本地导航解析，输出命中结果。
- `p26_gen_gat_rules.py` — 生成港澳台板块的提取规则（组 / 香港 / 澳门 / 台湾）。
- `p36_sample_check.py` — 抽查连通性复验（GET，-L 跟随重定向）。
- `p46_vertical_systems.py` — 垂直管理系统（条条）机构站点采集。
- `p47_build_tiao_tree.py` — 构建「条（垂直管理系统）」视图树 + 规则。
- `p4b2_final.py` — 2: 终版合并 + 增量解析。
- `p52_tobacco_official.py` — 从国家烟草专卖局官网导航提取下属单位（真实 HTML 提取，合规）。
- `p54_tobacco_city.py` — 烟草系统市级细化 —— 省局官网城市子站链接提取（真实 HTML）。
- `p55_apply_tobacco_city.py` — 烟草市级子站回填条模块（省局网站栏目真实 HTML 提取）。
- `p5_merge.py` — 合并产出最终 CSV（全量名单 + 官网名单）。
- `p62b_gy_sequential.py` — 高院页面顺序遍历提取（天津 areamap / 北京 tit_a·tit_b 通用）。
- `p62d_render_courts.py` — 缺失省高院/中院浏览器渲染补采（JS 渲染导航）。
- `p62i_hn_jx.py` — 湖南渲染 tab 模式 + 江西中院子站基层爬取。
- `p62j_last4.py` — 最后四省补全（西藏/兵团站点群页、湖北 API 列表页、宁夏官方群区块）。
- `p6_browser_fix.py` — WAF/JS 站点信息公开专栏浏览器修复（独立 Chromium，符合浏览器隔离铁律）。
- `p6b_browser_fix2.py` — 浏览器修复 v2 —— 长等待 + 每站点候选路径直连 + 残留链接 dump。
- `p88_interact.py` — 交互提取——安徽 tab、浙江折叠面板、宁夏 tab、西藏 /dxrd。
- `p88_interact2.py` — 2: 交互提取——安徽 tab 内容区、浙江折叠展开、宁夏 tab。
- `p88_interact3.py` — 3: 交互提取——安徽 tab、浙江折叠、宁夏 tab（JS 点击）。
- `p88_interact4.py` — 4: 真实点击交互（scroll.to_see + click）。
- `p8_repair.py` — 修复错配行（zwfw 政务服务网错配 + 海淀/成都特例）。
- `p9a_smart_fetch.py` — 用 util 的 smart_fetch 补齐
- `p9e_repair_v3.py` — 修复坏 xxgk（文章页误配）+ 二次解析剩余无 xxgk 行（article 过滤版）。
- `p9f_repair_all.py` — 修复坏 xxgk（文章页误配）+ 二次解析剩余无 xxgk 行（article 过滤版）。
- `p9g_pinyin.py` — 拼音候选 + smart_fetch 验证（pypinyin 缺失修复版）。
- `search_bing.py` — search_bing: 本地抓取 cn.bing.com 搜索结果，返回 (标题, cite路径, 直达URL) 列表。

## 区划/民政部（3）
- `p0_divisions.py` — 行政区划数据扁平化（v2）。
- `p12_mca_sync.py` — v2: 民政部区划同步（修正版：滤自引用行、直辖市辖区为地级层级）。
- `p12b_apply_codes.py` — 把民政部 6 位区划代码写回 divisions.json / city_county_final.jsonl，

## 厅局/门户（21）
- `p11_fix_depts.py` — 厅局修正 —— 清中央残留 + smart_fetch 补采缺厅局的省。
- `p11b_fix_depts2.py` — 厅局修正第二弹 —— 清洗误采 + 针对 北京/广东/湖南/上海/天津/重庆 定向补采。
- `p11c_fix_depts3.py` — 厅局补采第三弹 —— 首页导航发现「省直单位网站」页再提取。
- `p13_reattribute.py` — 省厅局从属关系全面重检 —— 以 URL 域名结构判定所属省份。
- `p14_cloak_depts.py` — smart_fetch(url) 渲染提取，抓 山东/湖北/安徽 部门列表页。
- `p15_depts_full.py` — 省级政府直属厅局全量重采 —— 从各省门户首页底部「部门网站」导航模块提取。
- `p16_browser_footer.py` — 浏览器渲染版厅局重采 —— 从渲染后首页的「部门网站」容器整体提取。
- `p20_order.py` — v2: 官网原始顺序采集（按与已有厅局清单匹配度选容器，URL 优先匹配）。
- `p21_gen_rules.py` — 生成各省「提取规则」元数据（方法/来源页/样例部门/样例市州）。
- `p28_gen_dept_rules.py` — 省政府部门（厅局组）提取规则补齐 —— 每省 1 条，提取结果为该省全部厅局（官网原始顺序）。
- `p2_prov_depts.py` — 省厅局（省政府组成部门/直属机构）名单 + 门户 + 信息公开专栏 URL。
- `p30_gen_cc_rules.py` — 市县并列机关组规则 + 县直部门（省政务服务网 deptSwitch）规则生成。
- `p3_city_county.py` — 市/县门户 URL 链式解析。
- `p3b_fallback.py` — 未匹配市/县门户兜底解析（重试父级 → 拼音域名探测 → Bing 搜索）。
- `p3c_fallback2.py` — 兜底第 2 轮 —— 对 p3b 后仍缺门户的市/县，强化查询策略。
- `p4_cc_xxgk.py` — 市/县门户的信息公开专栏 URL 解析。
- `p4b_xxgk_fix.py` — xxgk 增量补 —— 对 p4 未命中的行（含 p3c 后新填门户的行）再解析。
- `p7_browser_final.py` — 剩余真实市/县门户的浏览器终轮解析（含 xxgk）。
- `p9b_smart_chain.py` — 用 smart_fetch 补齐「无门户」的真实区县（链式重抓）。
- `p9c_dead_domain.py` — 死域名门户清理（p9a 后仍无 xxgk 且 DNS 解析失败的行 → 清门户重排队）。
- `p9d_retry_v2.py` — 用 smart_fetch + find_xxgk_links v2 二次补齐「有门户无xxgk」行。

## 工会（8）
- `p33_gen_prov_quntuan.py` — 省级群团组织板块（省总工会/团省委/省妇联…）。
- `p43_union_collect.py` — 工会系统隶属链采集 —— 省级工会官网 → 市级工会。
- `p44_union_render.py` — 省级工会官网浏览器渲染补采市级工会（p43 的 JS 渲染补充）。
- `p45_build_union_module.py` — 建「工会系统」模块 + 回填老系统。
- `p48_union_authoritative.py` — 省级工会 URL 权威化（来源：全总官网「省级工会」栏目，用户提供完整名单）。
- `p49_union_city_render2.py` — 用权威省级工会 URL 重新渲染补采市级/区级工会。
- `p50_apply_union2.py` — p49 渲染提取的市级/区级工会回填（真实 HTML 来源）。
- `p50b_cleanup_strict.py` — 工会市/区级数据严格化。
- `p253_union_tiao.py` — **条视图「工会系统」重建**（2026-11-19）：p45 的根级模块内容早已丢失，条 › 群团组织系统 下只剩空占位「工会系统」，前端 CROSS_MAP 仍指向旧名「工会系统（中华全国总工会）」，块视图点全总→条视图静默不动。用现有 tree 数据重建（不新采）：全总 + 省级工会 32/32 + 市级工会 142，组名「工会系统（32）」，registry 只补 n/locations 不改 URL；前端 CROSS_MAP 与 ruleKeyOf 同步改名。

## 应急管理（1）
- `p81_mem_orgs.py` — 应急管理部内设机构补全（mem.gov.cn/jg/ 真实 HTML）。

## 探测/清理（5）
- `p1b_fix.py` — 修复 P1 未命中的信息公开 URL（v2 链接识别 + 多路径探测 + 多指纹重试）。
- `p51_annotate_probed.py` — 存量域名探测数据降级标注（配合「禁止猜测域名」铁律）。
- `p62g_scan_courts.py` — 通用站内扫描——高院首页全部站内链接逐个探测，找含「中院」≥3 的
- `p66_purge_probed.py` — 拼音探测数据全面清除（用户明令：绝对不认可拼音）。
- `p88_probe.py` — probe: dump 安徽点击后 tab 区 + 浙江点击后折叠区 DOM。

## 政协（12）
- `p100_zx_interact.py` — 政协交互提取——点击「市县政协/设区市政协/盟市政协」按钮切换列表。
- `p100c_zx_full.py` — 政协交互提取 v2——点击后匹配纯地名链接（不要求含政协字样）。
- `p101_zx_merge.py` — 政协交互提取结果合并入 rd_zx.jsonl（内蒙古/山东/湖南/贵州）。
- `p102_zx_probe2.py` — 剩余省政协交互 probe——点击后保存 HTML 离线分析。
- `p103_js_final.py` — 江苏真实点击 linkBtn-item 抓市级政协。
- `p104_zx_merge2.py` — 政协第二轮合并（江苏/河南/江西/海南 简称与编码修正提取）。
- `p73_zx_authoritative.py` — 政协系统权威化重建（全国政协官网「地方政协」块真实 HTML）。
- `p91_zx_probe.py` — 批量静态抓 31 省政协官网首页。
- `p92_zx_render.py` — CDP 渲染无命中省政协首页。
- `p93_zx_columns.py` — 抓省政协官网「市县政协」栏目页。
- `p94_zx_batch.py` — 政协市级数据汇总 → rd_zx.jsonl。
- `p95_zx_mount.py` — 政协市级挂载（政协系统条模块 + 老系统回填）。仿 p78。

## 数据管线（12）
- `site_contract.py` — 补采统一写库契约（2026-11-17）：五系统标准 registry 键 `<类别>|<全名>`（人大|城市人大 / 政协|城市政协 / 法院|城市中级人民法院 / 检察|城市人民检察院 / 纪委|城市监委）、`five_key`/`five_name`/`parse_five`/`base`、`source_level`（L1>L2>L3 只升不降）与 `upsert_registry`（合并 locations、保留 xxgk/snapshot）。所有补采脚本必须经它写 registry，禁止手拼键。
- `p222_registry_contract_fix.py` — registry 写库契约迁移与校验：历史脏键归一（`法院|市人大|石家庄市`、`人大|北京市` 等）、重复条目合并、树有 URL 而 registry 缺记录时补登、已审计无官网的旧 URL 不复活、canonical 条目与树 URL 对齐。`--check` 输出硬问题（tree-url-no-registry / url-mismatch / malformed-key），必须 0 才可发布。
- `p221_url_stats.py` — URL 缺失率统计（省/市/县 × 政府/人大/政协/纪委/法院/检察/党委/群团/民主党派…）：块视图省级子树逐机构统计 u 是否为空，输出 `data/url_stats.json` + `data/URL_STATS.md`，并把结果嵌进 `data_js/quality.js`（站点「数据健康」面板消费）；p22 管线自动调用。
- `p220_dead_link_fix.py` — 死域名清理 + 错挂修正：整站下线/迁域的存量 URL（DNS NXDOMAIN）替换或列名，衡阳县/濮阳中院错挂修复，同步 registry（写前备份）。
- `p22_split_data.py` — 把 tree.json / extraction_rules.json 拆分为模块化数据文件（自动调用 gen_viz）。
- `p219_build_dist.py` — 站点发布包构建：只拷 HTML/视图脚本 + gov_data.js + data_js + data/geo 到 dist/，校验引用完整性、Cloudflare Pages 限额（单文件 25MiB/20000 文件）与泄漏（不含 .py/.json/state）；纯标准库，可直接作为 Pages 构建命令。另生成 `dist/_headers`（geo 一年 immutable、data_js 1h、脚本 1 天）与**省级县界包** `data/geo/geo_bundle_{省码}.js`（一省全部市级边界合并，27 省 21.6MB，仅入发布包）——省图打开后预取，点市下钻零请求，对慢网/高 RTT 环境是省→市等待的根治手段。
- `gen_viz.py` — 可视化数据生成：tree.json → gov_data.js（block/tiao/records）。
- `dl_geo.py` — 行政区划边界下载打包（DataV GeoAtlas + 港澳 + 台湾 p197），断点续跑。
- `backup_now.py` — 数据快照：tree/rules/registry 备份到 backups/<日期>/。
- `declarative.py` — 声明式采集框架（YAML 配置驱动，自动快照 + registry 登记）。
- `p53_tobacco_rebuild.py` — 烟草系统模块重建（总局官网导航真实 HTML 提取，替换拼音探测数据）。
- `p56_railway_rebuild.py` — 铁路系统模块重建 —— 政府侧 + 企业侧（全部真实 HTML 提取）。

## 检察院（19）
- `p105_jc_scan.py` — 检察院基层批量扫描——静态轮 186 个市级院官网。
- `p106_jc_audit.py` — 市级检察院 URL 审计——连通性 + title 身份验证。
- `p107_jc_verify.py` — CDP 渲染复核可疑市级检察院 URL。
- `p108_prov_jc.py` — CDP 渲染广东/广西/湖南省检察院官网，找市级院权威导航。
- `p109_hn_jc.py` — 湖南检察院全量挂载（省院 szylj 频道页真实 HTML）。
- `p109b_hn_rebuild.py` — 湖南检察节点从零重建（省院 szylj 栏目数据）。
- `p110_jc_mount.py` — 挂载 p105 静态轮基层检察院记录到检察系统 + 老系统回填。
- `p111_jc_render.py` — CDP 渲染轮——0 命中的 189 个市院官网提取基层检察院。断点续跑。
- `p112_s12309.py` — 12309 检察地图探测（CDP 渲染 + 网络监听找 API）。
- `p40_jcy_pinyin.py` — 市县检察院 pinyin.jcy.gov.cn 域名探测回填。
- `p42_prov_fyjc.py` — 省级高院/检察院门户拼音模式补齐。
- `p64a_jc_probe.py` — 检察院系统细化 —— 省检察院官网渲染 + 站内扫描找市级院列表页；
- `p64b_jc_jiceng.py` — 检察院基层院提取。
- `p65_build_jc_tree.py` — 检察院系统树重建 + 老系统回填。
- `p67_jc_shi.py` — 省检察院官网「市州分院」区块提取市级检察院（纯市名 anchor 模式）。
- `p68_build_jc_tree2.py` — 检察院系统树重建（真实 HTML 来源）+ 老系统回填。
- `p69_jc_authoritative.py` — 省级检察院 URL 权威化（最高检官网「全国检察院门户网站」区块）。
- `p70_jc_v3.py` — 检察院市级院提取 v3 —— gzip 解压 + 「XX市院/分院」文本模式 +
- `p71_jc_select.py` — 检察院「省内链接」select 下拉模式提取（江西式）。

## 民主党派（4）
- `p113_dp_mount.py` — 民主党派省级组织挂载（民盟/民建/民进/农工/致公/九三 + 九三市级）。
- `p114_mg_tm.py` — CDP 渲染民革/台盟官网找省级组织导航。
- `p115_mg_tm_mount.py` — 民革省级挂载（24 有官网）+ 台盟省级全列名 + rules 同步。
- `p251_rename_parties.py` — **省级组织改名**（2026-11-19）：p113/p115 原先生成「{省名}{党派}省委会」（「北京市民革省委会」——语序反了，直辖市/自治区还带「省」字）。统一为「{简称}{省名}委员会」（民革北京市委员会 / 九三学社浙江省委员会），同步 tree.json、site_registry.json 主键与 n、extraction_rules depts、xxgk_remainder；`--dry` 干跑。

## 法院（11）
- `p18_parallel.py` — 省级并列机关（人大/政协/监委/法院/检察院）门户 URL 采集。
- `p29_collect_cc_parallel.py` — 县/市 并列机关门户采集（人大/政协/监委/法院/检察院）。
- `p39_court_links.py` — 县级法院/检察院门户补全（用户终止条件核心）。
- `p41_court_pinyin.py` — 法院门户拼音域名探测回填（中院/基层院）。
- `p57_court_proc_systems.py` — 构建 法院系统 + 检察院系统 两条垂直系统模块。
- `p62_court_hierarchy.py` — 法院系统三级层级爬取（真实 HTML 提取，合规）。
- `p62c_court_unified.py` — 法院层级统一爬取（整合 p62/p62b，修复 option 空格写法与明文 elid）。
- `p62e_tab_courts.py` — 法院网「tab+section」模式提取（辽宁式：中院 tab=纯城市名，
- `p62f_list_courts.py` — 法院「专页列表」模式提取（黑龙江 qsfy.php 式：全称列表，
- `p62h_jx_gs_hn.py` — 江西站点群专页 + 甘肃法院网群下拉 + 湖南 tab 模式。
- `p63_build_court_tree.py` — 法院系统三级树构建 + 老系统回填（合规 HTML 提取数据）。

## 纪委（4）
- `p77_jw_system.py` — 纪委系统（纪检监察）条模块构建 —— 基于块数据映射。
- `p96_jw_render.py` — CDP 渲染 13 省纪委监委官网。
- `p97_ccdi_render.py` — CDP 渲染 ccdi 首页 + 地方纪委监委机构页（验证码需浏览器）。
- `p98_jw_authoritative.py` — 纪委系统 ccdi 权威化（省级 33 + 副省级市 15 + 中央派驻 26）。

## 自检（1）
- `p99_weekend_check.py` — 周末无人值守自检 / 核查脚本。

## 药监（2）
- `p79_yj_system.py` — 药监系统条模块（中央—省两级体制）。
- `p80_yj_authoritative.py` — 药监系统省级 URL 权威化（nmpa.gov.cn「地方药监」下拉，真实 HTML）。

## 证监会（3）
- `p60_vertical3_render.py` — 证监会派出机构 / 移民局边检总站 / 自然资源督察局 —— 浏览器渲染提取。
- `p61_vertical3_rest.py` — 补建三个垂管系统模块（证监会/移民管理/自然资源督察）。
- `p99_csrc.py` — 证监会系统补全（csrc.gov.cn 首页「派出机构/会管单位」区块真实 HTML）。

## 医疗（4）
- `p213_medical_system.py` — 医疗系统（卫生健康）条模块：国家卫健委+中医药局/疾控局+中国疾控中心 → 省级卫健委 32 → 市级卫健委 419 节点 + 省级疾控中心 31（疾控无导航走 SERP 筛选）；复用块树/registry 存量 + 医院项目 whc_cities.jsonl；state=p213_state.json。
- `p214_medical_verify.py` — 医疗系统 URL 正确性检验：全量并发复验连通性+title 匹配（gbk 解码/中性标题/疾控关键词/跨省同名基底 strict），mismatch/dead/waf 分类出报告。
- `p215_medical_purge.py` — 医疗 URL 污染治理（p214 问题项落地）：深路径根址优先 → 机构子站首页保留 → 都不过则清空列名；同步 tree/p213_state/registry 防下轮重采污染。
- `p218_medical_rules.py` — 医疗系统提取规则落盘（系统级一条，method 分级注明各渠道来源，SERP 兜底如实标注「线索+官网 title 严格验证」及 2026-11-17 检验治理口径）。

注：p205/p207/p210 已被五系统系列占用（p205_audit_5sys / p207_court_peer_links / p210_audit_cleanup），p216/p217 亦为五系统脚本（registry 回灌 / 县级误挂修复）；医疗系列编号为 p213/p214/p215 + p218。

## 五系统市级补全与审计（13）
- `p201_court_zy_fill.py` — 中院 URL 全量补全：各省高院官网「中院」区块提取，elink elid 直链解码（URL 编码/base64 两形态），节点名全名化。
- `p202_court_blk_sync.py` — 条树中院 URL 回填块树「市中级人民法院」（空才填）；p220 判死域（xjcourt.org / *.chinacourt.gov.cn / elink 包裹同类目标）回填前拦截，只有实际回填才写盘（indent=1，避免格式化噪音）。
- `p203_city_5sys_fill.py` — 五系统市级补全渠道①：省人大/政协/检察院/纪委官网首页市级链接区块真实提取。
- `p204_city_5sys_deep.py` — 渠道②③：市门户导航 + 百度 SERP 兜底（mu 属性取真实 URL，title 双验；每线程独立 curl_cffi Session）。
- `p205_audit_5sys.py` — 五系统市级 URL 全量审计：硬问题（文章/新闻页、门户根址、黑名单、title 不符）与存疑（中性标题/JS 壳/省级官网市级频道）分档输出。
- `p206_city_portal_nav.py` — 缺口城市门户导航深挖（组织机构栏目页，门户子路径官方频道也收）。
- `p207_court_peer_links.py` — 法院同级互链：中院官网友情链接区块提取缺口中院。
- `p208_city_peer_links.py` — 同省同级机构互链提取（P208_SYS 分系统轮换 zx/rd/jcy/jw）。
- `p210_audit_cleanup.py` — 审计裁决落库批一：替换 16（内蒙古 12 盟市纪委、东营中院、青海 3 州纪委）+ 根化 5 + 清除 57 + 医疗 2。
- `p211_five_sys_fix.py` — 审计裁决落库批二：镇江检察 zj.jsjc、淮北/六安监委（安徽纪检监察网市县导航）。
- `p212_five_sys_fix.py` — 审计裁决落库批三：合肥/铜陵/安庆监委、太原政协 tyzx（SERP 严格验证）；克拉玛依中院列名（新疆法院网 # 占位）。
- `p216_registry_sync.py` — 五系统审计裁决回灌 registry：按旧 URL 定位条目替换/清除，并向 p204/p206 种 cleared 标记防重采。
- `p217_five_sys_level_fix.py` — 五系统「县级机构误挂市级」修复：按权威源重采并 title 验证，补填 12 个严谨验证节点。

## 县级五系统补采与审计（p223-p239）
- `p223_county_5sys_fill.py` — 县级五系统补采主机器：四档渠道（S1 上级同系统官网名录 / S2 本级政府门户导航 / S3 同级互链 / S4 SERP 线索+title 严格验证）+ 共享校验器（ORG5/ORG_PATH/title_ok/geo_base…）。环境开关：`P223_STRATEGY`、`P223_S1_NAV/DEEP/ORG`、`P223_S2_SKIP_DONE/ORG/PROV`、`P223_S4_VARIANT/SKIP_BASE/RETRY/NS/WORKERS`。S2 的门户导航验收已加「领导之窗 / 建议提案办理 / 预决算 / 会议报道」负向过滤（2026-11-17 全量门户轮沉淀）。
- `p228_county_fill_audit.py` — 县级补采结果审计：A 文章/新闻路径清除、D 业务栏目/上级机构/机构类型错配、E 县名复验、F 按 p223 现行严格校验全量复验（`P228_FIX=1` 才清可清除类）。
- `p231_tidy.py` — 末期数据清理：WAF 会话参数剥离、空名/重复节点删除、门户「国家部委」链接区块误采节点清理（本次 3,595 个，市级机构数因此回到真实值）。
- `p235_upper_site_county_channel.py` — 上级站点县级频道专轮：市人大/政协/两院官网「县区」栏目深挖并 title 验证。
- `p237_12388_counties.py` — 县级监委 12388 名录补采（省纪委 12388 子站的县区目录 + root_hint 归一）。
- `p238_city_5sys_fill.py` — 市级五系统补采（复用 p223 四档渠道，task 里 county=市级节点、parent=省级节点）+ `--audit` 市级复核（省站栏目页 / 区县机构页 / 门户专题页 / 移动版归一等）。SERP 轮已加「区县机构顶替市级」「门户类目页」两条拒绝规则。
- `p239_registry_five_sync.py` — 五系统 registry 同步（省/市/县全量叶子）：树有 URL 而 registry 不同 → 以树为准；树因审计清空且 s 留痕 → registry 置 cleared；树有 URL 而 registry 缺记录 → 补登（verified_at 留空，不冒充当日复验）。

## 错误 URL 回填与垃圾节点清理（p241 系列，2026-11-18）
- `p241_wrong_url_backfill.py` — p240 清除节点（u 为空 + `p240` 清除痕迹）的**正确 URL 回填**：Phase B 通用（官方页面导航 + 百度 SERP 严格验证）→ Phase A 五系统（复用 p223 四档渠道，落库后逐条过 p240 复核，不过即回滚+还原 registry）→ Phase C 条块同步（块树同机构唯一 URL，只填空）。候选一律过 `verify()`：文章/栏目/门户栏目/群团站/重名区县证据/上级门户域名栏目等负向规则；不过的留空列名。环境开关 `P241_ONLY`（five,generic,sync）/`P241_LIMIT`/`P241_WORKERS`/`P241_FILTER`；断点 `p241_state.json`、报告 `p241_report.json`（不入库）。
- `p241b_new_url_audit.py` — p241 回填结果的**独立复核**：新进程重抓每个 s 带 p241 痕迹的 URL，用同一套 `verify()` 再判一次（硬通过/软通过=封锁默认正确/失败），`--apply` 清除失败项并做 http/https 协议升级；报告不入库。
- `p242_junk_nodes_clean.py` — 「市级政府部门」组**垃圾节点清理**：两会专题/中联办/建设部/省县政府门户冒充市级部门（13 个节点 + 9 个 registry 键），树与 registry 同步删除，写前备份，默认 dry-run。
- `p243_dup_url_adjudicate.py` — **同一 URL 跨地区串站裁决**：五系统节点按 URL 分组，组内 ≥2 个地区身份即冲突组；用 title/snippet 给每个身份打分（地区链 3/2/1 分），唯一归属保留、其余清空留名。结构变体（条树简称/旧名、州↔同名市）靠地名形态集合保护。`--apply` 清除 24 节点 + 9 registry（2026-11-18）。
- `p244_url_form_fix.py` — **URL 形态修复**：`https:https://…` 重复协议头（山西法院网 elink 解码残留，阳泉 5 站 9 节点），去头后按节点身份复核再落库，tree/registry 同步。

## 县级门户回填与连带修正（p245，2026-11-18）
- `p245_county_portal_restore.py` — p240 判出跨地区串站而清除的 4 个县级人民政府门户**回填**（石家庄桥西区 sjzqx / 连云港海州区 lyghz / 铜陵郊区 tljq / 同仁市 hntongren，用户人工核实+ 官方门户导航 + title 实测）；registry 三个裸地名键（桥西区/郊区/海州区，实为张家口/阳泉/阜新）改名加城市前缀消歧；清除连云港海州区「县人民法院」错挂的阜新海州区法院；修正 extraction_rules 海州区（320706）portal。

## 省市门户「组织机构类」栏目（p246，进行中）
- `p246_zzjg_pages.py` — 33 省级 + 333 地级市人民政府门户的「机构/单位/企业/高校」类栏目页 URL 采集。**2026-11-18 用户指令扩围**：内部组织、内设部门、机构、直属企业、事业单位、公积金、高校等都算，尽可能全面；每站 75 秒预算，超时跳过。类别优先级 机构设置 > 内设机构 > 直属单位 > 事业单位 > 直属企业 > 公积金 > 高校，同一门户多类命中全部记入 `links`，核心类最高优先作主 URL（仅命中公积金/高校时标 `partial` 继续找）。阶段：static（首页真实 HTML 锚文本分类）→ render（CDP 渲染，首页无果再渲染 1 个枢纽页）→ deep（政务公开索引下钻，治上海/广州形态）→ candrender（候选页渲染，治信息公开目录式 JS 列表）→ click（点击跳转）→ homeblock（首页内嵌机构名录兜底）+ `--refresh-extras`（已命中门户重扫首页 + 主栏目页，按 URL 增量并入，`skip_kinds` 把预算留给未收类别）。
  **枢纽页/自体页两条通用补丁**（2026-11-18）：① `self_candidate()` —— 导航直达的「机构设置」页本身直接收货（黑龙江的机构设置在「省政府」枢纽页 `/hlj/c107864/szf.shtml` 的锚点上，首页无任何机构字样；搜链接永远搜不到「抵达的这一页本身」）；从严要求**标题自证类别**，正文满屏机构字样的「政府信息公开指南」页不误收。② `hub_entries()` 把枢纽页关键词从「政务公开/信息公开」扩到「省政府/市政府/政府机构/走进XX/政府领导」。
  **评分三源证据**（2026-11-18）：`<title>` → `h1/h2/h3` 大标题 → 正文版块标题。大量门户栏目页 `<title>` 是站点模版名（长春政府机构页 title=「长春市人民政府-中国长春」，栏目名只在 h2「政府组成机构」），只认 title 会系统性误杀；正文版块证据要求同时 ≥10 个部门名（资金/领导页也有一两个部门名，单靠关键词会误收）。关键词补齐 `机关简介/机构简介/政府组成机构/政府工作部门`（锦州 `/jgjj1.htm`、朔州「机构简介」页）。**但 `letter_detail` 信件详情、办事服务页仍被负向规则挡掉**。
  **点击阶段四重加固**（2026-11-18）：① 候选从 1 个扩到最多 4 个，且只取最内层命中元素（点父容器=点整块导航，落点不可控）；② 落点是模板 404（七台河 `/dept38`、三门峡 `/dept103` 这类全站失效 href）→ 回门户换下一个候选，不再整站判死；③ 点了不跳转（hover/折叠展开式导航）→ 扫展开后 DOM 里的锚点再验证；④ 落点是 JS 空壳列表页 → 渲染落地页再判。**直连一轮拿不到（WAF/导航全靠 JS）→ 换 dps 代理独立 context 再点一轮**（`_proxied_page()`，Stealth + UA 覆盖与 `cdp_page()` 同等）。
  **`</a >` 闭合标签坑**（2026-11-18）：青海/甘肃门户写的是 `</a >`（尖括号前带空格），`<a…>(.*?)</a>` 匹配不上就"跨段吞并"，锚文本变成整段导航的超长串被丢弃——候选凭空消失（青海 `/xxgk/jgzn/` 明明在首页导航里，却判 `候选0`）。统一改用 `ANCHOR_RE = <a\b([^>]*)>(.*?)</a\s*>`。
  **iframe 外壳首页**（2026-11-18）：海南 `www.hainan.gov.cn` 根址只返回 1150 字节，正文就是 `<iframe src="/hainan/">` —— 真首页在 iframe 里，不跟进去静态阶段必然全灭。`iframe_home()` 跟同站 iframe（官网自己声明的入口，不算拼路径），`try_portal_static` 与 `fetch_or_render` 都接上；海南由此拿到 `/hainan/zfjgg/zfjg.shtml`（标题「政府机构」、40 个部门、10 分通过）。
  **links 去重**（2026-11-18）：同一张页面的多个入口（海南 `zfjgg/zfjg.shtml` 与 `zfjg/zfjg.shtml?ddtab=true`）会重复登记，`dedupe_links()` 按「同类别 + 同标题」去重（标题空则退化为同 path），`make_rec()` 与 `--reaudit` 都调用。
  **homeblock 兜底阶段**（2026-11-18，`--phase all` 末位）：西藏（首页底部「自治区政府部门网站」下拉）、甘肃（首页「省政府组成部门/直属特设机构/直属机构/部门管理机构/直属事业单位」版块）、连云港（首页页脚 `div_6.daohang_list` 部门网站：市委/市政府/群众团体/垂直管理部门 + `div_7` 市属企业/高校）把机构名录**内嵌在首页自身**，全站没有（或静态 HTML 里没有）独立栏目页，前五阶段必然全灭。该阶段收首页并留痕「门户首页内嵌机构名录（前序阶段未发现独立栏目页）」；判定=**按分组标题切段后，某段开头的 20000 字符内出现 ≥8 个机构站点链接，且整页机构站点链接 ≥15**，分组标题必须短（≤16 字）且不含 `条例/办法/通知/指示/会议/巡察/进驻/召开/关于…` 等句子词——新闻标题里的「国有企业」「市委巡察」、甘肃「事业单位登记管理条例」都会误命中（实测已挡）。**段内距离阈值**是关键：呼和浩特一条「十四届市委第一轮巡察完成进驻」标题后面拖了 6 万字符才凑够 8 个部门链接（新闻正文+全站导航），不是名录；真名录都是紧凑的页脚一列（西藏 3674 / 甘肃 1322 / 兵团 1055 / 天津 10974）。**页面够大但名录是 JS 拼的**（连云港静态 81KB 只有 3 个机构锚，渲染后 16 分组/119 个机构）要在静态判定失败后**显式再渲染一次**——`fetch_or_render` 只在静态 <1500 字节时才渲染，覆盖不到这种形态。零散部门链接而无分组块的首页（北京/太原/鞍山/开封/三门峡）一律拒收；广州（页脚「人民团体和群众团体」组后 49 个部门站）、赤峰（「市政府部门」组后 30 个）属真名录，收。`--reaudit` 对 `homeblock=True` 的链接走同一判定器复验，不走 page_score。
  **标题归属与本地性校验**（2026-11-18 二轮加固，`p246_hb_refresh.py` 可对存量重算）：
  ① 分组标题只认**结构性标签**——名录里某条链接的文字要被踢掉（合肥「政府机构网站」列表最后一条是「市委老干部局」，曾把 49 个部门全挂到老干部局名下；判据=标题所在 `<ul>` 内、它之前已排 ≥5 个机构链接就是名录成员，但 `h2/h3 > a` 里的标题照样认，郴州「本市集约化网站」即此形态）；
  ② 分组必须是**本地**机构名录——`国家××部/中国××/部$` 占比过高（伊春 34 条、绥化 84 条、牡丹江 35 条、武汉 65 条都是「国家部委/省政府部门/兄弟城市」友链区），或**同域比例过低**（真名录 80–100% 在门户同域，甘肃 23/23、青海 24/24、合肥 45/47；伊春同域 0%）一律拒收；
  ③ 「政府机构网站」「集约化网站」「网站群」已补进分组标题词表（合肥 JS 注入的 `政府机构网站` 列表、郴州 `li > h2 > a「本市集约化网站」` + `div.links-down` 隐藏层，符合同域部门站形态）；
  ④ 标题若本身像部门名（命中 `厅|局|委员会|办公室`、以「政府/党校」结尾、含「信箱」）改记为中性「首页机构名录」，不把单个部门冒充成一组。
  实测：甘肃/西藏/兵团/天津/青海/合肥/郴州/苏州/连云港 认，北京/太原/呼和浩特/武汉/伊春/牡丹江/绥化/池州/三沙/儋州 拒（三沙 92、儋州 36 个「机构锚」实为国务院/海南省级友链）。
  **验证/排序四处补丁**（2026-11-18 三轮，补收鞍山/营口）：① `page_score` 增「**机构路径 + ≥10 部门名**」组合证据——鞍山 `/asszf/zfxxgkml/fdzdgknr/jgjj/index.html` 标题只是「政府信息公开-鞍山市人民政府」，dept35 + ORG_PATH 即判过（旧口径 score3 误杀真机构页）；② `candrender` 候选排序改为**类别优先于分数**——营口首页只给「公共企事业单位信息」（事业单位 score8）与「公开机构与联系方式」（机构设置 score5）两条，旧口径只试 score≥8，真正的机构页永远轮不到；③ 「入口锚文本自证类别 + 页面验证通过」也收页——营口该页正文是 45 个部门名+联系方式的表格、**没有任何部门链接**，标题「政务公开-营口市人民政府」也不含机构字样，`self_candidate`（要求标题自证）必然漏；④ href 里 `&amp;` 先反转义再入库（该页 categorynum 参数）。
  **smart_fetch 获取链补丁**（2026-11-18，成都突破，影响所有采集脚本）：① **412 必须按响应体区分 Cloudflare / 瑞数**——旧链只看状态码，把带 `$_ts/nsd` 的瑞数 412 当 Cloudflare 处理，整段跳过 iv8/nodenv/RsSpider，成都白烧 265s 落 blocked；按 `_is_ruishu()` 判体后 `smart_fetch` 2.9s 拿到 281KB。② curl_cffi 超时改 `(connect, read)` 元组（connect ≤6s）——黑洞 IP 的 SYN_SENT 单浮点 timeout 兜不住（儋州/唐山静态卡 10min+）。③ `_try_ruishu` / `_try_iv8` 增加 dps 出口兜底（`IV8_PROXY` 让求解与重抓同一粘性 IP，cookie 与出口绑定）。
  候选页一律回抓验证：机构类看标题/内设机构/直属单位/部门名计数，企事业/公积金/高校类看类别关键词+实体名计数；办事服务页（提取公积金/登记管理/招生考试）、领导之窗、部门动态、新闻一律负向剔除。产物 `zzjg_pages.json`（事实源）、`p246_state.json`（断点）、`zzjg_pages_rejected.json`（复验剔除）；`--reaudit` 全量复验（支持多链接逐条剔除）、`--sync-registry` 写入 registry 的 `zzjg`/`zzjg_src`/`zzjg_links`。采集走 smart_fetch，`.env` 配 `PROXY_MODE=dps` 使用私密代理（节点 10 分钟有效期，`util/dps_proxy.py` 绑定 TTL 480s）。
- `p246_report.py` — p246 覆盖率报告（总览/类别分布/分省覆盖/缺口及失败原因）→ `zzjg_pages_report.md`，只读。
- `p246_export.py` — p246 成果摊平导出 → `zzjg_links.csv`（省/层级/单位/类别/标题/URL/方式/验证日期）+ `zzjg_links.md`（按省分组表），只读，用于交付复核。
- `p247_sitemap.py` — **网站地图渠道补采**（p246 第七通道）：六阶段全灭的门户，首页→同站「网站地图/站点导航」锚→地图页栏目候选→回抓验证（静态不过再渲染）。只走站内官方页面，不拼路径不走 SERP；复用 p246 的分类/评分/合并函数，结果增量并入 `zzjg_pages.json`。

## 县级人民政府「组织机构 / 部门信息」（p248，2026-11-18 用户指令扩展）
- `p248_county_zzjg.py` — 树内 **2,831 个县级人民政府**门户的机构/部门栏目采集（县级多数没有独立部门导航，形态与省市完全不同）。阶段（`PHASES` 有序字典，`--phase all` 按序试）：**`xxgkpage`（2026-11-19 新增，排最前）**、`sc` 四川省统一平台（`sczwfw.gov.cn/...deptSwitch?areaCode={cd}000000`，页面自证「直通部门」+ 部门链接 areaCode 必须等于本县；**6 个区划调整县区平台仍用旧码**，`SC_LEGACY` 已逐个实测）、`static` 首页锚文本、`render` 渲染、`deep` 政务公开→部门信息公开下钻、`xxgk` registry 专栏入口、`click` 渲染点击。产物 `zzjg_county.json`，断点 `p248_state.json`。
  **`xxgkpage` 阶段（用户 2026-11-19 人工分析 26 站后提炼的主导形态）**：县级部门清单**普遍不在门户首页**，而在「政府信息公开 → 法定主动公开内容 → 组织机构/机构简介/政府组成部门/部门平台链接」，且信息公开常独立挂在 `xxgk.<主域>` 子站（`P.same_site` 按 registrable domain 比较，子域视为同站可直接跟随）。实现：门户页抓锚点 → 收三类 hub（短锚文本命中「政府信息公开/政务公开」、href 含 `xxgk|zwgk|zfxxgk|gongkai|openinfo`、短文本且指向异主机的子站）→ 逐 hub 抓取：自身即目标则收（`self_candidate`），否则 `collect_links`；都不成再下一层，按 `SUB_KW`（法定主动公开|公开目录|机构简介|平台链接|部门单位|政府组成部门…）挑子页复验。全程受 `P.BUDGET` 与同站约束，链路写进 `src` 留痕。
  **候选页的「必须是部门清单」硬卡（`_deptlist_ok`，2026-11-19 补）**：`page_score` 只看标题含「机构职能」——「长山峪镇人民政府机构职能信息」这类**单篇公文**、企事业单位专栏都能拿高分（滦平/怀安/宽城/盐山实采复现）。所以本阶段额外要求：① 非文章 URL 形态（`/content/\d`、`/info/`、`/doc/`、日期目录、长数字 id）；② 页面不同「局/委/办/中心」名称 ≥6 个。不合格继续试下一候选，全不合格返回 `xxgkpage-no-verified`（保留原记录，绝不写入错入口）。
  **回炉低产县**：`--force` 绕过「已有核心链接就跳过」，`--keys-file` 精确指定 key（同 p250）。实测抽样 24 个低产县 → 8 个变 ≥3 部门、5 个部分命中；不加重跑入口这一步，渲染 100 个县零产出。
  预算尾声（剩 <35s）不再开渲染（`_fr`），否则一次渲染 45s 吃光整站预算、单县吞吐从 20/min 掉到 2.7/min。
  **归属校验 `county_guard`（红线：绝不能采成上级单位的部门）**：① URL 必须与本县门户同主域（四川平台例外：areaCode 必须属于本县且末两位非 00）；② 页面 `<title>/h1-h3` 或正文 ≥2 次出现本县名（含去后缀/去民族修饰/去省名前缀的基底名）；③ 标题出现上级市/省基底名而本县名缺席 → 判 `parent-unit` 拒收。写入前 `quick_guard` 先卡 URL 归属，并按 `_link_bad` 逐条过滤：**上级单位机构栏**（title 写上级市/省机构名）与**非清单页**（招聘/公示/公告/预决算/单条公文）只丢该条，全丢则整条拒收。两条免判例外——链接主机 == 本县门户主机（县站模板把市名印进 title：汝南/门源/栖霞实锤），以及 `kind` 为公积金/社保等全省统办入口（白沙可用省公积金局）。
  `--tidy` 离线清理：不抓页，直接按上面的 title 规则删链接/整条剔除，等价于 audit 的第一步，省请求。
  `--audit` 复核：逐条回抓，重跑 `page_score`（公文/预决算 `doc-page`、服务页、领导页一律剔除）+ `county_guard`，不合格整条移入 `zzjg_county_rejected.json` 并清断点；同时输出漏采清单 `zzjg_county_missing.json`。`--audit-render` 对 JS 壳页面渲染再验。
  `--retry-fail --retry-fail-re 'blocked|short|timeout|exc'` 只重试被封/超时的目标——配合 `PROXY_MODE=dps`（用户指令：IP 被封的站积极用代理），不浪费每 24h 1000 个代理 IP 的额度。
- `p248_report.py` — 县级覆盖率报告（分省/分市覆盖率、类别与渠道分布、剔除清单、漏采失败原因 Top15）→ `zzjg_county_report.md`，只读。
- `p249_fix_dup_county.py` + `p249b_reg_dup.py` — **同名区县门户 URL 串号修复**（2026-11-18）：7 组同名区县（新城区/青山区/西安区/南山区/西湖区/市中区/城关区）在 tree 里共用了同一个门户 URL，必有一方错。用**上级市政府门户的区县导航**（合规权威渠道）逐条核对，改正 7 个、暂缺权威来源清空 2 个（深圳南山、杭州西湖），并给 registry 补齐带省名/市名的同名条目。`p248 --drop` 剔除受影响县的错采记录后重采。

## 县级「政府部门名录」（p250，2026-11-19 用户指令）
- `p250_county_depts.py` — 从 `zzjg_county.json` 已采到的组织机构栏目里抽**部门名清单**。用户口径：「政府信息公开 → 法定主动公开内容 → 组织机构 就是我需要的内容」「删去机构职能几个字」「存在分页，采集完毕，然后清洗，删去冗余内容，最后去重」。
  - 两阶段：`static`（curl_cffi 直抓，约七成县首屏可抽）→ `render`（9222 常驻渲染 + **逐页点击分页**；云南统一平台 `/{县}rmzf/cXXXX/pc/list.html` 列表靠 POST 加载，分页 DOM 是 `<a class="num" data-page="N">`）。
  - 清洗：剥尾部冗余词（机构职能/机构职责/职能机构/职能职责及分工/组织机构/机构设置…最长优先循环剥）；**只留同站链接**（区分本地部门与页面上的上级/外站链接的唯一可靠信号）；剔除导航噪声（网站地图/新闻中心/公示平台/裸「县政府」残片）。
  - **县级闸门 `county_guard_depts`（红线：不能采成上级单位的部门）**：含本县名 → 收（`大理州生态环境局云龙分局` 是本地派出机构）；以所属市/省基底名开头 → 拒；无地名前缀的短名（`司法局`）→ 收。实测 `县|吉林省|四平市|铁西区` 的组织机构页是本区站点，但列的是**四平市**各部门，同站判定挡不住，只能按名称前缀判，35 条里剔掉 24 条。
  - **人工核验种子 `county_depts_seed.json`（2026-11-19，优先级最高）**：用户逐站分析的 21 个「部门/组织机构」真实入口（磐石/中宁/岚县/武鸣/曲水/六枝/嘉荫/云龙/景宁/琼山/榆中/六合/弋阳/顺昌/长海/广德/沂南/蕉岭/孝昌/茶陵/丹凤），直接绕过自动候选。`--seeds` 只跑这些；命中记录 `method=manual/...` + `seed_m` 保留用户备注。实测 17/21 出部门（≥16 条/县）。**故意不含**用户标注「无入口」的兴和县/周口临港开发区/和田市/固安县/互助县。
  - 并发：**每县一个 `subprocess.Popen(start_new_session=True)` + `communicate(timeout)` + `os.killpg(SIGKILL)`**（`ProcessPoolExecutor.wait()` 实测在 future 条件锁 `_PyMutex_LockTimed` 上永久阻塞、timeout 形同虚设，连续复现；`mp.Pool.terminate()+join()` 会被卡在系统调用的子进程拖死；线程杀不掉）。子进程 `socket.setdefaulttimeout(25)`。
  - **死站性能陷阱**：`smart_fetch` 对死站会跑满整条降级链（curl_cffi→系统 curl→cf→iv8→nodenv→瑞数 9333→DrissionPage→CDP），静态阶段吞吐 <7 县/分。设 `RS_DISABLE=1` 跳过最重的瑞数层后，117 县 33 秒跑完。
  - 代理（2026-11-19）：dps 私密代理已失效，隧道代理可用。`PROXY_MODE=off` 跳过 dps 但保留 `TUNNEL_PROXY` 兜底，降级链变「直连 → 隧道 → 直连」。
  - 渲染并发 3（`P250_RENDER_DEADLINE=50` 把单县上限压到 50s），实测 ≈7.5 县/分；内存 8G 机器不再吃紧。多进程同时写盘用 `P250_OUT` 分文件，避免互相覆盖。
  - 产物 `county_depts.json`（键同 `zzjg_county.json`，值为 `{u, method, pages, depts:[{n,u,c}]}`，`c` = gov/town/party）；`--reclean` 不联网重跑清洗与闸门（纯离线收口时**早退，不顺带联网重采**），`--report` 出产量分布。前端经 `zzjg_nodes._county_tree()` 消费：≥3 个部门的县叶子直接展开为部门清单，否则回退栏目链接。
  - **回炉流程（2026-11-19 定版）**：`p248 --phase xxgkpage --force --keys-file <低产县>` 换正确入口 → `p250 --phase static --force --keys-file <同一份>` 重抽 → 仍 <3 再 render。**入口 URL 本身不是部门清单时，渲染再多次都是零产出**（实测 100 个低产县渲染，部门条目总数一条未增）——瓶颈在入口，不在渲染。
  - `--only` 传多个县名要作为**一个参数**（`--only "磐石市 中宁县 岚县"`），argparse 不接受空格分隔的多值；跨多县批量一律用 `--keys-file`（每行一个 key，精确匹配，避免「城区」这类同名子串误中）。

## 全量 URL 核查与治理（p240 系列）
- `p240_full_url_verify.py` — **全站 URL 身份全量核查**：树节点 + registry-only 共 2.3 万唯一 URL 逐条实抓，按「地区/机构类型/文章页」三维判身份，分档 `ok / ok_neutral / waf / dead / suspect / mismatch`。要点：WAF/IP 封锁（含 4xx 反爬）**默认正确**并走隧道代理复验；标题取最深层行政区比对（上级地名顶替判错配）；跨省同基底（天津河北区 vs 河北省）专判；功能区名归一（经开区/综改示范区/西海岸新区）；合署办公（黄岛=西海岸、汉南=武汉经开、金州=金普）与省级平台市级频道（wx.jsjc「江苏检察网」）列入复核例外。`--report` 出报告、`--prune` 清「省级部门误挂市级组」结构垃圾、`--apply` 按节点清除 mismatch（同 URL 在别的节点正确则不清树、registry 仅在无任何存活节点时清除）。
- `p240b_article_fix.py` — 文章/详情页 URL 处置：把 p240 判为「文章页」的链接换成本站根页并重判身份，根页也过不了的清空列名（文章页不是机构官网入口）。
- 本轮核查口径、分档统计与误判修正记录见 **`URL_VERIFY.md`**（`p240_results.jsonl` / `url_verify_report.json` 为可复跑的中间产物，不入库）。
> 该批次脚本较多，各脚本头部有完整背景说明；此处按主题登记主线，未逐条列出。

- **垂直系统补采 p116-p120**：省院渲染探测、金融监管/移民/海关官网机构页、总局名录落库。
- **门户权威化 + 市县/厅局审计 p121-p130**：省政府门户市州导航、市/厅局缺口补采、拼音存量清除（p129）。
- **门户与厅局全量重建 p131-p137**：32 省门户渲染、SERP 线索 + title 验证、外交系统（p136/p137）。
- **政协第二轮 + 条系统重构 p139-p148**：省政协官网交互提取、群团系统重建（p145/p145b）、省级群团补采。
- **检察院第三轮 + 县级人大政协 p150-p163**：市/基层院扫描与落库、县级人大/政协节点建设、抽样审计与修复（p159-p160）。
- **经验/垂管/Registry/巡检 p161-p172**：经验写入名录（p161）、气象地震（p164）、垂管扩充（p165-p166）、site_registry（p167-p168）、巡检（p170-p171）。
- **信息公开专栏 p173-p177**：静态/渲染两轮 x 采集与落库、厅局 URL 修正、海关直属关攻坚（p176 系列）。
- **市级体系补全 p178-p188**：通用提取器 extract_org、市检察院/政协/人大补全。
- **地图与区划 p189-p200**：条→块同步（p189/p193/p196）、重庆补全（p192）、凉山（p194）、县级门户补全（p195 系列）、台湾 geo（p197）、五系统市级循环（p198）、市级部门（p199）、功能区（p200）。
