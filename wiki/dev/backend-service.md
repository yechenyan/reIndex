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

本期采用 S3-compatible 对象存储与 ParadeDB 0.24.3+。`pg_search` 提供 BM25，
`pgvector` 提供向量索引；不再维护 PostgreSQL `tsvector`、`pg_trgm` 或应用内搜索
实现。每个 collection 可有多次不可变的导入 revision，且只能查询自己的 current ready
revision。

对象字节的本地开发适配器仍保存在 `.reindex-data/`，但搜索没有进程内兜底。运行时必须
配置 ParadeDB，保存 collection、revision、Node、chunk、BM25 index 和 embedding；查询只读
active ready revision 并按 embedding profile 隔离。`reindex-server init-db` 安装 schema。

`FileStore` 仍是本地开发对象字节适配器；生产多实例部署前必须替换为 S3-compatible adapter。
这项对象存储配置与 PostgreSQL connection string 都不由 HTTP 客户端决定。

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
| `lexical` | ParadeDB `pg_search` BM25 covering index | `title`、`description`、`original_text` 使用 ICU 多语言 tokenizer，字段 boost 固定为 4:2:1；revision、Node、kind、path 和 row 字段进入同一索引供过滤。 |
| `semantic` | `unit_embeddings.embedding vector(1024)` 的 HNSW cosine index | 初始 profile 为本地部署 `Qwen/Qwen3-Embedding-0.6B`，输出 1024 维；以 `content_hash + profile` 缓存。换维度时新建列/索引并双写或重建，不能混入同一 ANN index。 |
| `hybrid` | ParadeDB BM25 与 pgvector 各取候选，在同一个 SQL 中做 weighted RRF，再把 multilingual MiniLM cross-encoder rank 加入同一融合 | 默认两路各取 100 个 unit，`weight/(60 + rank)` 融合，`id` 稳定打破同分；MiniLM 评估三种 mode 的前 20 个候选，但不覆盖召回分。仅当它的正分第一名明显领先第二名时，给予有上限的 bonus。响应返回 BM25、cosine、rerank、bonus、channel rank 与最终分数。 |

表格必须建立 metadata、行级全文 unit 和行级 embedding；页面/图像 embedding 和 query rewrite
均由评测后以 profile 开关启用。默认使用约 100M 参数的 multilingual MiniLM reranker；它对
RRF 前 20 个候选做 query-document pair 推理，并以 rank 融合，而非把原始模型分数当最终分。
它在服务 readiness 前预热。可用
`REINDEX_RERANKER=disabled` 关闭，或通过 `REINDEX_RERANK_LIMIT`、
`REINDEX_RERANK_BATCH_SIZE`、`REINDEX_RERANK_MAX_LENGTH` 与
`REINDEX_RERANK_WEIGHT` 调整其有界成本或影响力。embedding 在服务端的本地 worker 中运行
`Qwen/Qwen3-Embedding-0.6B`，客户端不持有模型或 API key，待索引文本
也不离开部署环境。应用启动时预热 embedding 模型，把一次性权重加载留在 readiness 之前。
Qwen3-Embedding 支持查询指令和 Matryoshka（MRL）输出维度；profile
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
所有 JSON request model 禁止未知字段，collection/Node ID 在 HTTP 边界按 UUID 验证。
`/docs` 和 `/openapi.json` 分别提供交互式文档和机器可读契约。

| 类别 | 端点 | 行为 |
| --- | --- | --- |
| 建立 collection | `POST /collections/create` | multipart 的 `root_node`；其 `id` 成为 `collection_id`，根 Node 的内容和类型不变。初始状态为 `draft`，不能搜索。 |
| 原始文件 | `POST /raw/upload` | multipart 的 `collection_id`、`raw_path` 和 `file`；例如 `raw_path=reports/a.pdf` 对应 `raw://reports/a.pdf`。服务保留路径、计算 hash 并去重；同路径同内容重传幂等。 |
| 下载 raw | `POST /raw/download` | JSON 的 `collection_id`、`raw_path` 和 `disposition`（`inline` 或 `attachment`）；response 为文件流。 |
| rawIndex 导入 | `POST /reindex/import` | multipart 的 `collection_id` 和 `archive`；其根 Node 必须匹配 collection root，所有 `raw://` 引用必须匹配 collection 内 raw path。返回 202。 |
| 查询状态 | `POST /collections/status` | JSON 的 `collection_id`；返回 root Node、当前可搜索 revision，以及最新导入的状态/阶段/进度/失败原因；不需要 import ID。 |
| 搜索 | `POST /search` | JSON 的 `collection_id`、`query`、`mode`=`lexical|semantic|hybrid`、`candidate_limit`、`filters`、`ranking` 和 `limit`。默认 `hybrid`，不做隐式 mode 切换或降级。 |
| Agent 工具 | `POST /grep`；`POST /nodes/browse`；`POST /nodes/get`；`POST /nodes/download`；`POST /tables/query` | `/grep` 接受 `pattern`、`regex`、`case_sensitive` 和 `limit`，独立执行受限字面/正则搜索；其余接口用于 browse、get、下载和表格查询。 |

