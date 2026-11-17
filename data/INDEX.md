# 提取规则脚本索引

共 274 个脚本（data/*.py）。编号 p0-p221 = 开发顺序。
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

## 数据管线（10）
- `p221_url_stats.py` — URL 缺失率统计（省/市/县 × 政府/人大/政协/纪委/法院/检察/党委/群团/民主党派…）：块视图省级子树逐机构统计 u 是否为空，输出 `data/url_stats.json` + `data/URL_STATS.md`，并把结果嵌进 `data_js/quality.js`（站点「数据健康」面板消费）；p22 管线自动调用。
- `p220_dead_link_fix.py` — 死域名清理 + 错挂修正：整站下线/迁域的存量 URL（DNS NXDOMAIN）替换或列名，衡阳县/濮阳中院错挂修复，同步 registry（写前备份）。
- `p22_split_data.py` — 把 tree.json / extraction_rules.json 拆分为模块化数据文件（自动调用 gen_viz）。
- `p219_build_dist.py` — 站点发布包构建：只拷 HTML/视图脚本 + gov_data.js + data_js + data/geo 到 dist/，校验引用完整性、Cloudflare Pages 限额（单文件 25MiB/20000 文件）与泄漏（不含 .py/.json/state）；纯标准库，可直接作为 Pages 构建命令。
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

## 民主党派（3）
- `p113_dp_mount.py` — 民主党派省级组织挂载（民盟/民建/民进/农工/致公/九三 + 九三市级）。
- `p114_mg_tm.py` — CDP 渲染民革/台盟官网找省级组织导航。
- `p115_mg_tm_mount.py` — 民革省级挂载（24 有官网）+ 台盟省级全列名 + rules 同步。

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
- `p202_court_blk_sync.py` — 条树中院 URL 回填块树「市中级人民法院」（空才填）。
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

## 中期批次概览（p116-p200）
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
