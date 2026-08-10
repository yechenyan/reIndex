# PDF to Markdown with verified table parsing

- 状态：开发中，等待人工审核
- 日期：2026-08-09

## 用户原始请求

> 我要做一个 PDF 转 markdown 的工具：
> 工具名字叫做：reIndex/packages/pdf-to-markdown
> 作用： 给定一个 PDF， 生成 markdown
> 流程：
> 1. 跑一遍 LiteParse 用它生成 markdown
> 2. 找到 liteParse 识别出的所有可能是表格的地方对于复杂的表格，直接判断用专门解析器
> 3. 对简单的表格：截图并构建列表；用 codex CLI 起一个 sample 采样进行前3行后3行采样；
> 用代码与 liteParse 表格比对，通过则继续，失败交给专门解析器。
> 4. 专门解析器是 reIndex/packages/pdf-table-5，尽量少改动并增加指定页面处理。
> 5. 用专门解析器结果替换 liteParse 生成的表格。
> 不要参考其他的本地类似产品，那些是失败作品。

## 后续请求

> 开始做吧，尽可能对 reIndex/packages/pdf-table-5 进行较少的改动。做完后用指定的
> sws_netze_solingen_gmbh_netzausbauplan_2024_pdf.pdf 进行一轮测试。

> 把 reIndex/packages/pdf-to-markdown/skills 写到这里，这样我只用引用这个 skill 加 input 就可以了，然后给我提示词。

> 测试时遇到问题，见对话：019fe679-7c4f-7fe3-953f-1343afaeaa06。

> 最简单的，你只要把 pdf-table-5 输出的表格放到对应的页面，代替原表；如果一个页面输出了
> 两个表，就放两个表上去。pdf-table-5 不用做小范围加固。

> Finder 不用大改，只加提示词。主要修改 Parser 提示词：检查表格周围是否混入表格外内容，
> 确认完整表格范围；无法确认时扩大表格截图范围。

> LiteParse 生成的 Markdown 没产生对应图片；在 `output.md` 同目录建立 `assets` 并把图片放入，
> 只增加 `image_output_dir`、相对路径和图片落盘，不增加完成校验等逻辑。

> 高分辨率大图要加限制；制定 `pdf-table-5` 表格确定进入 `output.md` 的方案，并系统解决多次出现的
> LiteParse 候选碎片数量与专项表格数量不一致问题。

> 修复 AVU 测试中的跨页误分组、连续表漏页和跨行重复词误杀；完成后清空旧产物，在
> `/Users/maxiao/Documents/code2/nap_gridextractor/data/nap-markdwon/avu_netz` 做全新测试。

> 查看对话 `019fe720-86ee-74c2-91bf-c99919c7a242` 的失败原因，并给出解决方案；本轮只诊断，
> 不修改实现。

> 查看对话 `019fe753-6d17-7910-a666-15c020a20a5d` 的失败原因并给出解决方案；先不要修改代码。

> 简化修复方案：提示词明确 header 和行号计算；不把 `suspectLocations` 作为严格修改权限；确认
> 结果校验失败不能终止整个 PDF；最外层仍生成 `accepted:false` 的报告，并且流程继续完成、生成
> `output.md`。本轮先讨论，不修改代码。

> 修改吧，并直接以 `nap_gridextractor/data/nap-markdwon/badenova_netze` 做测试。

> 排查 `celle_uelzen_netz`、`mvv_netze`、`stadtwerke_rostock_netzgesellschaft`、
> `swe_netz_erfurt`、`travenetz`、`westnetz`、`wsw_netz` 七个生成异常，说明原因并给出方案；
> 本轮只诊断，不修改代码。

> 修复七份异常：同页回填改为原子提交；`sample.py`/`parse.py` 不能运行时继续进入 repair；单表异常
> 不得终止其他表；不改 repair 状态机；支持连字符两侧空格等价；Parser 在 geometry OCR 污染时以
> 可见 crop 为准。不要把自动删除旧产物做进产品，只在本次 SWE 测试前临时清理其旧运行目录；
> 修改后直接测试上述七份 PDF。

