# 后端服务设计（v0.1）

状态：首期开发已实现；本设计不改变 [`reindex/node@0.1`](../reference/reindex-v0.1-standard.md)。

ReIndex package 是协议真相：原始字节和派生资源在对象存储，PostgreSQL 保存
可从 package 重建的服务层。导入器绝不把 `path`、树关系、chunk 或索引结果写回
`.node.md`。

## 范围与术语

- **blob**：以 SHA-256 去重的原始文件或 resource；对象存储保存字节，数据库只保存
  元数据和 object key。
- **raw path**：collection 内相对根目录的文件路径，例如 `reports/2026/a.pdf`。目录由路径
  派生，不单独建 Node；禁止绝对路径、`.`、`..` 和符号链接。
- **collection**：隔离、授权和检索的最小范围，且只存在于根目录。它的 ID 就是根 Node
  的稳定 `id`；根 Node 仍是普通的 `group` Node，有相同的 title、description、body 和
  source 规则，不引入 `kind: collection`。
- **rawIndex**：任务中的旧称，统一定义为“完整 ReIndex package archive”，不是另一种
  Node 格式。上传 archive 必须包含 `index.node.md`、Node 文件和资源，并通过 v0.1
  validator。
- **ready revision**：已验证、已建好最小可查询索引的 revision。搜索始终读取 package
  的 current ready revision；失败导入绝不影响旧版本。

本期采用 S3-compatible 对象存储、PostgreSQL 16+、`vector`、`pg_trgm`、`unaccent`
扩展。每个 collection 可有多次不可变的导入 revision，且只能查询自己的 current ready
revision。身份认证和租户策略尚未定义；首次实现必须在所有 collection 路由前确定它，不能
让 URL 参数替代访问控制。

当前可运行的开发适配器把对象字节保存在 `.reindex-data/`，并在进程内保存 catalog；它用于
本地测试和接口联调。`reindex-server init-db` 会在 PostgreSQL 中安装下述 serving schema。
生产接入必须把 catalog/index 写入该 PostgreSQL schema，并将 `FileStore` 换成 S3 adapter；
这两项基础设施配置不由 HTTP 客户端决定。

## 数据架构

| 层 | 表 / 存储 | 责任与关键约束 |
| --- | --- | --- |
| 对象 | `blobs`, `raw_files` + object storage | `sha256` 主键、byte size、media type、object key；`raw_files` 以 `(collection_id, raw_path)` 绑定 blob，保存上传目录结构；服务端流式计算 hash，重复上传幂等。 |
| 导入 | `collections`, `collection_revisions` | `collections.root_node_id` 是普通根 Node 的 ID；最新 revision 记录 `queued/validating/indexing/ready/failed` 与进度；只有 ready revision 可成为 `current_revision_id`。 |
| canonical 投影 | `source_versions`, `nodes`, `node_resources`, `table_catalog`, `table_columns` | Node 保留 frontmatter/body/source/locator；每行有 `collection_id`；`UNIQUE(revision_id,node_id)`、`UNIQUE(revision_id,path)`、`UNIQUE(revision_id,parent_node_id,ordinal)`。 |
| 检索投影 | `search_units`, `unit_embeddings`, `index_jobs` | Node metadata、结构化文本 chunk、表格 metadata 与表格行都是可重建 unit；保存逐字原文、上下文、行/字符范围和 locator。 |

`nodes` 的 `parent_node_id`、`path`、`depth`、`ordinal`、`breadcrumb` 和 `node_hash` 都
由 archive 路径和 Node 内容计算。根 Node 没有特权字段，只是 `collections.root_node_id`
指向的普通 Node；导入 archive 的根 Node ID 必须与目标 collection 一致。`source_versions`
将 v0.1 的 `raw://` URI + SHA-256 映射至同 collection 的 `raw_files.raw_path` 和 blob；
`node_resources` 同样绑定 `resource`。`table_catalog` 保存 CSV blob、grain、
row_count；CSV 仍是表格的权威数据，不能转换成可编辑业务表。

