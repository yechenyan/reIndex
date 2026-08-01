# ReIndex 产品概览

ReIndex 把本地文件转换成可移植、可追溯、可搜索和可查询的 Agent 知识包。

## 核心对象

- Collection 是数据隔离和搜索的最小范围，同时也是一个根 Node。
- Node 是稳定的逻辑对象，使用 UUID 身份、显式顺序和数据卡片。
- source 是原始文件。
- content 是 Node 的主要可读或可查询内容。
- assets 是附属文件，使用通用编号，具体用途写在 Node card 的 role 中。
- resource 是文件上传后的服务器对象，不写入本地 package。

## 1. 准备 Collection

每个 Collection 有自己的源数据目录：

```text
data/
└── test1/
    ├── report.pdf
    ├── customers.csv
    └── reIndex.md
```

`reIndex.md` 可以为生成过程提供目录说明和解析上下文，但不是 Node 协议文件。

## 2. 生成 ReIndex package

```text
reIndex/
└── test1/
    ├── index.node.md
    └── report/
        ├── index.node.md
        ├── 00001--introduction.md
        ├── 00001--introduction.node.md
        ├── 00002--network-map.png
        ├── 00002--network-map.node.md
        ├── 00003--investment-plan.csv
        ├── 00003--investment-plan.assets001.png
        └── 00003--investment-plan.node.md
```

Collection、目录和大文档使用 `index.node.md`。普通 Node 的 `.node.md` 只保存身份、
结构、溯源和数据卡片；完整 Markdown、CSV 或图片由 `content` 引用。

文件使用五位编号加短名称，便于人工浏览。机器关系始终由 frontmatter 的显式 URI、ID、
parent 目录和 order 决定，不能从文件名猜测。

## 3. 上传和索引

```text
package files ──SHA-256──> local content-addressed resources
Node cards ──────────────> PostgreSQL/ParadeDB
content/card/table rows ─> BM25 + embeddings
CSV/Parquet ─────────────> DuckDB read-only query
```

- source、content、assets 和原始 `.node.md` 字节进入 `REINDEX_DATA_DIR`。
- 相同 SHA-256 只保存一个 resource；原始 CSV 的 source/content 复用同一 resource。
- PostgreSQL 保存 Collection 当前态、Node 树、卡片、resource 关系和检索投影。
- 导入完成全部验证和索引后在一个事务中替换当前态；失败事务保留原有 Node 数据。

## 4. Agent 工具

- `search`：融合 BM25、向量召回和重排，返回可追溯 Evidence。
- `grep`：在 content 和表格行中进行受限字面或正则搜索。
- `browse`：浏览 Collection 的 Node 树和顺序。
- `get`：读取 Node card 和 content 元信息。
- `download`：按 `source/content/asset/card` 下载真实文件。
- `query`：使用 DuckDB 对 table content 执行受限只读 SQL。

完整 package 规则见 [`reference/reindex-v1.0-standard.md`](reference/reindex-v1.0-standard.md)。
