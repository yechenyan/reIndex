# ReIndex v0.1

ReIndex 把本地原始文件编译成程序可解析、Agent 可阅读、可搜索和可查询的知识包。

状态：当前实现基线；协议仍处于草案阶段。

## 1. 目标

```text
raw files → Node files → PostgreSQL / object storage → Agent tools
```

- `search`：融合全文搜索和向量搜索。
- `browse`：浏览 Node 树。
- `get`：读取 Node 或下载原始文件；容器可递归获取 children。
- `query`：用 DuckDB 查询完整表格。

原则不是字段越少越好，而是只保留能提高搜索、帮助 Agent 理解或保证正确溯源的信息。

## 2. 输入与输出

输入：

```text
data/
├── reIndex.md
├── someLargeA.pdf
├── someB.csv
└── folderC/
    ├── reIndex.md
    ├── someSmallA.pdf
    └── someC.png
```

输出：

```text
reIndex/
├── index.node.md
├── someLargeA/
│   ├── index.node.md
│   ├── 0001.node.md
│   ├── 0002.node.md
│   ├── 0003.node.md
│   ├── 0003.csv
│   ├── 0004.node.md
│   └── 0004.png
├── someB.node.md
└── folderC/
    ├── index.node.md
    ├── someSmallA.node.md
    └── someC.node.md
```

目录规则：

- 每个真实容器目录恰好有一个 `index.node.md`。
- 最近祖先目录中的 `index.node.md` 是父 Node。
- 大 PDF 是容器，完整内容由有序 children 覆盖。
- PDF children 使用 `0001`、`0002` 等四位前缀表达顺序。
- 大 PDF 不生成重复的聚合全文。
- 路径表示位置和树关系，稳定 `id` 表示跨重命名身份。

## 3. 统一 Node 格式

每个 Node 只有一个 `*.node.md`：

```text
.node.md
├── YAML frontmatter   身份、发现信息、溯源和类型数据
└── Markdown body      Agent 选中 Node 后读取的完整文字内容
```

通用格式：

```md
---
spec: "reindex/node@0.1"
id: "019f9c2a-..."
kind: "text"
title: "第一部分：项目概况"
description: "说明项目背景、建设目标和实施范围。"
source:
  uri: "raw://someLargeA.pdf"
  sha256: "64 位小写十六进制"
---
这里是 Node 的完整可读内容。
```

`source.locator`、`resource`、`warnings` 和 `table` 按 Node 类型条件添加，见后续示例。

字段：

| 字段 | 规则 |
|---|---|
| `spec` | 必需，固定为 `reindex/node@0.1` |
| `id` | 必需，稳定逻辑身份，不能使用路径或内容 hash |
| `kind` | 必需，决定搜索、读取和查询方式 |
| `title` | 必需，browse 和搜索结果标题 |
| `description` | 必需，简短说明这是什么、能回答什么 |
| `source` | 有原始来源的 Node 必需；纯目录可省略 |
| `resource` | 派生的非 Markdown 主资源与 source 不同时出现 |
| `warnings` | 可选，只写真实且影响使用的问题 |
| `table` | `kind: table` 必需 |

YAML 规则：

- UTF-8、LF，文件第一行必须是 `---`。
- 使用 YAML 1.2 的 JSON 兼容数据模型。
- 禁止 anchor、alias、merge key、自定义 tag、多文档和重复 key。
- closing `---` 后的全部字节是 Markdown body。
- 程序不得从 Markdown 标题推断 ID、类型或来源。

## 4. Node 类型与文件内容

| kind | body | resource |
|---|---|---|
| `group` | Collection、目录或大 PDF 的总体介绍，可为空 | 无 |
| `text` | PDF 章节、小 PDF、Markdown 或 TXT 的完整正文 | 无 |
| `table` | 表格说明和最多 5 行真实预览 | 派生 CSV；原始 CSV 可直接使用 source |
| `image` | 完整视觉描述和 OCR | 派生图片；原始图片可直接使用 source |
| `file` | Agent 可读说明或提取文本 | 其他二进制资源 |

不生成 Chunk 级 `retrieval_context`。数据库可以从完整 body 派生普通 chunk，但 chunk 不是 Node，也不写回文件。

## 5. 文本和 PDF

小 PDF 使用一个 `text` Node；大 PDF 使用一个 `group` 加语义章节 children。

章节示例：

```md
---
spec: "reindex/node@0.1"
id: "019f-pdf-a-section-1"
kind: "text"
title: "第一部分：项目概况"
description: "说明项目建设背景、总体目标和实施范围。"
source:
  uri: "raw://someLargeA.pdf"
  sha256: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  locator:
    pages: [1, 12]
---
# 第一部分：项目概况
这里必须按原有标题、段落和列表保存第 1–12 页的完整解析正文，而不是预览。
```

大 PDF 的 `index.node.md` 只保存整份文档介绍和原始 PDF source，不复制 children 正文。

## 6. 表格

完整数据只保存在 CSV。表格 Node 必须让 Agent 不打开全部 CSV 也能理解表格。

