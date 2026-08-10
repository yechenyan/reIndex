# PDF 表格提取 Workflow

`packages/pdf-extractor-pdf` 生成可重复运行的 PDF 专用表格 extractor。固定代码负责证据、
模板、Hash、运行、Diff 和冻结；Agent 负责找候选、精确提取和源图审核。

## 项目交付

```text
project/
├── output/          endgültige CSV und result.json
└── extractor/
    ├── job.yaml
    ├── main.py
    └── evidence/    Kandidaten, Struktur/QA/Review je Tabelle, endgültiges Inventar und Metriken
```

项目产物不得写回 package。

## 单槽逐表流程

1. 主 Agent 创建任务；固定代码生成全页低清图、Contact Sheets 和 Finder Packet。
2. Finder 检查每一页，只记录有表的页、粗略区域和有序 candidate ID。Finder 不确定
   精确 BBox、列数、行数、跨页延续或逻辑表归属。
3. Extraction 用滑动窗口依次判断 candidate：延续则合并，出现边界则关闭当前逻辑表；一个
   粗 candidate 含多张表时可拆成互不重叠的精确范围。
4. 表关闭后固定代码生成绑定 Extraction run、结构和 evidence Hash 的 `qa_handoff`。
   Extraction 把 handoff 直接交给原 QA，并在同一轮继续写代码；QA 用 `trigger_run_id` 认领后
   查看精确图及四周上下文图，检查范围、拆分、合并并采样。
5. 两边都以 `stage-finish` 作为最后命令，后完成的一方自动触发逐表 Diff。通过则继续下一
   candidate；失败则 QA 直接把当前表
   的范围、合并、结构或值问题反馈给 Extraction，不经过 Main 内容裁决。
6. 所有 candidate 被提取或有证据地排除、所有表逐表通过后，代码组装全局
   `inventory.json`/`reference.json`，再运行全局验证和最终 gate。

## 命令入口

```bash
uv run pdf-extractor-pdf init PROJECT SOURCE.pdf --request "Alle Tabellen extrahieren"
uv run pdf-extractor-pdf prepare PROJECT/extractor/job.yaml
uv run pdf-extractor-pdf freeze-candidates JOB candidate-draft.json
uv run pdf-extractor-pdf refine-table JOB table-structure-draft.json
uv run pdf-extractor-pdf scaffold-table-reference JOB TABLE_ID
uv run pdf-extractor-pdf plan-table-reference JOB TABLE_ID qa-structure-draft.json
uv run pdf-extractor-pdf freeze-table-reference JOB TABLE_ID qa-reference-draft.json
uv run pdf-extractor-pdf review-table JOB TABLE_ID
uv run pdf-extractor-pdf assemble-incremental JOB
uv run pdf-extractor-pdf validate JOB
uv run pdf-extractor-pdf finalize JOB
```

完整 draft 格式和边界规则见 package 的
[README](../../packages/pdf-extractor-pdf/README.md) 与 bundled `SKILL.md`。

## 数据与质量规则

表格是无额外表头的字符串矩阵；可见首行就是 row 0。每行保留 1-based 页码、PDF-point
BBox 和 Segment ID。QA 对数字、日期、ID、代码和金额使用 `exact`，对自由文本使用
`text`。采样覆盖前三行、后两行、中间行和每个 Segment 边界；源空值必须显式声明。

QA reference 绑定精确结构 Hash。结构变化会使旧 reference 失效。全局验证继续检查确定性、
候选覆盖、行列顺序、provenance、采样值和遗漏的合并候选。

任一时刻只有一张当前表；通过前不能提交下一张表，也不为每张表创建新 Agent。

## Metrics

Finder、Extraction 和 QA 使用不同 `agent_id`；Extraction 冻结范围后直接启动 QA，两个 stage
都用 `--tables ID` 记录归属。范围判断和代码共用 `extraction`，QA 使用 `qa`。
`stage-start` 必须在读取本轮证据前执行，`stage-finish` 必须最后执行。Token 的 input/output
必须同时提供；报告标明 `complete`、`partial` 或 `unavailable`，无精确 Token 时不得估算。