> 修复 enercity Tabelle B.3 的合并单元格校验：视觉边框表明单元格横跨多个逻辑列时，字符坐标
> 只表示合并单元格内的排版位置；确认采样和 Repair 必须按 sqlFriendly 规则把完整值复制到所有
> 覆盖列。清理 EAM 旧产物后由新 agent 重新处理 `eam_netz`。

> 修复 enercity 现有产物：明确 Review mismatch 左侧是期望 sample、右侧是实际 CSV，复用已验证的
> Tabelle B.3 专项结果重新完成 Markdown 回填和报告，不重新解析整份专项表格。

> SWE 第 16 页的 `Abb. 6: Screenshot Ergebnistabellen HS-Netz` 不应仅因 `Abb.`/`Screenshot`
> 标题被当作普通插图跳过；按最小方案补 Parser 提示词、清理该 PDF 的旧 specialist 缓存并重跑。

> 直接人工删除 SWE 最终 Markdown 中图片周围残留的 LiteParse 散落 OCR 文本，并说明其产生原因。

## 当前范围

- 新增独立 `packages/pdf-to-markdown`，负责 LiteParse、候选表、简单表抽样、专门解析路由与替换。
- 对 `packages/pdf-table-5` 只保留指定原始页码、连续页合并保护和提示词所需的小范围改动。
- 不使用或参考其他本地 PDF 转 Markdown 失败实现。
- 在包内提供可按路径直接加载的单文件 `skills/SKILL.md`，不使用标准发布或发现入口。
- skill 只要求输入 PDF；默认输出到同目录的 `<pdf-stem>-pdf-to-markdown-run/`。

## 验收目标

- LiteParse 只做一次解析，同时保留 Markdown、页面坐标、复杂度、文字和矢量证据。
- 简单表按表头、总行数、前 3 行和后 3 行做独立视觉抽样检查。
- 复杂表、抽样失败和抽样异常候选一次性交给 `pdf-table-region`。
- region 从外部表格列表开始运行，支持 `yes|possible|no` 跨页关系和中断恢复。
- 最终输出 Markdown、逐表/整体报告；未验证表格不能静默成为成功结果。
- 新增或修改的手写 Python 文件不超过 200 行。

## 实施记录

- 已实现 LiteParse 单次解析、候选发现、表格截图、Codex 独立首尾抽样、确定性比对、
  `pdf-table-5` 指定页面回退、GFM 表格替换及 fail-closed 报告。
- `pdf-table-5` 新增页码选择；Parser 提示词要求按源网格检查跨行边界。相邻行重复节点或分类的
  启发式诊断因会误杀合法数据，已退出硬失败路径。
- 指定 PDF 冷启动完整转换约 296.7 秒；缓存后复跑约 28.4 秒。6 个候选全部验证，
  其中 2 个由 LiteParse 抽样通过，4 个由专门解析器通过。
- 新增单文件 `pdf-to-markdown` skill，默认从 input 推导输出与工作目录，并强制检查 `accepted`、
  `failedTableIds` 和 `unmatchedSpecialistTables`。
- 专门解析结果改为页面对多表映射；同页全部 accepted 表按页码、bbox 上边界和左边界排序后
  拼接到该页替换区域。`pdf-table-5` 仍只接收页码并由 Finder 自行定位、截图，未为此修改。
- Finder 提示词补充“一个连续网格只生成一个候选”；Parser 提示词增加表格边界检查，要求排除
  相邻说明/表格、确认首尾行和左右列，并在范围不确定时按需扩大截图或直接读取源 PDF。
- LiteParse 启用原生嵌入图片提取，图片写入输出 Markdown 同级 `assets/`；整体和分页 Markdown
  中的占位引用统一改为 `assets/<文件名>` 相对路径，未增加额外完成校验或报告字段。
- LiteParse 增加文档级自适应 DPI：默认 150 DPI，仅在超大页面会超过 2500 万像素或单边 6000
  像素时降低 DPI，并在 `liteparse.json` 记录实际 `renderDpi`。