```md
---
spec: "reindex/node@0.1"
id: "019f-pdf-a-table-3"
kind: "table"
title: "各地区项目预算"
description: "记录各地区项目数量、预算金额和资金来源，可用于预算汇总与比较。"
source:
  uri: "raw://someLargeA.pdf"
  sha256: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  locator:
    pages: [31, 33]
resource:
  uri: "./0003.csv"
  media_type: "text/csv"
  sha256: "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
table:
  row_count: 128
  grain: "每行代表一个地区在一个预算年度的项目汇总"
  columns:
    - name: "年度"
      type: "integer"
      description: "预算所属年度"
    - name: "地区代码"
      type: "string"
      description: "行政区划代码，必须保留前导零"
    - name: "预算金额"
      type: "decimal"
      description: "项目预算总额"
      unit: "万元"
  primary_key: ["年度", "地区代码"]
warnings:
  - "原始表格存在跨页表头，CSV 已规范化为单层列名"
---
## Preview
| 年度 | 地区代码 | 预算金额 |
|---:|---|---:|
| 2024 | 110000 | 12500.00 |
| 2024 | 310000 | 9800.50 |
| 2024 | 440000 | 18320.00 |
```

表格规则：

- `row_count` 是不含 header 的精确行数。
- `grain` 说明一行代表什么。
- `columns` 必须覆盖 CSV 全部列，名称和顺序与 header 一致。
- 每列必须有 `name`、`type`、`description`；`unit` 条件可选。
- 类型只使用 `string/integer/decimal/boolean/date/datetime`。
- 代码、前导零或混合格式列使用 `string`。
- `primary_key/foreign_keys` 只有在有权威依据时填写，禁止 AI 猜测。
- Preview 最多 5 行，所有单元格必须逐字来自 CSV。
- 相同 CSV 必须生成相同 Preview，validator 必须验证 Preview 行存在。
- Preview 用于理解，CSV 才是完整权威数据。
- 从 PDF 裁剪的同一表格高清图是 `table` Node 的视觉参考，不是独立的
  `image` Node。它使用与 Node 相同的编号（如 `0003.png`），并从表格
  Node body 的 `## Visual reference` 链接；CSV 仍是表格的权威资源。

原始 CSV（如 `someB.csv`）本身就是查询资源时，不复制 CSV，只在 `source` 指向它。

## 7. 图片

```md
---
spec: "reindex/node@0.1"
id: "019f-pdf-a-image-4"
kind: "image"
title: "项目建设流程图"
description: "展示项目从申报、审核、建设到验收的完整流程。"
source:
  uri: "raw://someLargeA.pdf"
  sha256: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  locator:
    pages: [42, 42]
resource:
  uri: "./0004.png"
  media_type: "image/png"
  sha256: "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
---
## Description
这是一张从左到右排列的流程图，四个阶段使用箭头依次连接。
## OCR
项目申报
材料审核
项目建设
竣工验收
```

原始图片未转换时直接使用 source，不重复图片文件。没有可见文字时省略 `## OCR`。

## 8. 解析与校验

Validator 至少检查：

1. frontmatter 语法和 JSON Schema。
2. Node ID 全局唯一。
3. source/resource URI 合法，SHA-256 匹配。
4. source locator 在原始文件范围内。
5. 每个容器目录与 `index.node.md` 一一对应。
6. PDF 子节点编号唯一、连续，且没有重复聚合全文。
7. CSV 为 UTF-8，第一行是非空、唯一 header。
8. `row_count` 等于 CSV 实际行数。
9. `columns` 与 CSV header 名称、数量和顺序一致。
10. Preview 行真实存在于 CSV。
11. 主键、外键引用的 Node 和列存在。

Node 当前版本由导入器计算，不在文件中保存 `revision`：

```text
node_hash = SHA-256(normalized frontmatter + body + resource sha256)
```

## 9. 数据库与搜索

原始字节上传对象存储；Node、body 和树关系导入 PostgreSQL。

搜索索引：

- `title`：高权重。
- `description`：中高权重。
- `body`：正常权重。
- `breadcrumb`：中权重，由目录树派生。
- 表格额外索引 `grain`、列名、列说明、单位、Preview 和 CSV header。
- 表格行进入全文索引；是否全部建立向量由真实查询评测决定。

数据库派生而不写回 Node：`path`、`parent_id`、`order`、`node_hash`、文本 chunks、
PostgreSQL `tsvector`、embeddings、图片尺寸等可重算统计和索引构建日志。

不生成 Chunk 级 `retrieval_context`。

## 10. 明确不采用

- `.card.md`
- 文本 Node 对应的第二个 `.md`
- `.context.md`、`.ocr.md`、`.preview.md`
- 独立 `.schema.json`
- `children/`、`representations/`、`pages/`
- `revision`、`coverage`、显式 `parent/order`
- `uses`、`questions`、`keywords`
- 无边界的通用 `metadata`
- 每个 Node 重复的 `generated_by`

协议稳定后，再实现 loader、JSON Schema、validator、数据库导入和真实检索评测。
