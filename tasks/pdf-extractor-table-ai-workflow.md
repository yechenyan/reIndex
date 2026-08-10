# PDF 表格 AI Workflow

状态：等待人工审核

## 用户请求

> 在 `packages/pdf-extractor-table` 从零实现由主 LLM、找表 LLM、解析 LLM、质检 LLM和确定性程序组成的 PDF 全表格提取工作流。每份 PDF 的生成代码和资源位于自己的项目目录，根目录 `extractor.py` 可离线重跑并输出 CSV。不要参考项目中的其他代码。

> 支持用户选择 PDF 页面；页面坐标归一化需要高精度。纯扫描 PDF 可以由多模态 LLM 直接写入完整表格数据，不使用 OCR。目录、图表和表单不算表格。

## 已确认范围

- 工具适配不同 PDF，但生成的提取器只针对当前 PDF。
- 提取选定页面中的所有逻辑表格；默认选择全部页面。
- 每个逻辑表格输出一个 CSV，跨页续表合并并删除重复表头。
- CSV 保留行列顺序和多行表头；合并单元格左上角保留值，其余留空。
- 最终提取器离线运行并校验源 PDF SHA-256。
- 不使用 OCR；无文字层时由多模态 LLM 生成完整结构化数据。
- 文字比较允许空白、换行和断行连字符规范化；数字、符号和单位必须一致。
- 质检默认抽样首三行、尾三行和分页边界；六行及以下全量抽样。
- 任意 diff 立即标记 `needs_review`，由 main 判断重跑 Parser、重跑 QA 或接受 Parser；不会自动让一方迎合另一方。
- 大文件分批准备证据并支持断点续跑。

## 实现决策

- 使用固定调度器和声明式 `job.yaml`，不让主 LLM 为每个任务重写调度源代码。
- 页面选择使用从 1 开始的物理页码表达式，例如 `1-3,8,10-12`。
- 内部同时保存 PDF 原始坐标、旋转后页面坐标和十进制字符串归一化坐标。
- 归一化坐标默认保留 10 位小数；避免用归一化坐标反复往返计算。
- 每张逻辑表只启动一个连续 Parser CLI。Parser 先在单表受限可写 staging 中确认合并关系和坐标；裁图错误时自行调用确定性 `parser_tool.py recrop`，不返回 Finder。
- Finder 的宽松裁图默认直接接受；只有截断、混入另一张表或不可读时，Parser 才能对每个片段最多重裁一次。Parser 只提交 3–4 位粗坐标和要合并的 fragment ID，程序按实际图片像素对齐并生成 10 位精确坐标及 handoff，不再由 Parser 手写 geometry proposal。
- Parser 用原子替换发布 `evidence-ready.json` 后继续在同一会话生成提取代码；调度器监听到该文件便立即启动独立 QA，因此 QA 与 Parser 的代码生成阶段并行。
- QA 只读不可变 handoff、提升后的裁图和相关高清全页图；不读取 Parser 结果、代码、提取数据、原 PDF 或 native text。main 不生成代码或 QA 数据。
- main 判定初始 QA 裁图不完整后，`retry-verifier` 仅追加相关高清全页图，不向新 QA 暴露 Parser、提取结果或 comparison。
- Codex CLI 使用结构化输出 schema 和临时会话。Finder/QA 使用只读 sandbox；Parser 仅对 `resource/work/<table>/parser` 使用 workspace-write。

## 验收检查

- 页面选择解析、越界检查及非连续页处理有测试。
- 混合页面尺寸和旋转的坐标映射有测试。
- PDF 预检、分批 contact sheet、高清候选裁图可运行。
- 工作流有原子 checkpoint，并可从中断处恢复。
- Codex 输出经过 schema 和业务校验后才能写入项目。
- 生成代码在受限子进程运行；最终 `extractor.py` 不调用 LLM。
- 数字严格比较和文字断行规范化有测试。
- 样例 SWS PDF 完成全流程；WNG 大表样例保留可恢复检查点但不继续消耗模型调用。

## 实现与验证记录