- 专项表格落盘改为页面级事务：同页 accepted 输出按视觉顺序共同替换该页所有 LiteParse 表格
  碎片，不要求两侧数量一致；临时运行标记验证每个替换组恰好插入一次并在写盘前移除。
- `report.json` 在最终 Markdown 原子写入成功前始终保持 `accepted: false`；成功后记录
  `specialistPlacements`，包含页面、专项 `parseTableIds` 和被覆盖的 LiteParse `tableIds`。
- 候选发现改为逐页建模，不再把连续的弱表格信号自动聚成跨页候选；当 LiteParse complexity
  漏报时，高密度 `vectorLines` 仍会把页面送入专项 Finder。Finder 只允许同页或连续页合并。
- 页面级回填取消跨页候选必须由单个输出组覆盖全部页的限制；同页/跨页 accepted 表按其实际
  页面消费候选，Finder 未找到表格的页面保留 LiteParse 原文。

## 验证记录

- `uv lock --check`：通过。
- `uv run --package pdf-to-markdown pytest packages/pdf-to-markdown/tests packages/pdf-table-5/tests -q`：65 passed。
- 检查 `packages/pdf-to-markdown/skills/SKILL.md` frontmatter、命令与路径层级：通过。
- `git diff --check`：通过。
- Bielefelder 失败项目缓存复跑：`accepted: true`，第 5 页依次写入 `table_0000`、`table_0001`，
  `unmatchedSpecialistTables: []`，内部耗时 5047 ms。
- Solingen 既有产物静态回归：4 个专门解析结果各消费一次，16–17 页跨页表未重复，unmatched 为空。
- 提示词修改后完整单元回归仍为 65 passed；按用户要求未继续执行冷启动 PDF 测试。
- 图片落盘修改后完整单元回归为 66 passed；另以 LiteParse 真实解析确认 `img_p3_1.jpg` 会写盘。
- 超大页限流和页面事务单元测试：`packages/pdf-to-markdown/tests` 为 18 passed；覆盖 A4 保持
  150 DPI、4953×3500 pt 页面受双重上限约束、4 个 LiteParse 碎片由 3 个专项表格覆盖，以及
  替换组恰好插入一次。
- AllgäuNetz 第 15 页真实 LiteParse 验证：自适应值 86.46 DPI，解析 0.03 秒，未再产生超大栅格。
- 使用该失败运行的既有产物做静态回填：第 8 页 3 张专项表覆盖 4 个 LiteParse 候选，第 15 页
  1 张覆盖 1 个候选；4 个专项结果全部消费，最终 Markdown 含 4 个表且无运行标记残留。
- `uv lock --check`、`compileall`、`git diff --check` 均通过；`pdf-to-markdown` 与 `pdf-table-5`
  完整回归为 73 passed。
- AVU 冷启动端到端转换通过：`accepted: true`，总耗时 1,315,168 ms；11 张专项表全部 verified，
  `failedTableIds`、`unmatchedSpecialistTables`、`failedSpecialistTables` 均为空。
- AVU 措施表由第 39–43 页连续五段合并，最终 CSV 61 行，包含第 41 页行号 47/59、第 42 页
  行号 60/72，尾部覆盖 73–82。最终 Markdown 含 19 个表格块、11 个相对图片引用且文件均存在，
  无临时事务标记残留。
- Badenova 失败运行诊断：Finder 经 WebSocket 重试和 HTTP 回退后实际成功，耗时 671429 ms 并
  写出 34 个片段；真正终止点是随后 4 ms 的 merge 准备阶段。`find_0010` 位于第 33 页，前一个
  已选片段位于第 29 页，却被标为 `mergeWithPrevious: possible`，同时显式输出
  `preFindTableId: null`，触发 `Possible merge has no previous item: find_0010`。
