# PDF 表格提取 Codex Workflow 示例

状态：等待人工审核

## 用户请求

> “我想做一个借助 AI workflow 从PDF 提取表格的功能。”
>
> 通用 LLM 提示、合约和调度代码放在
> `reIndex/packages/pdf-extractor-table-example`；LLM 生成的项目代码与运行产物放在
> `reIndex/testbase/test5-table2-example`。项目入口是 `extractor.py`。
>
> Finder 从全 PDF 低清视觉证据找表；解析 LLM 确定精确位置、跨页合并并生成代码；
> 独立质检 LLM 从源图转录抽样；固定代码运行 extractor、diff、最多修复三轮并可恢复。
>
> 目录、缩写表和一列结构不算表；只支持精确 PDF，不考虑 layout family；输出采用
> header-neutral matrix；图片表用大模型视觉完整转录，不使用 OCR；三轮仍失败时保留
> 产物、标记需审核并继续。用户最终确认：“1. 改成 example，2. 同意。开工吧”。

完整早期实验背景与旧方案记录保留在 `tasks/7.生成表格.md`。

## 范围

- 新建独立 Python package、CLI、状态机、JSON Schema 和 Codex 提示。
- 预检 PDF 可读性、权限、文字层、旋转、混合尺寸和图片区域。
- 生成分窗口联系图、候选页高清证据、精确表格裁图、上下文图和宽表切片。
- Finder 输出粗候选；解析先冻结全部逻辑表结构，再与盲审 QA 并行。
- 生成精确 PDF 专用 `extractor.py`；图片表读取冻结的视觉完整转录。
- 固定代码执行两次、比较确定性、结构、行数、抽样和跨页边界。
- 最多三轮定向修复；失败表保留输出并标记 `partial`。
- 为五个现有 PDF 创建互不共享产物的示例项目；按用户后续要求先以 SWS 做端到端测试。

## 关键约定

- Main 只生成声明式 `job.yaml`；每个项目不生成新的调度程序。
- QA 可以看冻结结构和源证据，不能看 extractor、运行结果或双方 diff。
- 所有持久坐标使用旋转后显示空间中的 PDF points；视觉输出先用归一化坐标。
- Finder 连续候选链和完整逻辑表分别做有限并发批处理；任何批次都不拆连续链/逻辑表，
  合并后再做全局覆盖校验。
- 目录、目录式索引、缩写/术语表和少于两列的结构必须排除。
- 精确 source SHA-256 是生成 extractor 的兼容边界。

## 验收检查

- `prepare` 完整覆盖全部页面，联系图页码清晰且无裁切/空白窗口。
- Finder 的每页结论齐全；每个粗候选被逻辑表拥有或显式 dismiss。
- 冻结结构的 bbox、页码、旋转、列数和 source hash 通过固定校验。
- QA 证据目录不包含 extractor、输出或运行日志。
- extractor 双运行结果完全一致，未知 PDF hash 被拒绝。
- 小表全量 QA；长表至少覆盖前 3、后 3、每个 Segment 接缝和中间样本。
- 图片表的完整视觉转录冻结后可由无 AI、无 OCR 的 extractor 输出。
- 三轮未收敛不会丢表或无限循环；最终报告准确标记 partial/needs_review。
- 中断后执行 `run` 只重跑失效或未完成阶段。
- package 测试、构建、SWS 端到端运行和文档一致性检查通过。

## 实现与验证

- 新建 workspace package `pdf-extractor-table-example`，提供 `init`、`run`、`extract`、
  `status` CLI；加入根 `pyproject.toml` 与 `uv.lock`。
- 实现 SHA 锁定 job、阶段状态机、原子 JSON 产物、Schema 校验、PDF 预检、旋转坐标、
  联系图、候选/精确裁图、宽表切片和证据哈希。
- Finder 覆盖每页；Structure 按连续候选链分批并发、代码合并；Builder 和 QA 并行，
  QA 按完整逻辑表分批且使用隔离临时包。
- 实现 QA 抽样/图片表完整转录契约、双次确定性执行、固定 diff、盲检重读、Builder
  定向修复、最多三轮和 complete/partial 最终报告；固定写入边界会拒绝 Builder 修改
  source、稳定 runtime 或冻结证据。
- 初始化 `test5-table2-example` 下五个 PDF 项目的 `job.yaml`。WNG 压力测试已冻结 73 页
  Finder 的 46 个候选和 18 张逻辑表，按用户要求暂停并保留中间产物。
- SWS 完整运行结果：17 页，6 个候选，5 张合格表；首次 diff 后盲检重读，Builder
  一轮修复收敛；最终 `complete`、5/5 表通过、双运行一致、6 次 Codex 调用。
- SWS 与旧 `test5-table` 对比：排除了旧结果中的缩写表；其余 5 表行列规模一致，
  前 4 表单元格一致；跨页表仅有 11 处斜杠后多余空格被源图验证并修正。
- 验证：10 个 package 测试通过；独立第三次 SWS 运行与发布输出逐字节一致；不同 PDF
  SHA 被拒绝；sdist/wheel 构建通过；`git diff --check` 通过；所有新增维护源文件少于
  200 行。