`POST /collections/status` 的状态字段为 `draft`、`queued`、`validating`、`indexing`、
`ready` 或 `failed`。例如 `indexing` 返回当前阶段及 `nodes/chunks/csv_rows/embeddings` 的
已完成和总数；`failed` 返回安全的错误 code、文件 path 和 message。`ready` 才表示最新版
可搜索；导入失败时仍保持原 ready revision 可用。

`/search` 和 `/grep` 统一返回 `Evidence`：`node_id`、path、kind、title、逐字 excerpt、chunk
ordinal、行范围、表格 row、source SHA-256、locator（含页码）、命中 channel 和 channel rank。
`/search` 还返回最终 rank、BM25 score、cosine score、RRF score、实际 revision/profile、
`candidate_count`、`next_cursor` 与应用后的参数。cursor 绑定 query、filter、ranking 和
active revision；翻页保持全局 rank，任一绑定项改变时明确返回无效 cursor。`ranking`
默认 `lexical_weight=0.5`、`semantic_weight=1`、`rrf_k=60`、
`max_per_node=3`，并允许设置 cosine `semantic_threshold`。`candidate_limit` 默认 100，
范围 10–500，且不得小于最终 `limit`。

Evidence 的 Node 标识统一命名为 `node_id`。启用 reranker 时，`score` 是 lexical、semantic
与 rerank rank 的最终 weighted-RRF 融合分；否则 lexical 为 BM25，semantic 为 cosine
similarity，hybrid 为 weighted RRF。原始分量保留在 `scores.bm25`、
`scores.semantic`、`scores.rerank` 与可选 `scores.rerank_bonus`，不能跨查询比较绝对值。

所有 response 都包含 `X-Request-ID`，客户端可传入最多 128 字符的安全 request ID，否则
服务端生成。JSON error 统一为
`{"error":{"code","message","request_id","details?"}}`：业务参数或 cursor 错误为
`invalid_request`/400，schema validation 为 `invalid_request`/422，资源不存在为
`not_found`/404，collection 或模型状态冲突为 `conflict`/409，非预期异常为
`internal_error`/500。生产日志必须以相同 request ID 关联数据库与模型耗时。

当前 `POST /reindex/import` 只返回 collection ID 与 `queued`，进度由
`POST /collections/status` 查询；后台线程不是 durable job。引入持久化 worker 前，不承诺
进程崩溃后的自动恢复，也不提前暴露无法兑现语义的 job ID/cancel API。

`POST /tables/query` 在 body 中接收 `collection_id`、`node_id`、`sql` 和 `params`，并在
隔离 DuckDB 会话中将目标 CSV 注册为只读 `data`。仅允许一条参数化 `SELECT`/CTE，禁用
写操作、扩展和任意文件路径，并硬限制 timeout、内存、行数和响应字节数。

## 分期与验收

1. **MVP**：collection 根 Node、按 raw path 上传与下载、archive validator、revision
   原子切换、Node tree、browse/get、lexical 与 `/grep`。
2. **语义检索**：本地 `Qwen/Qwen3-Embedding-0.6B` worker、chunk、semantic/hybrid
   与 RRF；在标注集上确认 1024 维是否足够。
3. **表格**：行级 FTS 和向量、受限 DuckDB。
4. **增强**：查询改写和 PDF page/region 多模态索引，仅作为可观测 profile；MiniLM reranker
   已作为统一的第二阶段 rank-fusion 信号启用。精确表格条件应走受限 `/tables/query`，无答案
   则由答案层做证据校验/拒答，二者不应归因于重排。

集成测试使用带 pgvector 的真实 PostgreSQL（SQLite 不能验证 FTS/ANN）。至少覆盖 hash
去重、失败导入不污染 current revision、协议校验、字段权重、RRF、权限先于召回、Evidence
可回链，以及 CSV query 的资源限制。仓库的 `reindex-server eval-search` 读取 JSONL
标注集并对 lexical、semantic、hybrid 输出 Recall、MRR、NDCG、平均延迟、P50 与 P95。
上线前持续跟踪 Recall@5/10/20、MRR/NDCG、精确字段召回、citation accuracy/coverage、
P95 延迟和每查询成本。
