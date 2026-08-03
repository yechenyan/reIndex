# 让 Agent 生成 PDF 表格提取器

`pdf-table-codegen` 的产物是项目内可复用的 `extractor.py`，不是一次性的 CSV。
第一次由 Agent 看 PDF、冻结表格清单并写代码；后续流水线直接运行代码，不再调用 AI。
该 package 可独立安装，也可在 ReIndex 或其他数据流水线中调用。

## 安装和提示词

```bash
uv tool install ./packages/pdf-table-codegen
pdf-table-codegen install-skill <project-directory>
```

给 Agent 的提示词只需描述目标和输入：

```text
使用 $pdf-table-codegen，为 <PDF路径> 生成可重复运行的表格提取器。
输出放在 <项目目录>；先准备并检查所有页面证据，冻结表格清单和独立首尾行参考，
再按每张表的实际版式选择提取策略并写 extractor.py，运行 verify，并报告表数、行列数
和失败项。不要强制套用固定网格，也不要在运行时调用 AI。
```

Agent 会先写 `job.yaml`，再执行：

```bash
pdf-table-codegen prepare <project>/job.yaml
pdf-table-codegen freeze-inventory <project>/job.yaml /tmp/inventory-draft.json
pdf-table-codegen inspect <project>/job.yaml
pdf-table-codegen freeze-reference <project>/job.yaml /tmp/reference-draft.json
pdf-table-codegen scaffold <project>/job.yaml
pdf-table-codegen run <project>/job.yaml
pdf-table-codegen verify <project>/job.yaml
```

`prepare` 只有在 source SHA、DPI、工具版本和全部证据文件 hash 都一致时才复用缓存。
`freeze-*` 自动写入并校验 hash、表ID和必需样本；临时 draft 放在项目目录外。
`inspect` 只处理已经冻结的 bbox，生成逐表裁剪图和中性文字/矢量坐标报告，不决定提取算法。
`scaffold` 只生成 QA 断言提示，不能用参考值拼装结果。所有命令直接报告执行秒数。

裁剪图用于替代后续重复打开同一整页；只有需要上下文时才重开整页。独立清单审核 Agent
完成后，可以继续与主 Agent 分表并行制作 reference 草稿，但主 Agent 必须逐个确认合并后的
表头和样本，不能把并行草稿直接冻结。

## 项目输入和输出

```text
project/
├── source.pdf                 # 输入
├── job.yaml                   # 路径和通用策略
├── extractor.py               # 该 PDF 的全部版式、schema、规范化和 QA 代码
├── evidence/
│   ├── manifest.json          # 页尺寸、旋转、文本层统计
│   ├── inventory.frozen.json  # 冻结表格清单
│   ├── visual-reference.json  # 独立表头、总行列数、首尾行参考
│   ├── contacts/              # 全页联系图
│   ├── pages/                 # 页面图
│   ├── geometry/              # 原生文字与矢量坐标
│   ├── tables/                # 冻结区域裁剪图和中性几何报告
│   └── assertion-hints.json   # 仅用于 QA
└── output/
    ├── <table-id>.csv
    ├── result.json            # 结构化结果和逐行溯源
    └── verification.json      # 冻结参考验证报告
```

没有单独的 `schema.yaml`、`normalize.py` 或 `compatibility.py`。这些文档专用决策集中在
`extractor.py`，冻结参考保持独立，且不能被提取器读取。

## 提取策略不是固定模板

package 固定的是证据、函数接口、溯源和验证，不固定表格算法。Agent 必须逐表判断：规整表
可以按行带和列边界读取；无边框或可变行高表可以使用锚点与聚类；矢量边框表可以先重建
单元格；层级表和复杂合并表可以使用专用状态机。一个 `extractor.py` 可以混合多种方法，
必要时也可以只对文字层失效的冻结区域使用 OCR。

固定网格只是一种可选实现。无论采用什么方法，都必须增加与该方法对应的锚点、关键列、
跨页边界或坐标漂移断言，并通过独立视觉参考；不能只依赖总行列数判断正确性。

## 流水线调用

```python
from pdf_table_codegen import ExtractionRequest
from my_pdf_project.extractor import extract_tables

result = extract_tables(ExtractionRequest(source=input_pdf))
for table in result.tables:
    consume(table.headers, table.rows, table.provenance)
```

调用边界是 `ExtractionRequest -> ExtractionResult`，因此 NAP、ReIndex、Airflow 或普通 Python
函数都可以直接接入；CSV 只是默认序列化结果。

仓库中的完整样例位于
[`testbase/test5-table/bielefelder-netz-2022`](../../testbase/test5-table/bielefelder-netz-2022)。