raw 上传仅保存 collection 内的原始目录树，不直接建检索索引。导入 ReIndex archive 时，
服务以 `raw://` 路径验证它们存在于同 collection，随后才建立 Node、文本和向量索引。
raw CSV 只要被 `table` Node 作为 source/resource 引用，就按 table metadata 和每一行建索引。

导入顺序如下：安全解包（拒绝 traversal、symlink、超限 archive）→ 协议验证（Node ID、
hash、树、CSV/preview 等）→ blob 绑定和 canonical 投影事务写入 → 切分/索引 → 全部
成功后原子切换 current revision。索引、失败原因和 embedding 缓存都可删后重建。

## 全文与向量索引

每个 Node 至少有一个 metadata unit；正文按 Markdown 标题、段落、列表和表格边界切分，
目标 400–800 tokens，仅在自然边界保留 60–120 token overlap。`contextual_text` 前置
breadcrumb、Node 标题和章节层级供检索；返回的 Evidence 只能引用逐字 `original_text`。
大 PDF 的 group Node 不复制 child 正文。

| 通道 | PostgreSQL 实现 | 初始策略 |
| --- | --- | --- |
| `lexical` | `search_units.tsv` 的 GIN；`websearch_to_tsquery` + `ts_rank_cd` | title=A；description、breadcrumb、table grain/列=B；正文/表格行=C。按 package language 选 text config，默认 `simple`。 |
| literal | `pg_trgm` GIN（title、path、规范化原文） | 编号、金额、型号、短语和中文子串的补充召回；正则另走受限 `/grep`。 |
| `semantic` | `unit_embeddings.embedding vector(1024)` 的 HNSW cosine index | 初始 profile 为本地部署 `Qwen/Qwen3-Embedding-0.6B`，输出 1024 维；以 `content_hash + profile` 缓存。换维度时新建列/索引并双写或重建，不能混入同一 ANN index。 |
| `hybrid` | 两通道各取候选，再按 weighted RRF 融合 | 先取 100 个 unit，`1/(60 + rank)` 融合，按 Node 去重且每 Node 最多保留 2–3 个证据。 |

表格必须建立 metadata、行级全文 unit 和行级 embedding；query rewrite、reranker、页面/图像
embedding 均由评测后以 profile 开关启用，不是 v0.1 的硬依赖。embedding 在服务端的本地
worker 中运行 `Qwen/Qwen3-Embedding-0.6B`，客户端不持有模型或 API key，待索引文本
也不离开部署环境。Qwen3-Embedding 支持查询指令和 Matryoshka（MRL）输出维度；profile
必须固定模型 revision、1024 output dimensions、document/query 的 task instruction 和归一化
方式。所有 document 与 query 都必须使用同一 profile。

选择 0.6B 而不是 BGE-M3：ReIndex 已用 PostgreSQL 维护词法索引，BGE-M3 的 sparse head
不会成为首期主通道；Qwen3 有 32K 上下文和指令化 query，同时 0.6B 权重与运行内存适合
8GB 以下的服务实例。若未来部署资源提高，4B/8B 必须作为独立 profile 重新建向量，不能与
0.6B 向量混检。上线前用标注查询集比较 0.6B@1024 与更大 profile 的 Recall/NDCG、P95 和
索引体积，再决定是否升级。中文高质量全文检索仍需要部署确认的分词器或应用层分词，不能
假定托管 PostgreSQL 支持某个扩展。

## HTTP API

所有接口位于 `/v1`，使用稳定的动作型路径，**不在 URL path 或 query string 中放 ID、
Node ID、文件路径或筛选条件**。除上传外，参数都放在 JSON body；上传使用 multipart form
fields；下载也用 `POST`，其 response 为文件流。列表和检索使用 body 内的 cursor、`limit`
（最大 50）和响应字节上限。导入、embedding 和重建在 collection 内异步执行；同一
collection 同时只允许一次导入，状态直接显示在 collection 上，避免额外的 job/status API。