- 复核第 32 页 LiteParse 证据：`text_table_run_count=0`、`ruled_table_count=0`、仅 2 条 vector line，
  内容为正文；第 33 页才出现 399 条 vector line 和 `table-likely,dense-graphics`，因此没有证据表明
  专项页选择漏掉了该连续表的上一页。
- 当前非连续页保护已能确定性拒绝该缓存结果（`Cannot merge nonconsecutive pages 29 and 33`，
  `packages/pdf-table-5/tests/test_contracts.py` 为 9 passed），但仍确认一个残余契约漏洞：相邻页的
  `possible` 若显式携带空前驱 ID，现有 `setdefault` 不会修复它，校验会放行而 merge 阶段仍会失败。
  建议后续将 `preFindTableId` 完全由有序结果派生，并在校验层要求合并关系只指向紧邻前项；merge
  准备阶段再按顺序派生前项而非信任模型字段，同时让顶层异常也写出 `accepted: false` 报告。
- Badenova 第二次失败诊断：前一次非连续页错误已越过，Finder、merge/list 及前三张表处理成功；
  真正失败于 `table_0003` 第一次 repair 后的独立 sample confirmation。CSV 为 24 行（表头 1 行、
  数据 23 行），正确尾部数据索引是 21/22/23，repair 提议的 `totalRows=24` 也正确；确认 Agent
  虽正确修复了抽样值，却把“23 条数据”误写成 `totalRows=23`，形成与索引 23 自相矛盾的结果。
- 确认提示词只嵌入 JSON Schema，没有像 Parser 提示词一样说明 `totalRows` 包含表头；而本次
  `suspectLocations.metadataFields` 为空，确认阶段本不应修改 `totalRows`。建议将确认写入限制在
  `suspectLocations`：未授权元数据保持当前值；补充行数/索引语义；非法确认结果只使本次 repair
  失败并进入后续 repair，而不是异常终止整个专项及 PDF 转换。顶层仍应生成 `accepted: false` 报告。
- 用户选择更简单的后续方案：不实现 `suspectLocations` 写入权限限制；只在确认提示词中写清统一
  行数语义，并把非法确认结果降级为该表 repair/验证失败，继续处理后续表格。专项表最终未通过时
  不使用其 CSV 替换 Markdown，而保留该页 LiteParse 原文；流程仍必须写出 `output.md` 和包含失败
  表格、失败阶段及错误的 `report.json`，其 `accepted` 保持 false，CLI 最终以非零状态表示未通过。
- 已按该方案实现：source-confirm 提示词明确 header/`totalRows`/数据 `rowIndex` 语义；非法确认
  写为 `rejected_invalid`、保持当前 sample 并继续下一次 repair。`pdf-to-markdown` 无论最终验收
  是否通过都会先应用 accepted 专项替换、写出 `output.md` 和最终报告；失败表格保留 LiteParse
  原文，报告新增 `failedStage` 与 `errors`，随后 CLI 才以非零状态表示未完全验证。
- `pdf-table-5` 整体异常也会在 `pdf-to-markdown` 中转为专项失败结果，保留完整 LiteParse 输出并
  生成失败报告；成功与 best-effort 报告都只记录实际应用的 `specialistPlacements`。
- 完整回归：`uv lock --check`、compileall、`git diff --check` 均通过；`pdf-to-markdown` 与
  `pdf-table-5` 合计 76 passed。新增回归覆盖非法 source-confirm 不终止 repair、专项整体异常
  降级，以及未验证时仍写 `output.md`/最终失败报告；所有相关手写 Python 文件不超过 200 行。
- Badenova 现有项目恢复复跑通过：`table_0003` 从原 in-flight attempt 恢复，确认结果正确返回
  `totalRows=24`、尾部索引 21/22/23 并 accepted；最终 9 张专项表全部 verified，39 个候选状态为
  1 个 `liteparse_verified`、34 个 `specialist_verified`、4 个 `specialist_no_table`。
- Badenova 最终 `accepted:true`，总耗时 516102 ms；failed/unmatched 列表均为空。`output.md` 为
  86672 bytes、包含 14 个 Markdown 表格块和 67 个均存在的相对图片引用，无运行事务标记；第
  33–57 页长表作为单个专项表完成回填。
