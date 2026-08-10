# PDF Table 5 AI workflow

- 状态：等待人工审核
- 日期：2026-08-09

## 用户原始请求

> 实现 reIndex/packages/pdf-table-5/readme.md， 之后调用一个在agent 以eIndex/testbase/test5-table5/sws-netze-solingen-2024/sws_netze_solingen_gmbh_netzausbauplan_2024_pdf.pdf 做第一轮测。 先看下你有没有问题。
>
> 1， 对  2. 对。 另外测试用的子 agent 用 5.6 terra。

## 后续优化请求（2026-08-09）

> 优化 Finder、Merge、Parser：把必要文件的完整且精简内容直接放入提示词，并把必要图片
> 作为初始输入；正常路径不再让 agent 自行发现、读取、执行或校验文件。默认子 agent 使用
> `gpt-5.6-terra`、中等 reasoning。Finder 只给带大边距的近似 bbox；`yes` 和 `no`
> 确定性处理，只有 `possible` 启动 Merge。Parser 不读 Skill/AGENTS，不执行 sample lock、
> parse、CSV/JSON/编译/行数/git/cache 校验；生成的 parse 代码不受 200/300 行限制。
> 不增加工具次数硬限制、不并行 Parser、不做 strategy 确定性试跑；重点通过完整精简的
> `parseXXX.json` 上下文和建议步骤减少 shell、token 与时间，并报告优化内容和预计降幅。

## Sample 原始值确认请求（2026-08-09）

> 初始采样时对存在断行连字符风险的列直接添加按列规则。普通 Parse Repair 可以修改 sample rule；
> 如果要修改 sample 原始值，必须找一个新 agent 根据 PDF 来源独立确认。方案保持简单。实现后由
> 子 agent 使用 `reIndex/testbase/test5-table5-2/e-dis-2024` 做一轮测试。

- 初始 Parser 提示要求检查每个文本列，对 PDF 换行造成空格/连字符不稳定的列立即添加
  `ignore_space_hyphen`；规则必须包含非空 `columns`，通常以空 `rowIndexes` 覆盖整列。
- Repair 提交 `samplePy` 后，调度器分别执行当前和建议脚本。去掉 `compareRules` 后原始 sample
  完全相同则直接接受规则修改；mode、totalRows、header、rows 或 skipReason 有变化时启动新 agent。
- 新 source-confirm agent 只接收当前 sample、变化位置、PDF crop、源 geometry 和 source PDF 路径，
  不接收 CSV actual、parse.py 或 Repair 建议值。确认结果持久化到 `sampleConfirmation.json`，并作为
  后续原 Parser session 的权威来源反馈；Agent 仍保留重新查看 PDF、geometry 和截图的工具能力。
- 本地定向回归 27 passed，package 全套回归 41 passed；`uv lock --check`、`git diff --check` 通过。
  所有新增/修改仓库手写 Python 不超过 200 行。

## 第二轮优化流程测试请求（2026-08-09）

> 创建一个新子 agent terra 5.6 以
> `reIndex/testbase/test5-table5-1/sws-netze-solingen-2024` 为例进行一轮测试。

- 使用独立 `gpt-5.6-terra`、medium reasoning 子 agent，从该目录内源 PDF 初始化并完成一轮。
- 不复用旧 `test5-table5` 的表格产物；记录实际总耗时、逐阶段耗时、token、Agent Shell 次数、
  表格数量、repair 情况及最终 verify 结果。

## Repair 原因诊断请求（2026-08-09）

> 为什么会 这么多 repair，原因是什么，为什么 repair 失败了

- 只读还原每次初始 Parser、review 和 repair 的失败链路，区分数据/坐标问题、产物结构问题、
  repair 提示与验证反馈问题，以及异常恢复造成的重复调用；本轮不修改实现或生成产物。

## Repair 修复方案请求（2026-08-09）

> 1. 前面应优化提示词，而不应把子 agent 限制在不能重新解析 PDF、截图或有效修复的沙箱中。
> 2. 解决 geometry 读不到的问题，直接在提示词里下发。
> 3. 给 Parser 嵌套输出增加 schema 约束，并解决 Repair 重写全部产物。
> 4. geometry 不可见可能误导 imageTable；vector 表格不能以 format_only accepted，解析失败应
>    标记 failed，继续其他表并在最后列出失败表格。
> 5. 修复 Resume 重置 repair 次数，并确认 repair 应恢复旧 agent、不是调用新 agent。
> 6. 提高 prompt cache 命中：固定规则、schema、loader contract 前置，table id、attempt 等动态
>    内容后置。

- 本阶段先提交修复方案，不改实现；用户确认后再实施和重新测试。
- 计划取消临时 `read-only` cwd，改为项目根目录 `workspace-write`，保留 shell/PDF/截图/执行能力；
  每表首次 Parser 建立持久 Codex session，Repair 优先 `codex exec resume <session_id>`。
- Prompt 固定前缀统一放严格 sample/summary schema、runtime loader contract、工具建议和验证规则；
  动态 table/context/review/attempt 放后缀。geometry 同时给绝对路径、项目相对路径、word count 和
  可复制 loader 示例。
- Parser 初始输出使用深层 typed object schema；Repair 使用 nullable field-level patch 与 base hash，
  调度器只合并非空变更，拒绝无关 artifact 重写。
- `imageTable` 改为调度器确定的严格 boolean；vector table 的 `format_only` 不 accepted。超过累计
  repair budget 后表状态为 failed，流程继续，最终报告列出 failedTables 并令整体 accepted=false。
- 每表 session id、累计 repair attempts、in-flight attempt 和 artifact revision 持久化；resume 不再
  重置次数，会话不可恢复时才显式 fallback 到新 agent，且不额外增加 repair budget。

## 第三轮性能优化与测试请求（2026-08-09）

> 按这个优化吧，优化完后再找一个 子agent 以reIndex/testbase/test5-table5-3/sws-netze-solingen-2024/sws_netze_solingen_gmbh_netzausbauplan_2024_pdf.pdf 做测试

- 实施上一轮实测报告中的优先项：确定性消除已知 geometry/sample repair，正常 Parser 采用内联
  上下文直接返回的建议路径，减少 Skill/仓库发现、scratch file-change、重复图片和 Resume 重复前缀。
- 保持 Parser 顺序执行、`gpt-5.6-terra` medium、完整工具能力与严格 vector 内容门槛；优化后用全新
  子 agent 对 `test5-table5-3` 从源 PDF 执行完整测试，并记录逐阶段时间、token、Shell 与质量结果。

## Bielefelder Netz 扩展测试请求（2026-08-09）

> 找子 agent 测试 reIndex/testbase/test5-table5/bielefelder-netz-2022/2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf 这份

- 使用全新 `gpt-5.6-terra`、medium reasoning 子 agent，从仅含源 PDF 的目录执行一次完整
  `pdf-table-5 all`；不手工修改 agent 产物。
