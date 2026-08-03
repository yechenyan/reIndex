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
    ├── .rei/
    ├── report.pdf
    ├── customers.csv
    └── reIndex.md
```

`reIndex.md` 整个文件可选；没有它时，`rei` 递归发现普通文件并按 `auto` 解析。需要特殊处理时，可使用
[`reindex/input@1.0`](reference/reindex-input-v1.0.md) frontmatter 确定地覆盖 item、声明
`part_of`/`derived_from` 关系或解析开关；Markdown body 只提供非机器说明且不参与编译。它是构建输入，
不是 Node 或最终 package 文件。

```bash
rei init data/test1 --name test1 --agent codex
rei inspect data/test1
rei scan data/test1
rei push data/test1
```

`init` 建立稳定身份边界并安装或更新 Agent skills，`inspect` 让 Agent 在写入前核对真实文件与 manifest，
`scan` 使用确定性流水线生成并校验 package，`push` 提交完整 manifest、只上传缺失 blob，并原子发布新版本。PDF 由
Docling 本地解析；存在文本层时不启用 OCR，缺少文本时才以 Docling OCR 重试。
`push` 会再次执行完整 package check；单独运行 `check` 主要用于 Agent 修改 card 后的复检或 CI 门禁。

## 2. 生成 ReIndex package

```text
reIndex/
└── <collection-id>--test1/
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
- 相同 SHA-256 的字节只保存一个 object；不同 URI 的 source/content 仍保留各自的逻辑 resource。
- PostgreSQL 保存 Collection 当前态、Node 树、卡片、resource 关系和检索投影。
- 导入完成全部验证和索引后在一个事务中替换当前态；失败事务保留原有 Node 数据。
- 每个成功提交保存轻量 manifest/version；搜索只读 active，历史版本可 diff、pull、get 或整体 rollback。

## 4. Agent 工具

- `pull`：下载只有 `.node.md` 的完整 Node tree，供 Agent 浏览 Collection 结构和顺序。
- `fetch/history/diff`：只取得并比较远端版本元数据，不在线搜索历史版本。
- `rollback`：把 retained manifest 作为新的完整 head 发布，不改写旧版本。
- `search`：融合 BM25、向量召回和重排，返回可追溯 Evidence 与建议的 get 参数。
- `grep`：在 content 和表格行中进行受限字面或正则搜索。
- `get`：按 `source/content/asset/card` 精确取得真实文件，并优先复用本地文件和 SHA-256 cache。
- `table query`：使用 DuckDB 对 table content 执行受限只读 SQL。

用户使用 Collection name，而不是 UUID：

```bash
rei pull test1 --output ./test1-nodes
rei search "investment plan" --remote test1
rei get report/00003--investment.node.md --target content
```

`pull` 只拉取完整 Node tree；source/content/assets 由 `get` 按需从本地、SHA-256 缓存或远端精确取得。

完整 package 规则见 [`reference/reindex-v1.0-standard.md`](reference/reindex-v1.0-standard.md)。