- 按 PDF 视觉验证流程检查源第 18、33、57 页：第 18 页 23 条数据与确认 sample 的
  `totalRows=24` 一致；长措施表从第 33 页编号 12 延续至第 57 页编号 197，专项 CSV 为 185 行
  （1 header + 184 data）、11 列，首尾编号与页面一致，未见边界截断。
- 七目录诊断：最外层报告均为 `accepted:false`。Celle 与 Westnetz 的 Agent 分别生成语法损坏和
  运行越界的 `sample.py`；repair 在校验 proposed sample 前先执行坏的 current sample，异常逃逸并
  中止整个 `pdf-table-5`，导致该 PDF 的全部专项候选被标为 workflow 失败。
- MVV、Rostock、TraveNetz、WSW 均完成专项流程，但各有一张表三轮 repair 后仍未通过。MVV parser
  主动删掉正确表头 `Bestand`；Rostock 只差日期范围连字符前后的空格；TraveNetz 是嵌入位图 OCR
  的空格、大小写和变音字符错误；WSW parser 错把 `in Industrie enthalten` 重复到备注列所有行。
- MVV 与 WSW 的第三次（最后一次）repair 都试图修改正确的 `sample.py` 以迁就错误 CSV；独立源确认
  返回 `keep_current`，但当前状态机仍把这次被否决/未收敛的修复计为已完成并立即耗尽 repair 预算，
  没有携带确认结论再修 parser 的机会。这是两份文档未收敛的共同状态机原因。
- SWE 旧的顶层报告记录第 16 页源图横向截断、无法可靠读取完整表头/行数；其后又启动过一次专项
  恢复但未完成，`states.json` 时间晚于顶层报告且停在 `parse-table_0002`，因此项目同时含有旧报告
  和新一轮半成品状态。源页本身含遮黑且右侧表格被页面边界截断，不能安全臆造缺失内容。
- 发现页面级回填的事务边界仍不完整：MVV、Rostock、WSW 的失败专项表与通过表位于同页；当前
  `plan_replacements` 只过滤失败 CSV，却让同页通过表消费该页全部 LiteParse span，最终把失败表的
  LiteParse 兜底一并删除。建议先实现“页级原子提交”：同页存在任一失败/不可验证专项表时，该页
  不应用任何专项替换并保留完整 LiteParse；之后再处理单表 repair 与图像表分类。
- 已实现关联页组原子回填：失败表所在页以及被跨页 accepted 表连接到的页面全部阻止专项替换，
  保留完整 LiteParse；报告新增 `blockedSpecialistTables`、`blockedSpecialistPages`。
- 非法 proposed sample 记为 `rejected_invalid_proposed` 并继续 repair；current sample 已损坏时由
  source-confirm agent 从源证据重建，不再抛出终止工作流。prepare/Parser/Repair/Review 的未预期
  异常按表隔离，最终复核也不会让一张表中止其余表。
- 连字符左右仅空格不同会确定性记录为 `ignore_space_hyphen` 等价；Parser 提示词要求 geometry
  出现 OCR 污染时核对可见 crop，并禁止仅因缺少网格线就把邻近备注传播到整列。
- 本轮没有加入自动清理旧运行目录的产品行为；只会按用户要求在 SWE 真实测试前清理其指定旧产物。
- 第一轮七份真实测试表明仅在提示词中要求回看 crop 仍不足：恢复 Parser session 的 Repair 原本传入
  空图片列表，TraveNetz 和 WSW 仍受 OCR 错字影响。现改为每轮 Repair 重新附加表格 crop，并要求
  Agent 返回前执行候选 parser、逐项消除 review 中的 sample mismatch；随后针对两份 OCR 型失败复测。
- 最终七份真实测试：Celle、MVV、Rostock、TraveNetz、WSW 均为 `accepted:true`；TraveNetz 与
  WSW 在重新附带 crop 后复测通过，分别完成 6 张和 3 张专项表回填，失败、阻塞、未匹配列表均为空。