- 记录逐阶段耗时/token、表格发现与合并、Repair/session、Shell/file-change、最终严格 verify 和
  CSV 尺寸；主 agent 独立复核报告、事件日志、生成项目 verify 及相关 PDF 页面。

## Bielefelder 空行与进一步优化请求（2026-08-09）

> `reIndex/testbase/test5-table5/bielefelder-netz-2022/output/table_0001.csv` 的第 51 行有个空行。
> 另外检查提高速度、减少 token 和提高质量的优化空间。

- 核对该空行与源 PDF、geometry、Parser/Repair 产物及事件链，修正当前 fixture，并修复通用质量门。
- 分析本轮 Repair 的耗时、input token 与 Shell 回合放大原因，给出并实施不削弱工具权限和内容检查的
  优化；完成后记录实际验证结果和预期收益。

## E.DIS 2024 扩展测试请求（2026-08-09）

> 再找个子agent (terra)试下
> `reIndex/testbase/test5-table2/e-dis-2024/e_dis_netz_gmbh_netzausbauplan_2024_aktualisiert.pdf`

- 使用一个全新的 `gpt-5.6-terra`、medium reasoning 子 agent，在源 PDF 所在目录执行一次完整
  `pdf-table-5 all`；不手工干预中途产物。
- 主 agent 独立复核 CLI/generated verify、CSV 结构与内容、相关 PDF 页面、逐阶段耗时与 token、
  Repair/session、Shell/file-change，并把结果记入本任务。

## sample.py 与连续大表简化请求（2026-08-09）

> repair 可以修改 sample， 不然万一 sample 提取错了后面就完蛋了。sample.json 都改成
> sample.py 统一输出，没规则的直接输出 json 就行。另外具体实践上步骤不要过度保守：连续大表
> 第一轮只给首段和尾段完整数据，让同一套代码直接运行全部中间段，失败后再按需诊断。
>
> 实现吧， 并找个新子 agent 用
> `reIndex/testbase/test5-table5-1/e-dis-2024/e_dis_netz_gmbh_netzausbauplan_2024_aktualisiert.pdf`
> 进行测试。

- 所有 Parser 统一返回 `samplePy`；调度器执行 `sample.py --table-json ...` 并从 stdout 读取 sample
  JSON。无特殊规则时脚本直接输出原 sample JSON；可选 `compareRules` 用于受控连字符等价比较。
- Repair 继续使用 revision patch，允许按诊断修改 `samplePy`、`parsePy` 或两者，并归档发生变化的
  旧 sample 脚本。
- 多段连续大表初始 Parser 只内联首段、尾段的完整 geometry 并附加两张裁剪图；中间段只给路径、
  页码、bbox 与计数。生成脚本在运行时通过 loader 处理全部 segments，失败时 Agent 仍有完整工具能力。
- 实现和单测完成后，使用全新的 `gpt-5.6-terra`、medium reasoning 子 agent 对指定 E.DIS PDF
  执行一轮完整测试，记录结果、耗时、token 与 Agent Shell。

## 范围与确认

- 按 `packages/pdf-table-5/readme.md` 在该目录实现通用工作流，不把 Python 逻辑写入 Markdown。
- 生成项目的根目录为 PDF 所在目录，包含 `parse/` 与 `output/`。
- 首轮 Finder、Merge、Parser agent 通过 Codex CLI 调度并拥有完整读写权限。
- 修复后运行时 agent 在项目根目录使用 `workspace-write`，保留按提示词读取 geometry/PDF、截图、
  编写 scratch parser 和执行诊断的工具能力；必要上下文与图片仍由调度器直接下发，正式产物继续由
  调度器依据结构化返回写入并校验。
- 实现完成后，由一个 `gpt-5.6-terra` 独立子 agent 对指定 PDF 做首轮测试。
- 不借鉴仓库内旧测试项目的流程；不改动无关的既有工作树内容。

## 验收检查

- `parse/main.py` 对外提供 `execute()` 和 `verify()`。
- 调度可初始化、恢复并记录步骤、耗时、异常、模型与 token 使用。
- PDF 页码与 bbox 均使用 1-based visual-page 坐标系。
- Finder、可选 Merge、逐表 Parser、review/repair 和最终重跑流程可执行。
- 最终 CSV、`output/finalTable.json` 和 `parse/report/` 可生成。
- 自动化测试通过，并完成指定 PDF 的首轮 agent 测试。

## 实现记录

- 新增独立 `pdf-table-5` workspace package、CLI、生成项目公开 API、PDF visual-page
  坐标/截图工具、Codex agent 调度、状态与步骤日志、Finder/Merge/List/Parser/Review/Report
  全流程。
- 首轮实现曾用 SHA-256 lock 固定 `sample.json`；后续按优化请求移除 lock，但继续按
  sample-first 顺序写入并静态拒绝 Parser/strategy 引用验证与既有输出。
- 首轮 Finder 找到 6 个片段，Merge 合并第 16-17 页续表后得到 5 张逻辑表；全部为
  矢量表并通过格式与 sample 内容验证。
- 首轮发现第 16 页 Finder bbox 截断边界行 8。Parser 从源 PDF vector words 恢复该行；
  通用实现随后开始实际应用 `bboxMarginPt`，默认 36pt，并在 table packet 同时保留
  `sourceBbox` 与扩展后的 `bbox`。确定性恢复重跑确认扩展 geometry 包含行 8；本轮新项目
  默认进一步提高到 72pt。
- 首轮还修复了 Codex CLI 返回 0 但缺少 terminal event 的静默成功、字符串形态
  `surroundingText` 的汇总兼容，以及未捕获异常没有把状态设为 failed 的问题。
- 后续性能优化把 Finder/Merge/Parser 改为 Codex CLI structured output：调度器把必要 JSON
  内容直接内联，并把图片复制到独立临时目录后通过 `--image` 附加；运行时忽略用户配置，
  使用只读 sandbox 和 ephemeral 会话，默认显式指定 `gpt-5.6-terra` + medium reasoning。
- Finder context 内含每页视觉尺寸与实际图片像素尺寸，只要求带 72pt 以上安全边距的近似
  bbox；不再要求 agent 读取文件、探测 PDF 库、提取文字块或自行校验输出。
- Merge 只处理 `possible`；`yes` 确定性并入前组，`no` 确定性分组。Merge 仅返回 possible
  pair 的布尔决策，最终 mergeTable 由调度器生成和校验。
- 每表新增完整精简的 `parserContext.json`：保留当前 table packet 必要字段、bbox 内全部 word
  的紧凑数组、附件映射、runtime geometry shape，以及 strategy 文档与公开签名。Parser 只返回
  sample/summary/parse/可选 strategy；调度器按 sample-first 顺序落盘，再执行和 review。
