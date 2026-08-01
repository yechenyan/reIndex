# reindex-server

ReIndex 1.0 的当前态 resource 存储、导入、搜索和查询 HTTP 服务。package 协议见
[`wiki/reference/reindex-v1.0-standard.md`](../../wiki/reference/reindex-v1.0-standard.md)，服务端模型见
[`wiki/dev/backend-service.md`](../../wiki/dev/backend-service.md)。

## 数据模型

服务端不保留 revision 或旧格式兼容层。四张核心业务表是：

```text
collections → nodes → node_resources → resources
```

- Collection ID 等于根 Node ID。
- Node 使用 `parent_node_id` 表示直接父节点，使用 `tree_path/order_path` 加速子树查询和稳定排序。
- source、content、card 和 assets 统一通过 `node_resources.role` 关联。
- `resources` 保存 Collection 内逻辑路径和本地对象元数据；对象 key 按 SHA-256 寻址并跨路径复用字节。
- `search_units/search_embeddings` 和 ParadeDB BM25 是可删除重建的派生投影。

## 运行组件

- PostgreSQL/ParadeDB：Collection 当前态、Node 树、resource 关系、BM25 和 pgvector。
- 本地内容寻址存储：source、content、assets 和原始 `.node.md`。
- DuckDB：只把目标 table CSV 注册为 `data`，关闭外部文件访问后执行单条 SELECT/CTE。
- Qwen embedding 和 multilingual reranker：semantic/hybrid search。

所有资源写入 `REINDEX_DATA_DIR` 下的内容寻址目录：

```bash
REINDEX_DATA_DIR=/srv/reindex-data
```

## 启动和初始化

`init-db` 是破坏性 baseline：删除旧表并创建 1.0 当前态 schema，只应在全新数据库或明确允许
重建的数据库运行。

```bash
DATABASE_URL=postgresql://... uv run reindex-server init-db

DATABASE_URL=postgresql://... \
REINDEX_DATA_DIR=/srv/reindex-data \
REINDEX_EMBEDDINGS=qwen \
uv run reindex-server run
```

不安装可选模型依赖、只运行 lexical/grep 时，应设置 `REINDEX_RERANKER=disabled`。semantic/hybrid 和
`REINDEX_RERANKER=minilm` 需要安装 `reindex-server[embeddings]`。

健康检查为 `/health`，OpenAPI 为 `/openapi.json`，交互文档为 `/docs`。

## API

```text
POST /v1/collections/create
POST /v1/raw/upload             POST /v1/raw/download
POST /v1/reindex/import         POST /v1/collections/status
POST /v1/nodes/browse           POST /v1/nodes/get
POST /v1/nodes/download         POST /v1/search
POST /v1/grep                   POST /v1/tables/query
```

- `/reindex/import` 只接受包含唯一 Collection 目录的 `reindex/node@1.0` archive。
- 导入先完成验证、对象上传、切块和 embedding，最后在一个数据库事务中替换 Collection 当前态；
  失败时旧 Node 数据保持不变，未引用对象由后续 mark-and-sweep 清理。
- `/nodes/browse` 默认返回直接 children；`recursive=true` 返回完整后代。
- `/nodes/download` 的 target 为 `card/source/content/asset`；asset 必须提供 `asset_ordinal`。
- `/search` Evidence 使用 `card/content_text/table_row` 明确 excerpt 类型。

验证 fixture 位于 `testbase/test1/reIndex/test1/`，原始 PDF 位于 `testbase/test1/test1/`。
本地 ParadeDB、真实 HTTP E2E 测试步骤见
[`wiki/dev/testing.md`](../../wiki/dev/testing.md)，接口字段和示例见
[`wiki/reference/http-api.md`](../../wiki/reference/http-api.md)。