- SWE 与 Westnetz 均跑完整流程并生成 `output.md`/`report.json`，但保持 `accepted:false`：SWE 第 16 页
  源表在 PDF 页面边界处物理截断，Westnetz 第 23 页仍有一格无法从可见证据可靠确认。两者均触发
  页组原子回退，分别阻塞第 16 页和第 23 页的专项替换，保留完整 LiteParse 兜底内容。
- SWE 测试前仅将指定旧运行目录移动到系统废纸篓（可恢复），随后在原路径生成新产物；未实现任何
  自动删除旧产物的运行时逻辑。
- E-Netz Südhessen 第 25 页进一步确认：表格单元格不是原生 PDF 文本，而是一张约 182 DPI 的嵌入
  JPEG；页面上仅标题、表注和页脚属于原生文本。旧分类以整页 word 数判断，因表注的 10 个 words
  误判为原生表格，现改为检查目标表格区域的图片覆盖率以及图片区域内的原生 words。
- 最终采用精简方案：保留表格区域级的 JPEG 分类修复，回退 OCR 静态阻断、图像小表全行采样、
  source-confirm 扩展和 Repair artifact 快照。Parser 提示词明确：`imageTable=true` 时由 Parser LLM
  直接读取并完整转录截图，使用 sample skip 和 format-only review；截图不完整或不清楚时先扩大范围
  或提高 DPI。`imageTable=false` 时仍沿用 PDF words/geometry 和 content sample 流程。
- 精简方案回归通过：`uv lock --check`、compileall、`git diff --check` 均通过，`pdf-to-markdown` 与
  `pdf-table-5` 合计 83 passed。新增分类回归覆盖“大图 + 表外 caption words”仍判为图像表格、图片
  区域存在原生 cell words 时判为非图像表格，以及小 logo 不触发图像表格。
- 仅对用户指定的 E-Netz Südhessen PDF 做最终重跑，报告 `accepted:true`，17 个候选中 9 个
  `specialist_verified`、3 个 `liteparse_verified`、5 个 `specialist_no_table`，失败、阻塞、未匹配列表
  均为空，总耗时 810845 ms。第 25 页分类为 `imageTable:true`（图片覆盖 0.8184，图片区域原生 words
  为 0），Parser LLM 直接转录 15 行数据，Review 为 `format_only`、sample 为 skip。
- PDF 视觉核对确认第 25 页截图边界完整，最终表格保留 `Sanierung von MS/NS-Stationen` 与数值 `1,89`。
  该页专项替换后仍残留 LiteParse 对同一 JPEG 的表格外乱码；未增加产品逻辑，只对本次最终
  `output.md` 做一次性清理，并同步 `report.json.outputSha256` 为最终文件哈希。
- enercity Tabelle B.3 失败确认是合并单元格语义冲突：视觉上横跨四个年份列的 `1 (0)` 被确认
  Agent 按 glyph 横坐标误拆成空、`1`、`(0)`、空。现仅强化 Parser/source-confirm/Repair 提示词：
  合并单元格以可见边框为准，glyph 坐标不表示覆盖列归属，sqlFriendly 输出须在所有覆盖列重复完整值。
- 合并单元格提示词修复回归：针对 prompt/source-confirm 的 13 项测试通过；`pdf-to-markdown` 与
  `pdf-table-5` 完整回归仍为 83 passed，`uv lock --check`、compileall、`git diff --check` 均通过。
- 按用户要求将 EAM 既有运行目录移入系统废纸篓（原 PDF 保留），随后由全新 Terra 子 Agent 从
  空产物状态执行 `packages/pdf-to-markdown/skills/SKILL.md` 的完整转换与验收。