- 移除 sample lock helper、CLI 和 review hash 依赖；Parser/strategy 仍被静态限制为不读取
  sample、summary、review 或 finalTable。生成的 parse/strategy 不设 200/300 行限制；仓库手写
  源码继续遵守全局规则。修复时 sample 真有变化才自动归档为 `sampleN.json`。

## 首轮结果

- 独立测试 agent：`gpt-5.6-terra`。
- Finder/Parser 首轮使用当时 Codex 配置的默认 `gpt-5.6-sol`；优化后改为显式默认
  `gpt-5.6-terra` + medium，仍记录模型与 reasoning effort。
- 状态：5 `verified`，0 `format_only`，0 `skipped`，0 `failed`，`accepted=true`。
- CSV 尺寸（含表头）：`6x3`、`8x6`、`7x4`、`7x4`、`14x16`。
- 首轮报告耗时：2,148,576 ms（35m48.576s）。
- 首轮 token：input 5,814,312；cached input 5,397,504；output 85,896；reasoning 42,882。

## 验证记录

- `uv run --package pdf-table-5 pytest packages/pdf-table-5/tests -q`：优化后 16 passed。
- `uv run --package pdf-table-5 pdf-table-5 run testbase/test5-table5/sws-netze-solingen-2024`：
  最新 bbox/汇总修复恢复重跑，5/5 verified。
- `uv run --package pdf-table-5 pdf-table-5 verify testbase/test5-table5/sws-netze-solingen-2024`：
  `accepted=true`，5/5 verified。
- 独立 Terra agent 另行调用生成的 `parse/main.py::verify()`：`accepted=true`，5/5 verified。
- `uv lock --check`、`python -m compileall` 和 `git diff --check` 通过。
- 真实最小 Codex CLI structured-output smoke：`gpt-5.6-terra`、medium，6.9 秒，返回
  `{"value":"ok"}`；input 15,289，output 15，terminal event 完整。
- 旧首轮 fixture 在不启动新 agent 的恢复路径上重新执行并 verify：5/5 verified。
- 所有新增/修改的仓库手写 Python 文件不超过 200 行；生成 parse/strategy 不再受该限制。

## 优化量估算

- 指定首轮文档的新 Finder + 5 个 Parser prompt 共 76,526 字符；旧 Finder/Merge/Parser 的
  prompt 加 shell 命令/输出可见文本约 304,708 字符，直接上下文材料减少约 74.9%。
- 最复杂 table_0004 的两份原 geometry 为 112,943 字节；完整紧凑 evidence 为 28,855 字符，
  减少约 74.5%，同时不丢 word、bbox、block、line、word index。
- 该 PDF 中唯一续页为 `yes`，优化后不启动 Merge，直接消除首轮 133.888 秒和 446,888
  input token。
- 基于 6 个正常路径单轮 structured agent、15,289-token CLI 固定基线、实际 prompt 尺寸和
  图片附件数量，预计完整新首轮约 0.2M-0.6M input（较 5.814M 降低约 90%-97%），耗时约
  8-15 分钟（较 35:48 降低约 58%-78%）。这是未做第二次昂贵端到端重跑前的区间估计；
  repair 次数和视觉复杂度会影响实际值。

## 第二轮优化流程实测

- 独立测试 agent：`gpt-5.6-terra`、medium reasoning；输入为新目录内唯一源 PDF，未复用旧
  `test5-table5` 表格产物。
- Finder 得到 6 个 segment；`find_0005 -> find_0006` 为 `yes`，确定性合并为 5 张 logical
  table，Merge agent 调用为 0。
- pipeline CLI 墙钟合计 1,201.02 秒（20m01.02s），最终 report 记录 1,200.298 秒；相对旧
  2,148.576 秒减少 44.10%。实际高于 8-15 分钟预计，主要来自 12 次 repair 及恢复时重复处理
  failed 表。
- 20 份 agent event log 合计 token：input 628,814、cached input 193,024、output 54,646、
  reasoning 10,416；较旧基线分别减少 89.19%、96.42%、36.38%、75.71%。最终 report 的成功
  workflow 口径为 556,521 / 193,024 / 53,132 / 9,972。
- 所有 Finder、Parser、Repair event 中 `command_execution` 总数为 0；`yes` 续页也未启动
  Merge agent，因此正常运行 agent 没有 Agent Shell 命令。
- CSV 尺寸（含表头）：`6x3`、`8x6`、`7x4`、`7x4`、`1x16`。CLI `verify` 与生成
  `parse/main.py::verify()` 均返回 `accepted=true`，但 5/5 都仅为 `format_only`、
  `contentPassed=false`，没有 `verified`；最后一表只有表头，属于需要后续收紧的质量门槛。
- 实测暴露并修复三处通用阻断：不足 1pt 的整点 bbox 与 PDF 小数页边界差异；review 对非对象
  sample row 无类型防御；自然语言 `summary.strategy` 被当作路径导致文件名过长。三处均补回归，
  未手工修改 CSV、sample 或 report。
- 主 agent 独立复核：package 全套 `19 passed`；CLI verify 与生成模块 verify 均复现上述结果；
  event log 复算为 20 turns、0 command execution，token 与报告一致。

## Repair 原因诊断

- 12 次 repair 分布为 `table_0000=6`、`table_0001=1`、`table_0002=1`、
  `table_0003=2`、`table_0004=2`；累计 837.593 秒。其中 7 次之后的 review 仍失败或异常，
  5 次最终进入 accepted，但没有一次达到 `verified`。
- 首要共因是 runtime geometry 路径语义不闭合。`table.json` 保存的是相对项目根目录的
  `parse/tables/.../segment.json`，生成 parser 普遍按 `table.json` 所在表目录拼接；实测前者均存在、
  后者均不存在。各 segment 实际含 134-364 个 vector words，但 parser 因路径错误得到 0 words。
- Prompt 只描述字段概念，Codex structured schema 只约束五个顶层字符串，未约束字符串内嵌
  sample/summary JSON。五个初始 sample 都用了 `columns` 而非 `header`；三个 summary 用
  `evidenceBasedSteps` 而非 `steps`；repair 又把 sample row 从 `{rowIndex,values}` 改成裸数组或
  任意列名对象，且多表把 `totalRows` 当数据行数而非含表头行数。
- `imageTable` 未约束为 boolean，也未定义语义。agent 分别返回 `true`、附件名、附件数组或对象；
  review 用 `bool(imageTable)` 判定，因而跳过 content comparison。视觉页和 geometry 证明五张表
  都是含完整 vector words 的文本表，不应被当作 image-only table。这使表 3 的硬编码 fallback、
  表 4 的仅表头 CSV 均成为 `format_only accepted`。
- Repair agent 不运行代码，只收到通用的 “extracted 0 rows”；生成 parser 又静默忽略不存在的
  geometry 路径，所以反馈没有解析后的候选路径和 word count。table 0000 前五次依次误判为
  compact-word 格式、page/bbox filter、row anchor 或语法问题，第六次才搜索父目录并找到 geometry。
