# PDF 表格逐表 Diff Workflow

状态：等待人工审核

## 用户请求

> “以 `reIndex/packages/pdf-exractor-table-example-diff` 作为核心代码你新提的方案修改，
> 以 `reIndex/testbase/test5-table2-example-diff/sws-netze-solingen-2024/
> sws_netze_solingen_gmbh_netzausbauplan_2024_pdf.pdf` 作为测试文件，修改完代码，
> 再找子 agent 做一轮测试，收集反馈。”

## 目标架构

- 全 PDF 只执行一次预检和 Finder。
- 固定代码把 Finder continuation hints 转成有序逻辑表任务。
- 每张逻辑表单独生成高清证据、Parser/Builder 模块和盲 QA 参考。
- Parser 与 QA 使用隔离副本并行，QA 不看代码、输出或 diff 值。
- 每张表单独双运行、diff、重检、修复和哈希冻结；后续表失败不重跑已通过表。
- 最终 `extractor.py`、全局 structure/reference 和输出由固定代码汇总。
- 精确 PDF SHA-256；排除目录、缩写表和一列结构；不使用 OCR。

## 验收

- 新包 CLI、测试、构建和根 workspace lock 通过。
- 每表状态与产物可恢复，失败表不污染其他表。
- QA 隔离审计不包含 extractor、output 或 diff values。
- 单表双运行确定性、行列、抽样、跨页和 provenance 检查通过。
- SWS 由外层 Terra 子 agent 从空目录运行；内部角色保持 job 默认模型。
- 记录完整墙钟耗时、每角色 token、失败恢复、表格规模和人工源图抽查。
- 任务保持等待人工审核，不自动归档。

## 实现结果

- 新核心包、workspace CLI、schema、prompt、逐表状态、隔离 packet、双运行 diff、
  source-only QA recheck、Parser repair、哈希冻结和最终汇总均已实现。
- Finder 只执行一次；固定代码将 6 个候选组合为 5 张逻辑表，其中第 16–17 页
  以 `0.98` continuation confidence 合并。
- 证据策略为：纵向页整页宽并保留上下至少 72pt，横向页使用整页高清图；旧证据
  按 task hash 归档，不删除。
- 固定代码正规化无业务意义的 Segment ID、continuation 和模块路径，并把 QA 的
  crop-relative bbox 转成 PDF page 坐标；native-text 的冗余 full rows 被丢弃。
- QA 首次域输出不一致时在同一次 workflow 自动 source-only recheck；标题、行列、
  bbox、抽样、跨页接缝、provenance 与确定性逐表比较。

## SWS 实测

- Terra 外层主 agent 运行；内部 `finder/parser/qa/repair` 均保持 `null` 默认模型。
- 最终 `complete`，5/5 passed，轮次为 `[0, 1, 2, 1, 1]`；输出规模为
  `5×3、8×6、7×4、7×4、14×16`。
- 四次独立 extractor 验证中的最后两次及正式输出字节一致，最终 result SHA-256：
  `6efc887da7766f52cdaffedc47776a8c47091c2833e4ac255537d05f224f9654`。
- 最终累计（含开发期中断与恢复）：39 次 Codex 调用，3232.406 agent 秒；
  6,046,483 input tokens（4,799,232 cached）、116,941 output tokens。
- workflow 墙钟 3503.546 秒。最终恢复只处理失败的 `table-005`，前四张冻结表未重跑。
- QA audit 均为 `source_only=true`、`extractor_unseen=true`。Parser staging 已隔离写入，
  但下一阶段仍建议加 OS/容器级读隔离，防止绝对路径读取主 workspace。

## 真实卡点与处理

- Finder 粗框曾裁掉左侧列：改为固定的 full-width / landscape full-page 证据。
- QA 曾混用 crop/page bbox：明确单一 crop 坐标协议，由代码转换且带幂等标记。
- 跨页表曾把首个表头漏出 row 0：prompt 固化 `sum(source - repeated)` 公式并自动复核。
- Parser 曾漏 provenance key、误读 `I + II` 为 `| + ||`、漏 `Tabelle 5:`：逐表 repair
  后通过；title 已加入 structure diff。
- 累计耗时包含上述开发迭代，不代表稳定版单次基准。后续应另做一次全新目录冷启动计时。

## 追加修改

用户要求同一逻辑表修复时恢复原 Parser/QA 会话，不同表仍使用独立会话；同时扩大
纵向页表格上下文，避免表格下方标题被 72pt 边距裁掉。修改完成后清理 SWS 产物，
由新的外层子 agent 再做一次冷启动测试。

首次追加测试发现 Finder 可能把 portrait rough bbox 整体上移，120pt 固定边距仍会
裁掉 table-004 的末行和下方 caption；同时暴露了 `codex exec resume` 多图片参数必须
逐个重复 `--image`。证据策略因此改为候选页整页高清渲染，resume 参数也已修正。

完整冷启动进一步证明 resume 默认回落到 read-only 且使用启动进程 cwd；Parser 虽识别
出修复内容却不能写入会话模块。恢复命令现显式设置原角色 sandbox，并以持久 packet
目录作为 subprocess cwd，确保同一 Parser thread 只能在正确 staging 内修复。

## 2026-08-08 清理后冷启动结论

- 冷启动前 SWS 项目只有原 PDF；Finder 得到 6 个 candidate、5 张逻辑表，逐表证据均为
  整页高清图。table-004 的完整标题为 `Tabelle 4: Assetbedingte Maßnahmen der
  Mittelspannung und Umspannung MS/NS`，未再被裁掉。
- 不同逻辑表拥有不同 Parser/QA thread；同表 repair/recheck 已真实验证 resume 原 thread。
  Resume 不再重复附加高清图，调用 revision 单调递增；无 `turn.completed` 的 0 退出会失败。
- 同一 thread 连续两次 incomplete 或重复无效 QA contract 时会保留到 `retired_roles` 并
  新建仲裁角色。维修阶段 QA contract 错误会回到 QA 自修，必需/缺失样本索引会明确反馈。
- 技术状态曾达到 5/5 complete，正式输出与两次独立复跑字节一致；但人工审计发现
  table-005 把源图/PDF text layer 的 `Löhdorf` 错改为 `Löhndorf`。因此内容质量不通过，
  该 complete 属于假通过，95 分钟开发/恢复跨度也不能作为稳定性能基线。
- 核心代码现拒绝生成模块中的字词到字词硬编码 rewrite；repair prompt 要求 QA 与源图冲突
  时保持源值并 blocked，diff issue 会给 QA 精确 disputed column。此保护已由单测覆盖；
  本轮错误现场保留作回归样本，不把错误产物声明为合格结果。
