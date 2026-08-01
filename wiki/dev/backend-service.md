# 后端服务设计（ReIndex 1.0 当前态）

服务端只接受 [`reindex/node@1.0`](../reference/reindex-v1.0-standard.md)，不保留 revision、旧 schema
或数据迁移。本地 resource 目录保存字节，PostgreSQL/ParadeDB 保存当前业务状态和可重建检索投影，DuckDB
只执行受限 table content 查询。

## 1. 核心模型

```text
collections(id, name, status, package_hash, embedding_profile, progress, error)

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

Collection ID 等于根 Node ID。`nodes.collection_id` 是上传、授权、删除和查询的隔离字段；根 Node
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

## 3. 导入

1. 接收只包含一个 Collection 目录的 ZIP，拒绝 traversal、symlink 和重复 entry。
2. 验证 1.0 frontmatter、UUID、根 Node、parent/order、文件名、URI、SHA-256、CSV header/row count。
3. 解析 `raw://`，确认对应 raw resource 已上传且 hash 一致。
4. 将 card/content/assets 写入本地内容寻址目录；生成 Node、resource link 和 search unit。
5. 按需在数据库外生成 embedding。
6. 对 Collection 加事务级 advisory lock，在一个事务内删除旧当前态并插入新当前态。
7. PostgreSQL、BM25 和 embedding 写入全部成功后将 Collection 标为 ready。

失败事务回滚并保留之前仍可查询的 Node 当前态；Collection 状态记录失败原因。事务前写入但未被引用的
对象是安全孤儿，后续按数据库引用做 mark-and-sweep。服务端不提供历史回滚。

## 4. API 行为

| 端点 | 行为 |
| --- | --- |
| `/collections/create` | 上传不引用文件的 Collection 根 `index.node.md` |
| `/raw/upload` | 建立 `raw/<path>` resource；同路径异内容返回 conflict |
| `/reindex/import` | 异步验证并替换当前态 |
| `/collections/status` | 返回状态、package hash、进度和错误 |
| `/nodes/browse` | 默认直接 children；`recursive=true` 返回有序后代 |
| `/nodes/get` | 返回解析后的 card、attributes 和全部 resource 元信息 |
| `/nodes/download` | target=`card/source/content/asset`，asset 带 ordinal |
| `/search`、`/grep` | 返回带 `unit_type/resource_id/locator` 的 Evidence |
| `/tables/query` | 目标 CSV 注册为 `data`，只允许一条 SELECT/CTE |

DuckDB 连接关闭 external access、限制内存和线程；不暴露对象路径，也不允许 SQL 自行读取文件或安装扩展。

## 5. 存储配置

`REINDEX_DATA_DIR` 指定 resource 根目录，默认 `.reindex-data`。对象保存为
`objects/sha256/<前两位>/<次两位>/<完整 hash>`。生产必须把该目录放在持久卷上；本地文件存储只允许
单个服务实例写入，不能用于多实例水平扩容。

`init-db` 会删除现有 ReIndex 表再建立当前 baseline，是明确的破坏性命令。生产首次切换应使用全新
数据库或已经确认可全部重建的数据环境。

## 6. 验收

- `testbase/test1` 的 raw PDF 和 1.0 package 能完整上传、导入、浏览、下载、搜索和查询。
- 导入得到 8 个 Node；Browse order 为 1–6；两个 table 分别为 24 和 52 行。
- source/content/card/asset 下载字节与 fixture 完全一致。
- `card/content_text/table_row` Evidence 不混淆。
- 真实 ParadeDB BM25、pgvector 和 hybrid SQL 集成测试通过。