- repair 每次返回全套 artifacts，即使只需修 sample/summary，也会重写原 parse.py；因此
  table 0003 的结构修复引入 “No geometry words”，table 0000 的一次修复引入 SyntaxError，
  table 0004 的修复引入非法 sample rows。
- `maxRepairAttempts` 是每次 `Workflow.run()` 的局部循环，不持久化累计次数。两次调度器异常恢复
  后，failed 的 table 0000 又获得三次 repair，令总数从不中断情况下的 9 次放大到 12 次。
- 优先修复方向：提供调度器拥有的确定性 geometry loader/绝对路径；把完整 sample/summary schema
  及类型放入上下文并在调用后立即深校验；`imageTable`/skip-content 由调度器确定且文本表不得
  `format_only accepted`；repair 只替换出错字段并返回已解析路径与 word count 等紧凑诊断；
  持久化每表 repair budget，恢复时不重置。
- 本轮仅诊断并更新任务记录，未修改实现、生成 parser、sample、CSV 或 report；当前 README、wiki、
  CLI/HTTP contract 没有因诊断发生行为变化，无需文档或契约更新。

## Repair 修复实施记录

- 移除 `--ephemeral`、临时 cwd 和 `read-only`；agent 在项目根目录 `workspace-write` 中运行，可按
  提示词精确路径读取 PDF/geometry、执行 parser、截图，并使用每表 report scratch。正式 artifacts
  仍由调度器根据结构化返回原子写入。
- Parser 首次调用建立持久 session 并保存 session id；Repair 优先 `codex exec resume <session_id>`，
  仅恢复命令失败时在同一 attempt 内 `fallback-new` 并记录原因。
- `parserContext.json` 新增 projectRoot/sourcePdf/tableDir/tableJson/scratch/testCommand，以及每份
  geometry 的 project-relative/absolute path、word/image count；`table.json` 同时写 projectRoot。
  Prompt 固定前缀给出可复制 loader，明确路径相对 projectRoot、已知 wordCount>0 时零 words 是
  loader failure，不得判图像或使用完整硬编码 fallback。
- Parser structured output 将 sample/summary 从 JSON 字符串改为严格嵌套对象；约束 rowIndex/values、
  totalRows、严格 boolean imageTable、summary 字段类型和 strategy filename。调度器用实际 word/image
  count 覆盖 imageTable，agent 无权放宽。
- Repair output 改为 `{diagnosis,baseRevision,changes}`；五个 change 字段均 nullable，调度器只合并
  非 null 字段并检查 artifact revision。修复 metadata 不再重写 parser，修代码不必改变 sample。
- `states.json` 持久化每表 parserSessionId、repairAttemptsStarted/Completed、inFlightAttempt、
  artifactRevision 和 fallback 信息；workflow resume 使用累计 budget，不从零开始。
- Review 深校验 sample/summary；vector sample 不得 skip，vector `format_only` 永不 accepted；只有
  调度器确认的 image-only table 可 `format_only`。修复耗尽标记 failed、继续其他表，report 新增
  failedTables 并令整体 accepted=false。
- Prompt 统一稳定前缀，动态 operation/table/review/attempt 放在 canonical JSON 后缀；同表 Repair
  恢复旧 session，只发送 review、revision、路径等 delta，fallback 才携带完整 context/artifacts。
- 本地验证：package `27 passed`；JSON Schema Draft 2020-12 检查通过；真实 Terra medium Codex CLI
  smoke 确认深层 Parser schema 与 nullable Repair schema 均被接受，Repair session id 与 Parser 相同。
- 文档同步：更新 package readme 的权限、工具、geometry、session、field patch、strict review、失败
  报告和状态语义；根 README 移除已过期的 locked-sample 描述。未改变 ReIndex HTTP/CLI v1 contract。

## 修复后 Terra 独立实测

- 使用全新 `gpt-5.6-terra`、medium reasoning 子 agent，对
  `testbase/test5-table5-1/sws-netze-solingen-2024` 从仅保留源 PDF 的状态执行完整 `pdf-table-5 all`；
  测试前旧生成物可恢复地移至 `/tmp/pdf-table-5-before-fix.zIT39V`，没有混用上一轮产物。
- Finder 识别 6 个 segment，并将第 16-17 页续表确定性合并为 5 张 logical table；续页为 `yes`，
  Merge agent 调用为 0。最终 `verified=5`、`format_only=0`、`skipped=0`、`failed=0`，
  `accepted=true`，5 张表的 `formatPassed/contentPassed` 均为 true。
- CSV 尺寸（含表头）为 `6x3`、`8x6`、`7x4`、`7x4`、`14x16`。主 agent 又独立执行 CLI
  `verify`、生成项目 `parse/main.py::verify()` 并对照第 6、10、13、14、16、17 页截图，结果一致。
- 本轮报告耗时 861,238 ms（14m21.238s）；相对最初 35m48.576s 减少约 59.9%，相对上一轮
  20m01.02s 减少约 28.3%。
- 本轮 token 为 input 1,720,151、cached input 1,206,528、output 66,435、reasoning 9,466；
  cache 命中占 input 70.14%。相对最初 input 5,814,312 减少约 70.4%；但相对上一轮 event-log
  input 628,814 增加约 173.6%，主要来自恢复会话携带历史和 4 次严格内容 repair。
- Repair 分布为 `table_0000=0`、`table_0001=1`、`table_0002=2`、`table_0003=1`、
  `table_0004=0`。4 次全部为 `sessionMode=resumed`，使用各表原 Parser session；session fallback 为 0，
  started/completed 计数分别持久化为 1/1、2/2、1/1，最终无 in-flight attempt。
- `table_0001` 的一次 repair 修正 sample 行索引；`table_0002` 初始 parser 把 word object 当数组，
  第一次 repair 修复类型后列坐标仍为空，第二次修复坐标分组；`table_0003` 同类 object/array 错误在
  一次 repair 中修好。字段级 patch 与 artifact revision 生效，repair 没有无条件重写全部产物。
- Agent event 中实际 `command_execution` 共 14 次：初始 Parser 分布为 3/2/0/0/6，repair 分布为
  0/0/1/2。工具能力恢复后 parser 能自行执行候选代码并检查 geometry；同时仍观察到个别主动读取
  Skill、仓库发现和打印 CSV 的冗余行为，后续可继续用更明确的正向步骤与紧凑诊断入口引导。
- 主 agent 最终回归：`27 passed`；JSON Schema Draft 2020-12 与真实 Terra structured-output/session
  smoke 均通过；`uv lock --check`、`git diff --check` 通过；仓库手写 Python 文件未超过 200 行。

## 文档一致性

- 更新 `packages/pdf-table-5/readme.md` 的安装、CLI、公开 API、Terra medium、上下文内联、
  图片附件、隔离权限、approximate bbox、possible-only Merge、structured Parser 和无 sample
  lock 说明。