| 类别 | 端点 | 行为 |
| --- | --- | --- |
| 建立 collection | `POST /collections/create` | multipart 的 `root_node`；其 `id` 成为 `collection_id`，根 Node 的内容和类型不变。初始状态为 `draft`，不能搜索。 |
| 原始文件 | `POST /raw/upload` | multipart 的 `collection_id`、`raw_path` 和 `file`；例如 `raw_path=reports/a.pdf` 对应 `raw://reports/a.pdf`。服务保留路径、计算 hash 并去重；同路径同内容重传幂等。 |
| 下载 raw | `POST /raw/download` | JSON 的 `collection_id`、`raw_path` 和 `disposition`（`inline` 或 `attachment`）；response 为文件流。 |
| rawIndex 导入 | `POST /reindex/import` | multipart 的 `collection_id` 和 `archive`；其根 Node 必须匹配 collection root，所有 `raw://` 引用必须匹配 collection 内 raw path。返回 202。 |
| 查询状态 | `POST /collections/status` | JSON 的 `collection_id`；返回 root Node、当前可搜索 revision，以及最新导入的状态/阶段/进度/失败原因；不需要 import ID。 |
| 搜索 | `POST /search` | JSON 的 `collection_id`、`query`、`mode`=`lexical|semantic|hybrid|auto`、kind/source/path filters、limit 和 `include_neighbors`。响应必须回显实际 mode/profile。 |
| Agent 工具 | `POST /grep`；`POST /nodes/browse`；`POST /nodes/get`；`POST /nodes/download`；`POST /tables/query` | JSON body 均含 `collection_id`；分别是受限字面/正则、browse、get、下载 Node 的 source/resource 和表格查询；不是第五种 `/search` mode。 |

`POST /collections/status` 的状态字段为 `draft`、`queued`、`validating`、`indexing`、
`ready` 或 `failed`。例如 `indexing` 返回当前阶段及 `nodes/chunks/csv_rows/embeddings` 的
已完成和总数；`failed` 返回安全的错误 code、文件 path 和 message。`ready` 才表示最新版
可搜索；导入失败时仍保持原 ready revision 可用。

`/search` 统一返回 `Evidence`：`node_id`、path、kind、title、逐字 excerpt、Node 行范围、
source SHA-256、locator（含页码）、命中 channel 和 rank。`auto` 对短编号/金额/引号短语
优先 lexical；其他自然语言用 hybrid；无可用 embedding 时明确降级为 lexical。

`POST /tables/query` 在 body 中接收 `collection_id`、`node_id`、`sql` 和 `params`，并在
隔离 DuckDB 会话中将目标 CSV 注册为只读 `data`。仅允许一条参数化 `SELECT`/CTE，禁用
写操作、扩展和任意文件路径，并硬限制 timeout、内存、行数和响应字节数。

## 分期与验收

1. **MVP**：collection 根 Node、按 raw path 上传与下载、archive validator、revision
   原子切换、Node tree、browse/get、lexical 与 `/grep`。
2. **语义检索**：本地 `Qwen/Qwen3-Embedding-0.6B` worker、chunk、semantic/hybrid/auto
   与 RRF；在标注集上确认 1024 维是否足够。
3. **表格**：行级 FTS 和向量、受限 DuckDB。
4. **增强**：reranker、查询改写和 PDF page/region 多模态索引，仅作为可观测 profile。

集成测试使用带 pgvector 的真实 PostgreSQL（SQLite 不能验证 FTS/ANN）。至少覆盖 hash
去重、失败导入不污染 current revision、协议校验、字段权重、RRF、权限先于召回、Evidence
可回链，以及 CSV query 的资源限制。上线前建立标注集并跟踪 Recall@5/10/20、MRR/NDCG、
精确字段召回、citation accuracy/coverage、P95 延迟和每查询成本。