- EAM 全新运行已跑完整流程并生成 best-effort `output.md`/最终报告，耗时 5,184,398 ms（约 86 分
  24 秒），结果 `accepted:false`。71 个候选中 62 个 `specialist_verified`、3 个 no-table、3 个
  failed、3 个 blocked；`unmatchedSpecialistTables` 为空。专项失败为 `table_0003`（Agent 生成的
  `sample.py` 错把 `add_argument()` 返回值当 parser 调用 `parse_args()`，三轮未修复）和
  `table_0013`（表头单位 `[km]` 在 Parser 与 sample 间不一致）。页组原子回退因此阻塞第 33、
  43–47 页；其余 accepted 表已正常回填，包括第 78–108 页的 31 页长表和第 111–113 页长表。
- enercity Tabelle B.3 的 source confirmation 已正确确认合并单元格应在四个逻辑列重复 `1 (0)`，
  但 Repair Agent 把 mismatch 的左右值看反，误以为实际 CSV 已正确并连续返回 no-op。Parser/Repair
  固定提示词现明确 mismatch 为 `expected sample != actual CSV`，右侧才是当前 parse.py 输出。
- 复用 enercity 既有专项项目恢复外层编排，未重新调用 Finder/Parser 全量识别；74.173 秒后报告转为
  `accepted:true`。第 15 页 `table_0002` 已替换 LiteParse `table_0007`，最终 `Laufwasser` 行四个
  enercity 年份列均为完整 `1 (0)`。37 个候选中 1 个 `liteparse_verified`、23 个
  `specialist_verified`、13 个 `specialist_no_table`，failed、blocked、unmatched 列表均为空。
- enercity 最终 Markdown SHA-256 为
  `e900f319bbbd5bc2f4c09edb2ca67dfba30d57339d3b9468dce7dfd12b31fa93`，与正式报告一致；图片引用
  缺失数为 0，且无残留事务标记。目录根部旧的异构报告已移入废纸篓，并用正式 `work/report.json`
  同步替换，避免两个报告继续冲突。
- Parser 固定提示词增加最小防误跳过规则：标题或 caption 中出现 `Abb.`、`Figure`、`Screenshot`
  不能成为跳过可见结构化行列的依据；只有图片确实不含目标表格数据时才允许 skip。未修改 Finder、
  页面替换或报告逻辑，并新增固定提示词回归测试。
- SWE 旧 `work/specialist` 已移动到系统废纸篓
  `swe_netz_erfurt-specialist-2026-08-11`（可恢复），保留原 PDF、LiteParse、assets 与其他运行产物；
  随后从当前代码重新生成专项结果。第 16 页新分类为 `imageTable:true`，图片覆盖率 0.8813，图片区域
  原生 words 为 0；Parser 直接视觉转录并生成两张 format-only accepted 表，分别为 5 行变压器数据和
  2 行线路数据，且排除源图片右侧物理截断的残缺列。
- SWE 重跑最终 `accepted:true`，11 个候选中 7 个 `specialist_verified`、1 个
  `liteparse_verified`、3 个 `specialist_no_table`，failed、blocked、unmatched 均为空，总耗时
  551440 ms。第 16 页两张表共同替换 LiteParse 的 `table_0005`、`table_0006`，原嵌入图片仍保留；
  图片周围仍有少量 LiteParse 散落 OCR 文本，本轮按最小改动范围未增加清理算法或手工改最终产物。
- 本轮完整回归为 84 passed；`uv lock --check`、compileall、200 行限制及 `git diff --check` 均通过。
- 按用户要求对 SWE 最终产物做一次性人工清理：删除第 16 页图片与专项表之间的 `Mor lef`、孤立
  数值等 OCR 碎片，以及第二张专项表之后的残缺标题/表头；保留原图、两张专项表、图注和正文。
  `output.md` 新 SHA-256 为
  `1a9a602c7949cc88354fc617b6f3ed2de8ca9b3a7dbafc7b585ba7ba1708f11b`，已同步正式 `work/report.json`。

## 文档检查

- 已检查并更新根 README 导航、wiki 导航、`wiki/user/pdf-to-markdown.md`、包 README、skill 和本任务记录。
- 当前行为、CLI 路径、默认 skill 输出位置和验收报告位置一致。