- 更新根 `README.md` workspace package 导航；该新增工作流不改变现有 HTTP/CLI v1 契约，
  因此无需更新协议、OpenAPI 或 ReIndex CLI contract 文档。
- 任务保持“等待人工审核”，未归档。

## 第三轮性能优化实施

- 新增 `pdf_table_5.runtime_geometry` 规范 runtime：`load_segments(table_json)` 统一解析 projectRoot、
  geometry 路径以及磁盘 object/compact array word，并始终返回 compact word 数组；segment 明确为
  dictionary，以 `segment["words"]` 访问。`join_word_text()` 统一处理小写断行连字符、
  `MS-/NS-/ONS-` 复合词和独立短横线。
- Parser 初始提示改为正向的直接返回路径：优先使用已内联 evidence 与 crop，由调度器执行；只有
  evidence 冲突、需要重看来源或 Repair 诊断不足时才使用 Shell/PDF/scratch。工具权限仍为项目根
  `workspace-write`，没有恢复 read-only 或禁止工具。
- 初始化项目时仅在不存在用户文件的情况下生成最小运行时 `AGENTS.md`，澄清这是数据提取而非仓库
  开发任务，避免读取 workflow Skill、创建任务记录或修改无关文件；已有用户 `AGENTS.md` 保持不变。
- 初始 Parser 和 fallback-new 每个 segment 只附加 table crop；context 图片以绝对路径按需打开。
  Resume Repair 只发送约 4 KB 动态 delta，不重复约束前缀或图片；fallback 才发送完整 context/crop。
- Parser structured result 落盘前确定性规范 sample：若 agent 返回完整有效超集，则按 contract
  裁剪/排序为所需索引，值不变；缺少任何必要行时仍由严格 Review 拒绝，不降低内容门槛。
- 新增/更新回归覆盖规范 loader 的两种 word 形态、segment 访问契约、连字符拼接、sample 超集规范、
  crop-only 附件、Resume 无重复图片/短 prompt、运行时 AGENTS 生成与用户文件保护。

## 第三轮 Terra 最终实测

- 使用同一个全新 `gpt-5.6-terra`、medium reasoning 子 agent 对
  `testbase/test5-table5-3/sws-netze-solingen-2024` 执行。首个诊断轮发现 segment 属性访问歧义和
  连字符规则后，其完整产物可恢复地移至 `/tmp/pdf-table5-3-diagnostic.s7vxWl`；应用通用修复后，
  从仅剩源 PDF 的目录只启动一次最终 `all`。
- 最终 Finder 识别 6 个 segment，`yes` 续页确定性合并为 5 张 logical table，Merge agent=0。
  结果为 5 `verified`、0 `format_only`、0 `skipped`、0 `failed`，`accepted=true`；CSV 尺寸（含表头）
  为 `6x3`、`8x6`、`7x4`、`7x4`、`14x16`。
- 报告/实际墙钟均为 327,682 ms（5m27.682s）；token 为 input 339,059、cached input 115,712、
  output 18,810、reasoning 3,560。相对上一正式轮 14m21.238s / input 1,720,151 / output 66,435，
  分别减少 61.95%、80.29%、71.69%；相对最初 35m48.576s / input 5,814,312，分别减少
  84.75% 和 94.17%。
- 8 份最终 agent event log 的 `command_execution=0`、`file_change=0`。此前14次 Shell 和8次
  file-change 已全部消除，同时 Agent 仍保留 Shell/PDF/截图能力。
- Repair 仅 `table_0003=1`、`table_0004=1`，均恢复各自原 Parser session，fallback=0；累计次数为
  1/1、artifact revision=2、in-flight=null。前者修正跨行 Zeitraum cell 分配，后者修正 UA 标识中
  独立短横线后的空格；其余三表首次通过。
- 逐个 Agent 耗时：Finder 34.670s；Parser 0000-0004 分别 29.574s、38.081s、31.127s、35.536s、
  90.491s；Repair 0003/0004 分别 31.302s、33.835s。全部 Review 1.055s，最终报告 0.516s。
- 主 agent 独立执行 CLI `verify` 和生成项目 `parse/main.py::verify()`，两者均 5/5 accepted；对照第
  6、10、13、14、16、17 页视觉检查，并抽查 Zeitraum、UA、MS/ONS 复合词，内容一致。
- 最终回归为 `33 passed`；Parser/Repair JSON Schema Draft 2020-12、`uv lock --check`、
  `git diff --check` 及仓库手写 Python 200 行限制均通过。

## 第三轮文档审计

- 更新 `packages/pdf-table-5/readme.md` 的 canonical geometry/text runtime、sample 超集规范、
  crop-only/按需 context、正常 Parser 建议步骤、运行时 AGENTS 与 Resume 短 delta 行为。
- 搜索根 `README.md`、`wiki/`、package README 和任务记录中的旧 runtime geometry shape、图片附件、
  固定前缀与 sample 描述；根导航和 wiki 不描述这些内部行为，无需修改。
- 本轮未改变 ReIndex HTTP/CLI v1 contract，不需要更新 OpenAPI 或 ReIndex CLI contract。任务恢复为
  “等待人工审核”，继续留在 `tasks/`，未归档。

## Bielefelder Netz Terra 实测

- 全新 `gpt-5.6-terra`、medium reasoning 子 agent 从仅含源 PDF 的
  `testbase/test5-table5/bielefelder-netz-2022` 只启动一次完整 `pdf-table-5 all`，正常退出；未修改
  package 源码或手工调整 CSV/sample/parser。
- PDF 共 5 页；Finder 在第 5 页发现 2 个 segment，均为独立表格，Merge agent=0，最终 2 张 logical
  table。结果为 2 `verified`、0 `format_only`、0 `skipped`、0 `failed`，`accepted=true`。
- `table_0000` 为 4x9（含表头）的下层网级聚合十年规划；`table_0001` 为 54x20 的未来十年措施明细，
  首个/末个编号为 `4aa`/`91`。主 agent 对照第 5 页完整页面和两张 crop，表格边界与内容结构一致。
- 总耗时 230,887 ms（3m50.887s）；token 为 input 1,300,451、cached input 949,248、output 13,572、
  reasoning 6,171。逐个 Agent：Finder 17.312s（25,544/11,008 input/cache）；Parser 0000 35.486s
  （36,524/0）；Parser 0001 68.173s（106,555/11,008）；Repair 0001-1 108.416s
  （1,131,828/927,232）。
- 仅 `table_0001` 发生 1 次 Repair：首次 CSV 少一行并有两处独立短横线空格差异；Repair 恢复原
  Parser session，修复后 54x20 verified。状态为 attempts 1/1、revision=2、in-flight=null、fallback=0。
