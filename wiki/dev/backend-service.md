# 后端服务设计（ReIndex 1.0）

服务端只接受 [`reindex/node@1.0`](../reference/reindex-v1.0-standard.md)，不保留旧 schema 或上传接口兼容层。
本地 resource 目录保存 CAS 字节和 manifest；PostgreSQL 保存轻量版本链、active 当前业务状态和可重建检索投影，
DuckDB 只执行受限 table content 查询。

## 1. 核心模型

```text
collections(id, name, status, package_hash, embedding_profile, progress, error)

collection_versions(id, collection_id, parent_version_id, package_hash,
  manifest_sha256, message, operation, source_version_id, stats, created_at)

version_files(version_id, namespace, logical_path, sha256, byte_size, media_type, object_key)

nodes(
  collection_id, id, parent_node_id, ordinal, path,
  tree_path, order_path, kind, title, description,
  card_markdown, attributes, node_hash
)

resources(
  id, collection_id, namespace, logical_path, display_name,
  sha256, byte_size, media_type, object_key
)

node_resources(
  collection_id, node_id, role, ordinal, resource_id,
  locator, asset_role, description
)
```

Collection `name` 是用户使用且服务端唯一的远端名称；内部 ID 等于根 Node ID。`nodes.collection_id` 是上传、授权、删除和查询的隔离字段；根 Node
没有 parent/ordinal，其他 Node 的同父 ordinal 唯一且从 1 连续。

Node 不保存 `children_node_ids`。直接 children 使用
`(collection_id,parent_node_id,ordinal)` 索引；`tree_path uuid[]` 保存根到当前 Node 的 ID，GIN
索引支持子树查询；`order_path integer[]` 提供深度优先 package 顺序。

resource 是 Collection 内的逻辑文件，`namespace` 为 `raw/package`，逻辑路径在 namespace 内唯一。
本地 `object_key` 按 SHA-256 分层，不包含 title 或 display name；不同逻辑 resource 可引用同一对象
字节。数据库负责归属、URI 映射、权限和垃圾回收，文件目录本身不承担业务元数据。

`node_resources.role` 固定为 `card/source/content/asset`。card/source/content ordinal 为 0，asset
ordinal 从 1 连续；locator 属于 source 关系，asset role/description 属于 asset 关系。原始 CSV 作为 source、
package CSV 作为 table content 时是两个逻辑 resource；相同 SHA-256 使它们共享底层 object bytes。

## 2. 派生检索表

```text
search_units(
  id, collection_id, node_id, resource_id, unit_type,
  path, tree_path, kind, title, description, ordinal,
  row_number, start_line, end_line, locator,
  original_text, contextual_text
)

search_embeddings(search_unit_id, profile_id, embedding)
embedding_profiles(id, model, dimensions, config)
```

`unit_type` 为 `card/content_text/table_row`。title、description、kind、path 和 Collection/Node ID
在派生表中有意冗余，使一个 ParadeDB BM25 索引完成检索和过滤。图片和 assets 默认只通过 card
文字进入索引。表格 schema/grain 保存在 `nodes.attributes.table`，CSV 仍是权威数据，不建立业务行表。

## 3. 版本化增量 push

1. `POST /v1/push` 接收 Collection identity、base version 和完整 transport manifest，返回缺失 SHA-256。
2. `POST /v1/push/blob` 流式校验并保存 session 声明的缺失对象；相同 blob 幂等复用。
3. `POST /v1/push/commit` 在 Collection 事务锁内二次检查 base，避免 plan/commit 之间覆盖新 head。
4. 服务端物化完整 package/raw 集合，验证 1.0 frontmatter、树结构、URI、SHA-256 和 CSV 元数据。
5. 首版完整重建 SearchUnit/BM25 active 投影，但按 embedding profile + contextual text SHA-256 复用向量。
6. 同一事务写 `collection_versions/version_files`、完整替换当前投影并切换 `active_version_id`。

manifest 总是完整目标状态，只有字节传输是增量。失败不切 active；事务前孤儿对象由 retained manifest/session
mark-and-sweep 回收。服务端提供轻量历史与整体 rollback 所需原语，但不 merge/rebase、不保存多版搜索投影。

## 4. API 行为

HTTP v1 的权威接口契约是 package 内的 `openapi/reindex-http-v1.yaml`。开发顺序为先改契约，再改
FastAPI adapter；`scripts/check_http_contract.py` 会重新生成实现 Schema 并检查两者完全一致。Scalar 和
`/openapi.json` 直接读取权威契约，避免实现、文档和后续 SDK 各自生成不同接口。

| 端点 | 行为 |
| --- | --- |
| `/push`、`/push/blob`、`/push/commit` | 计划缺失对象、上传 blob、原子发布版本 |
| `/fetch`、`/history` | 返回 active/历史 manifest 与 retained version 摘要 |
| `/pull` | 按 name 和可选 version 返回只包含 Node cards 的 ZIP |
| `/get` | 按 Node path/ID、target 或 raw URI 精确下载 active/历史 resource |
| `/search`、`/grep` | 按 name 返回带 `unit_type/resource_id/locator` 的 Evidence |
| `/tables/query` | 目标 CSV 注册为 `data`，只允许一条 SELECT/CTE |

DuckDB 连接关闭 external access、限制内存和线程；不暴露对象路径，也不允许 SQL 自行读取文件或安装扩展。

## 5. 存储配置

`REINDEX_DATA_DIR` 指定 resource 根目录，默认 `.reindex-data`。对象保存为
`objects/sha256/<前两位>/<次两位>/<完整 hash>`。生产必须把该目录放在持久卷上；本地文件存储只允许
单个服务实例写入，不能用于多实例水平扩容。

`init-db` 会删除现有 ReIndex 表再建立当前 baseline，是明确的破坏性命令。生产首次切换应使用全新
数据库或已经确认可全部重建的数据环境。

## 6. 验收

- `testbase/test4-all` 的临时副本覆盖首传、no-op、增量 V2、stale base、本地冲突、历史 pull/get、rollback 和 embedding 复用。
- `testbase/test1` 的真实 HTTP E2E 导入 8 个 Node，并验证 24 行 table、raw/content 精确 get 和原始 Node card pull。
- Node path/order、source/content/card/asset 关系和 SHA-256 在 package 导入时完整校验。
- `card/content_text/table_row` Evidence 不混淆。
- 真实 ParadeDB BM25、pgvector 和 hybrid SQL 集成测试通过。