- 新增独立包 `packages/pdf-extractor-table`，包含 CLI、PDF 预检和渲染、找表、证据准备、解析/质检、语义 diff、main 决策、断点状态与最终离线提取器模板。
- 源码未引用项目其他实现；手写 Python 模块均不超过 200 行。
- SWS 样例预检 17 页，找出 7 个物理表格片段并生成 6 个逻辑 CSV；第 16–17 页正确合并为同一张表。
- SWS 六张表的最终尺寸依次为 `25×2`、`5×3`、`8×6`、`7×4`、`7×4`、`14×16`（行数包含表头）。
- 前五张表一次通过抽样质检；跨页表初始 QA 裁图漏掉表头和部分数据行，main 路由高清全页 QA 重试后把差异收敛到 `I + II` 和 `Löhndorf` 两处，再路由 Parser 修订并通过。
- 最终 `extractor.py` 校验源文件 SHA-256，离线运行；工作流连续两次复跑及一次独立复跑的所有 CSV 哈希一致。
- `pytest` 31 项通过；`compileall`、`git diff --check` 通过。PyMuPDF 仅有 5 条上游 SWIG 弃用告警。
- 已按 PDF 工作流要求检查 SWS 两张低分辨率总览图，并检查候选页高清证据。
- 任务保留为“等待人工审核”，未经用户确认不归档。
- 2026-08-08：改为 handoff 驱动真并行。一个连续 Parser 先自助重裁剪并原子发布证据，再继续生成代码；watcher 同时启动隔离 QA。6 张表的 `branches_overlapped` 均为 true，合计减少约 337 秒串行等待。
- 2026-08-08：Parser 使用单表 workspace-write；Finder/QA 只读。Parser sandbox 明确关闭网络并排除 `/tmp` 与 `$TMPDIR` 写根，临时文件改用 staging 内 `scratch/`。异步 CLI 日志直接落盘以避免管道超过 64 KiB 后阻塞。
- 2026-08-08：全新 Terra 只执行 init/run/status。首次运行 19 分 15 秒到 main-review；QA 返工与继续运行 11 分 36 秒；Parser 返工与 finalize 2 分 08 秒。含 main 决策停顿的总历时约 37 分 52 秒，三段调度器活动时间合计约 32 分 59 秒。
- 2026-08-08：最终角色调用为 Finder 2、Parser 6、Parser revision 1、QA 7（含 QA retry 1）；CLI 报告 token 总量约 699,372，其中 Parser/Parser revision 453,068、QA 203,454、Finder 42,850。已追加提示避免 SVG/XML/全量 word dump，降低后续无效上下文。
- 2026-08-08：最终状态 `complete`，6 张表全部 `passed`；7 个候选片段共触发 7 次 Parser 本地 recrop；离线重跑 `extractor.py` 后 manifest 和 6 个 CSV 均逐字节及 SHA-256 一致。
- 2026-08-08：启用 `coarse_lazy_recrop` 后从仅保留原 PDF 的干净 SWS 项目重新运行。7 个候选片段均直接接受宽松 Finder 裁图，`recrop_events=0`；6 张表的 `branches_overlapped` 仍全部为 true。
- 2026-08-08：几何 handoff 总耗时由约 18 分 51 秒降至 6 分 38 秒，减少约 64.8%。首次运行 24 分 13 秒停在跨页表真实 diff；main 根据高清原图判定 Parser 把 `I + II`/`Löhndorf` 误读为 `| + ||`/`Löhdorf`，只重跑 Parser，约 1 分 56 秒后完成。调度器活动总计约 26 分 09 秒，比旧基线 32 分 59 秒减少约 6 分 50 秒。
- 2026-08-08：新回归 CLI token 总量约 546,412（Finder 61,533、Parser 含一次 revision 316,691、QA 168,188），比旧基线约 699,372 减少约 21.9%。最终 6 个 CSV 尺寸保持 `25×2`、`5×3`、`8×6`、`7×4`、`7×4`、`14×16`；独立离线复跑的 manifest 和 CSV 哈希全部一致。