- Finder 和两个初始 Parser 的 Shell/file-change 均为 0。Repair event 独立复算为 7 次
  `command_execution`（6 成功、1 失败）、0 file-change、Shell 输出仅 3,108 bytes；失败调用把原始
  word object 当数组导致 `KeyError: 0`，后续按字典形态诊断。高 input 主要来自多轮工具回合重复携带
  大表 prompt、页面 crop 与会话历史，不是 Shell 文本输出本身。
- 主 agent 独立运行 CLI `verify` 和生成项目 `parse/main.py::verify()`，均返回 2/2 accepted；CSV
  矩形与行列数复核通过，`failedTables=[]`。
- 本轮是新 fixture 实测，没有改变 package 行为、schema、HTTP/CLI contract 或文档流程；检查当前
  package README、根 README、wiki 后无需更新。任务恢复为“等待人工审核”，未归档。

## Bielefelder 空行修复与第四轮优化

- 根因复核：源 geometry 中左侧编号锚点恰好为 52 个，编号从 `4aa` 到 `91`；初始 Parser 的代码也
  生成 52 条数据，但 sample 错写为含表头 54 行。Repair 已正确数出 52 个源记录，却为了迎合错误
  `totalRows` 在编号 89 前显式插入 20 个空字段，因此旧 Review 的“总行数 + 前三/后三样本”被绕过。
- 当前 fixture 已按 source-backed evidence 修正为 53x20（1 表头 + 52 数据）；物理第 51 行现在是
  编号 89，空行数为 0。`sample.totalRows` 改为 53，尾部样本索引改为 50/51/52，生成 parser 删除
  synthetic padding。
- 通用 Review 新增全空数据行硬拒绝、sample 行宽与全空 sample 检查，并在 review 中提供紧凑
  `csvProfile`（行列数、空行索引、首列头尾），防止只靠抽样和行数通过内容门。
- Parser/Repair 固定协议明确要求由 source geometry 记录锚点精确核对 `totalRows`，禁止生成、插入或
  保留空行/虚构行来迎合 sample；Repair 优先使用 `csvProfile` 与 `geometryHints`，证据足够时直接返回
  field patch，仍保留 Shell/PDF/截图能力。
- `parserContext` 增加左边缘 visual-line 提示，帮助 Agent 无需 Shell 即可核对记录锚点。完整 inline
  geometry 改为按视觉线共享 `y0/y1` 的无损编码，线内保留 `x0/x1/text/block/line/word`；runtime
  loader 仍返回原有 flat word contract，不影响生成代码。
- 进一步抽查发现旧 `join_word_text()` 把同一行的 `Schutz- und` 错成 `Schutzund`，也把
  `Schutz- &` 错成 `Schutz-&`。规范 join 现在用 y 坐标区分真实断行连字符，并结合前缀/词间距保留
  同行连字符；Bielefelder 中段相关记录已随确定性 verify 重生并修正。

## 第四轮性能与质量评估

- Bielefelder 大表初始 Parser prompt 从旧 166,578 字符降到 136,447 字符，减少 30,131（18.09%）；
  其中 3,275 个 word 的完整 geometry 从 flat 157,437 字符降到 line-packed 114,463，减少 27.29%，
  已包含额外 12,778 字符/103 行的 row-count hints 后仍实现整体净减少。
- 旧 Repair 为 108.416 秒、input 1,131,828（cache 927,232）、output 8,097、reasoning 4,041，7 次
  Shell。若新提示在初始轮正确核对 52 个记录，该 Repair 整体可消除；即本案例直接少 46.96% 总耗时、
  87.03% total input 和全部 7 次 Agent Shell，再叠加大表初始 prompt 的约 18% 缩减。
- 若仍需 Repair，`csvProfile + geometryHints` 应把当前 7 个诊断工具回合压到单个 resume 回合；按旧
  每回合历史重放量估算，Repair input 可减少约 80%-88%，耗时预计从 108 秒降到约 20-40 秒。该项
  是基于本次 event 的估算，尚未重新付费执行 Terra 端到端测试。
- 无 Repair 的同文档下一轮保守预计约 1.7-2.2 分钟、0.14M-0.25M input；若发生一个单回合 Repair，
  预计约 2.0-2.8 分钟、0.28M-0.45M input。模型波动和复杂表结构会影响实际值。
- 质量上仍可选择把长表的 6 行样本改为分层样本（首 3 + 四分位/中位 + 尾 3），代价约增加每张
  长表 2-3 行 structured output；本轮先用零 Agent token 的结构检查、canonical join 和 source hints
  修复已知漏洞，未擅自改变用户确认的抽样数量契约。

## 第四轮验证与文档审计

- 新 Review 对原错误产物确定性返回 failed，错误为全空 data row index 50；修正后 CLI `verify` 与
  生成 `parse/main.py::verify()` 均为 Bielefelder 2/2 verified、accepted=true，尺寸为 4x9 与 53x20。
- Solingen 第三轮 fixture 用同一新版 runtime 复核为 5/5 verified、accepted=true，尺寸仍为
  6x3、8x6、7x4、7x4、14x16，连字符修复未造成既有 sample 回归。
- package 全套 `35 passed`；`uv lock --check`、`git diff --check` 通过；所有新增/修改仓库手写
  Python 不超过 200 行（最高 `taskReviewTable.py` 197 行）。
- 更新 package readme 的 line-packed geometry、row-count/padding 禁令、空行格式检查、Repair
  diagnostics 与 visual-line-aware join。根 README、wiki、HTTP/CLI v1 contract 不描述这些内部行为，
  无需修改。任务恢复为“等待人工审核”，继续留在 `tasks/`，未归档。

## E.DIS 2024 Terra 实测

- 使用一个全新 `gpt-5.6-terra`、medium reasoning 子 agent，只启动一次完整 `pdf-table-5 all`；没有
  重跑、resume 或手工修改生成的 parser/sample/CSV。PDF 为 34 页、8.3 MB、AES 权限标记为可打印但
  禁止复制；PyMuPDF 仍成功提取 vector geometry，故权限不是本轮阻断原因。
- Finder 用 104.072 秒找到 25 个 segment，其中 `yes=9`、`possible=0`、`no=16`；确定性合并为
  16 张 logical table，Merge agent=0。表 1-15 位于第 8-18 页；表 16 是第 25-34 页的 10 页续表。
- 唯一一次主命令最终失败：`table_0015` Parser 在五次 WebSocket stream disconnect 后转 HTTP fallback，
  仍以 exit 1 结束。该表未产生 sample/summary/parse.py/CSV；`states.json` 为 failed。独立 CLI verify
  与生成 `parse/main.py::verify()` 均得到 15 verified + 1 failed、`accepted=false`。
- 实际墙钟约 1,100.953 秒（18m20.953s），steps 累计 1,100.820 秒。阶段合计：Finder 104.072s、
  Merge/List 0.002s、prepare 8.774s、Parser 860.735s（含最后失败重试 287.020s）、Review 2.450s、
  Repair 124.787s。前 15 个成功 Parser 合计 573.715s，平均 38.248s。
- 已记录 token 为 input 733,453、cached 294,400、output 36,108、reasoning 8,982；cache/input 为
  40.14%。失败的最后 Parser 没有完成 usage event，steps 将其 token 记为 0，因此这些数字是可审计
  下限，不是服务端实际计费上限。
- Repair 共 4 次：table 0003/0005/0007/0010 各 1 次，均恢复原 session，fallback=0。累计
  124.787s，input 278,849（占已记录 input 38.02%）。前两次分别修 caption block 判定与 compact word
  索引误用；后两次涉及表头/sample 与连字符文本。
- 全部 workflow agent events 精确计数为 1 次 command_execution（成功）、0 失败、0 file_change；
  唯一 Shell 是 table 0003 Repair 的聚焦 geometry block 诊断。正常 Finder/Parser 仍未使用 Shell。
- 已生成 15 个 CSV，共 88 行、4,657 bytes；尺寸依次为 9x6、9x6、3x4、6x5、6x5、6x5、6x5、
  7x4、7x4、4x3、3x5、7x4、7x4、4x4、4x4。所有 CSV 均通过当前矩形、空行和 sample gate。

## E.DIS 质量复核与扩展性结论

- 主 agent 查看了 Finder 的 3 张完整 contact sheet，覆盖全部 34 页，并核对第 8-18 页小表及第 25-34
  页十页续表。自动状态的 15 verified 不能等同于人工严格成功，至少发现四个 source fidelity 问题。
- table 0007 源表头为 `Geschätzte Menge`/`Geschätzte Kosten`；首次 sample 正确，但 Repair 无源依据地把
  sample、summary、parse.py 一起改成 `Menge`/`Kosten`，形成 sample 与 parser 共同放宽。
- table 0010 把跨视觉行的专名写成 `Mecklenburg- Vorpommern`，Repair 又修改 sample 接受该空格；同一
  表头的软断行 `Ortsnetz-` + `stationen` 也被硬编码成 `Ortsnetz-stationen`，而不是语义词
  `Ortsnetzstationen`。
- table 0011/0012 把一个跨两条措施行的 Zeitraum 合并单元格拆开：第一条只有 `2023 bis 2028`，下一条
  只有 `(t+5)`，其余两个 Zeitraum 同样拆分。sample 与 parser 同源地产生相同错误，现有抽样无法发现。
- 最后一张表是明确的扩展性边界：10 个 segment、23,693 vector words、1,798 visual evidence lines、
  626 hint lines；单 Parser prompt 929,785 字符，落盘 parserContext 4,011,720 bytes，10 张 crop 合计
  11,940,408 bytes。连续断流很可能与超大多页单表请求相关，而非 parser 执行或 geometry 缺失。
- 后续优先修复方向：对超阈值续表使用 representative full geometry + 全页 row/column profiles，或分两步
  设计 parser/核对首尾 sample，避免一次发送 10 页完整 words/crops；对 failed initial turn 持久化
  thread id，以短 delta resume 而不是重新发送约 930K prompt；禁止 Repair 仅为匹配 parser 而改动
  source-backed header/sample；增加 merged-cell repeat/propagate 的结构检查和跨行词法归一规则。
- 本轮按用户要求只测试，没有修改 package 实现或手工修正 E.DIS 产物。任务恢复为“等待人工审核”，
  继续留在 `tasks/`，未归档。

## sample.py 与连续大表简化实施记录

- Parser structured output 的 `sample` 对象统一改为 `samplePy` 字符串；调度器先写
  `parse/tables/<table>/sample.py`。Review 以 `python sample.py --table-json TABLE_JSON` 执行脚本，
  只接受 stdout 的单个 JSON object，再做原有 sample schema、行数、行宽和抽样检查。没有特殊规则
  时脚本直接打印固定 JSON；脚本也可通过 runtime loader 从全部 segments 动态计算 sample。
- sample stdout 可选 `compareRules`；当前固定规则 `ignore_space_hyphen` 可按列/rowIndex 作用。Review
  先做严格 Unicode/空白比较，只在声明规则的单元格去除空白、ASCII/soft/Unicode hyphen 形成比较键；
  等价命中 accepted 且写入 `hyphenEquivalentMatches`，其他文字、数字和标点差异继续失败。
- Repair field patch 从 `sample` 改为 `samplePy`，仍允许按诊断修改 sample、parser 或两者；旧脚本仅在
  实际变化时归档为 `sampleN.py`。revision、累计 attempts、原 session resume/fallback 语义不变；新
  step 日志增加 `changedArtifacts`，便于审计 sample 是否被修改。
- 4 个及以上 segments 的逻辑表启用 boundary evidence：Parser context 仅内联首段和尾段完整 geometry，
  只附加首尾 crop；所有中间段仍在 runtimePaths 中给出页码、bbox、绝对/相对 geometry 路径及计数，
  生成的 sample.py/parse.py 通过 `load_segments()` 直接运行全部 segments。少于 4 段仍下发完整证据。
- 实测后收紧两条固定提示规则而未增加调度阶段：纯连字符/空白差异应保留原 sample 值并增加窄范围
  compareRule；sqlFriendly 表格的跨记录合并单元格应把完整多行值复制到每条记录，不得把日期范围与
  括号限定词拆到相邻 sample/CSV 行，也不得为匹配错误 CSV 而把正确 sample 改成碎片。
- 新增 `sample_runtime.py`、`sample_review.py` 和 `strategy_context.py`，把已接近行数上限的 Review/context
  职责拆开。最终所有仓库手写 Python 不超过 200 行，最高为 `agent_context.py` 195 行。

## E.DIS sample.py/boundary Terra 实测

- 全新 `gpt-5.6-terra`、medium 子 agent 在仅含源 PDF 的
  `testbase/test5-table5-1/e-dis-2024` 只执行一次完整 `pdf-table-5 all`，exit 0；未重跑、未 resume 主
  命令、未手工修改 agent 产物。Finder 为 25 segments，确定性 merge/list 为 16 logical tables，
  Merge agent=0。
- 报告墙钟/累计耗时为 983.391 秒（16m23.391s）；token 为 input 852,299、cached 316,928、output
  46,160、reasoning 13,791。阶段：Finder 103.097s（70,823/0/2,678/743）；Prepare 9.121s；Parser
  707.209s（507,194/197,376/28,958/8,844）；Review 4.155s；Repair 156.813s
  （274,282/119,552/14,524/4,204）；Final 2.994s；Merge/List 0.002s。
- 16 张表全部生成 `sample.py`，`sample.json=0`。自动 report、主 agent 独立 CLI `verify` 和生成项目
  `parse/main.py::verify()` 均为 16/16 verified、accepted=true。CSV 尺寸为 9x6、6x6、3x4、6x5、
  6x5、6x5、6x5、7x4、4x4、4x3、3x5、7x4、7x4、4x4、4x4、565x17；无全空行、非矩形行、重复
  header 或重复整行。
- Repair 共 5 次：table 0002/0003/0010/0011/0012 各 1 次，全部 resumed、fallback=0。只有 table
  0010/0011 修改了 sample 并产生 `sample1.py`；其他三次只修改 Parser。22 个 agent turns 的 event
  中 `command_execution=0`、`file_change=0`，Agent 工具能力仍保留但正常路径没有使用 Shell。
- 十页 table 0015 的 parserContext 为 boundary mode、`fullEvidenceIndexes=[0,9]`，只含页 25/34 的两份
  evidence 和 2 张 crop，同时列出全部 10 个 runtime geometry。context 从旧 4,011,720 bytes 降为
  820,235（-79.56%），Parser prompt 从 929,785 bytes 降为 201,809（-78.30%）。该 Parser 用 67.243s、
  input 124,064 首轮成功；旧轮在 287.020s/五次断流后仍失败。长表为 17 列、564 数据行；逐页 source
  anchor/CSV 边界一致：56、57、57、57、57、57、57、57、57、52 行，编号边界 7-151、152-241、
  242-298、299-355、356-412、413-469、470-526、527-583、584-640、641-692。
- 相对旧 E.DIS 轮 18m20.953s 且最终失败，本轮总耗时降低 10.67% 并完整成功。旧轮最后失败 Parser
  没有 usage event，因此不能用旧 733,453 的已记录 input 与本轮完整 token 作严格总量降幅比较；长表
  prompt/context 与 Parser 时间的降幅是可直接比较的数据。

## 本轮人工质量复核与后续验证边界

- 对照 Finder contact sheets、第 17 页表格 crop 和第 25/34 页长表 crop，长表全部十页连续、首尾与
  每页 anchor 数一致，结构质量可接受；主 agent 未修改生成 CSV。
- 自动 accepted 仍存在 2 个明确 false verified：table 0007 和 table 0011 把跨两条措施记录的
  Zeitraum 合并单元格拆成 `2023 bis 2028` 与下一行 `(t+5)`，而 sqlFriendly 输出应在两行均重复完整
  `2023 bis 2028 (t+5)`；后两组同理。table 0011 初始 sample1.py 原本正确，Repair 为匹配错误 CSV
  改成碎片；table 0007 初始 sample/Parser 同源地产生碎片。
- table 0010 的 `Mecklenburg-Vorpommern` 被 Repair 改成 `Mecklenburg- Vorpommern`，没有使用新
  compareRule；产物中 `hyphenEquivalentMatches=[]`。这属于版式等价但不是期望的 sample 修复路径。
  实测后已在固定前缀增加明确的连字符 Repair 与 merged-cell repeat 指引，但按单轮测试约束没有再
  启动第二个 Agent 或手工改当前产物，因此本 fixture 的自动 report 保留原始真实结果。
- package 最终回归 `38 passed`；`uv lock --check`、`git diff --check` 和手写 Python 200 行限制通过。
  `packages/pdf-table-5/readme.md` 已同步 sample.py CLI/规则、boundary evidence、Repair sample patch、
  merged-cell 与 changedArtifacts 行为。根 README、wiki 和 ReIndex HTTP/CLI v1 contract 不描述该包的
  内部 artifact schema，不需要更新；任务等待人工审核，未归档。

## Sample 原始值门禁实施与 Terra 实测

- `compareRules` 现在必须使用非空 `columns`；初始 Parser 固定提示要求逐列识别 PDF 断行连字符风险，
  在初始 `sample.py` 中立即声明 `ignore_space_hyphen`，通常以空 `rowIndexes` 覆盖整列。
- Repair 建议的 sample 脚本先在临时路径执行。调度器比较忽略 `compareRules` 后的 mode、totalRows、
  header、rows 和 skipReason：完全相同视为 rule-only 并直接应用；任一原始值变化才启动新的
  source-confirm agent。该 agent 的提示没有 CSV actual、parse.py 或 Repair 建议值，只给当前 sample、
  变化位置、PDF crop、source PDF 和 geometry；结果写入 `sampleConfirmation.json` 并反馈原 session。
- 生成的 sample.py/parse.py 均静态禁止读取 `sampleConfirmation.json`，确认文件只用于 agent 修复反馈，
  不成为运行时数据依赖。旧 sample 仍只在实际脚本变化时归档。
- 本地新增回归覆盖：无列范围规则拒绝；rule-only sample 修复不启动新 agent；原始值修改必启动新
  source-confirm agent；确认提示不包含错误 CSV 值；拒绝错误建议后原 Parser session 收到来源确认并
  修 parse。package 全套为 `41 passed`，`uv lock --check`、`git diff --check` 通过。
- 全新 `gpt-5.6-terra`、medium 子 agent 对 `testbase/test5-table5-2/e-dis-2024` 只执行一次 `all`，exit 0；
  Finder 25 segments、确定性合并为 16 logical tables、Merge agent=0。最终 16 verified、0 failed、
  accepted=true；CLI verify 与生成项目 verify 均复现。
- E2E 总耗时 999,938 ms（16m39.938s）；token 为 input 960,914、cached 329,472、output 44,571、
  reasoning 12,839。阶段为 Finder 128.181s、prepare 8.138s、Parser 693.706s、Review 3.696s、
  Repair 164.135s、final 2.079s，merge/list 0.003s。
- 6 次 Repair 位于 table 0008-0013，均 resumed、fallback=0；0008/0009/0011/0012/0013 只改 parsePy，
  0010 只改 samplePy。0010 的旧、新 sample 原始值都为 `Mecklenburg-Vorpommern`，只新增第 0 列
  `ignore_space_hyphen`，因此按设计没有启动 source-confirm。全轮无任何 sample 原始值修改，确认路径
  由本地回归真实执行覆盖。
- 初始 0010 Parser 没有主动声明规则，直到 resumed Repair 才补上，说明“初始按列添加”提示并不保证
  每次被模型遵循；门禁仍保证 Repair 不能借此修改原始值。CSV 保留源视觉换行形式
  `Mecklenburg- Vorpommern`，sample 保持规范值并由列规则判等。
- 所有 Zeitraum 表人工复核为完整 SQL-friendly 值；table 0011 的两条共享记录均为完整
  `2023 bis 2028 (t+5)`，后两组同样重复完整值，没有再次拆分 sample。全部 CSV 无空数据行且矩形；
  尺寸为 9x6、6x6、3x4、四张 6x5、两张 7x4、4x3、3x5、两张 7x4、两张 4x4、565x17。
- Agent event 为 23 turns；只有 parser 0001 使用 2 次实际 Shell 命令（对应 4 个 started/completed
  lifecycle events），file_change=0，其余 Finder/Parser/Repair 均无 Shell。文档已同步 package README；
  根 README、wiki、HTTP/CLI contract 不描述该内部 sample 门禁，无需修改。

- 状态恢复为：等待人工审核。
