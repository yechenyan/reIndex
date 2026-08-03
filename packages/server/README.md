# reindex-server

ReIndex 1.0 的版本化 resource 存储、导入、搜索和查询 HTTP 服务。package 协议见
[`wiki/reference/reindex-v1.0-standard.md`](../../wiki/reference/reindex-v1.0-standard.md)，服务端模型见
[`wiki/dev/backend-service.md`](../../wiki/dev/backend-service.md)。

## 数据模型

服务端不保留旧上传接口兼容层。当前投影与轻量版本元数据为：

```text
collections → collection_versions → version_files
            ↘ nodes → node_resources → resources
```

- Collection name 是用户使用的唯一远端名称；内部 Collection ID 等于根 Node ID。
- Node 使用 `parent_node_id` 表示直接父节点，使用 `tree_path/order_path` 加速子树查询和稳定排序。
- source、content、card 和 assets 统一通过 `node_resources.role` 关联。
- `resources` 保存 Collection 内逻辑路径和本地对象元数据；对象 key 按 SHA-256 寻址并跨路径复用字节。
- `search_units/search_embeddings` 和 ParadeDB BM25 是可删除重建的派生投影。
- 每次提交保存不可变 manifest/version；只有 active version 投影到 Node、resource 和搜索表。
- embedding cache 按 profile 与 contextual text SHA-256 复用；SearchUnit/BM25 首版仍完整重建。

## 运行组件

- PostgreSQL/ParadeDB：Collection 当前态、Node 树、resource 关系、BM25 和 pgvector。
- 本地内容寻址存储：source、content、assets 和原始 `.node.md`。
- DuckDB：只把目标 table CSV 注册为 `data`，关闭外部文件访问后执行单条 SELECT/CTE。
- Qwen embedding：semantic/hybrid search；multilingual reranker 可按需启用。

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
uv run reindex-server run
```

Qwen embeddings 默认启用，需要安装 `reindex-server[embeddings]`。只运行 lexical/grep 时应显式设置
`REINDEX_EMBEDDINGS=disabled`。Reranker 默认关闭；设置
`REINDEX_RERANKER=minilm` 可按需启用，并同样需要模型依赖。

健康检查为 `/health`，OpenAPI 为 `/openapi.json`，Scalar 交互文档为 `/docs`。HTTP v1 的机器可读
权威契约是
[`src/reindex_server/openapi/reindex-http-v1.yaml`](src/reindex_server/openapi/reindex-http-v1.yaml)；
运行时 Schema 和文档都读取该文件。修改 HTTP 接口时必须先更新契约，再运行：

```bash
uv run python scripts/check_http_contract.py
```

该检查会从 FastAPI 路由重新生成 OpenAPI，并与权威契约逐项比较，防止实现和文档漂移。

## API

```text
GET  /v1/collections
POST /v1/nodes/browse
POST /v1/push                   POST /v1/push/blob
POST /v1/push/commit            POST /v1/fetch
POST /v1/history                POST /v1/pull
POST /v1/search                 POST /v1/get
POST /v1/grep                   POST /v1/tables/query
```

- `/collections` 列出当前 Collection 状态；`/nodes/browse` 为 Explore 客户端返回有序 Node 摘要。
- `/push` 接收完整 transport manifest 并返回缺失 blob；`/push/blob` 上传缺失对象，`/push/commit` 二次检查 base 后原子发布。
- `/fetch` 返回 head/历史 manifest；`/history` 返回 retained version 摘要。服务端不提供 merge 或历史 search。
- `/pull` 返回保持 Node path 的原始 `.node.md` 字节，不含 source、content 或 assets。
- `/get` 接受 Collection name、Node path/ID 或 `raw://` URI，精确返回一个 resource 和 SHA-256 响应头。
- `/search` Evidence 使用 `card/content_text/table_row` 明确 excerpt 类型，并返回建议 get target。

验证 fixture 位于 `testbase/test1/reIndex/test1/`，原始 PDF 位于 `testbase/test1/test1/`。
本地 ParadeDB、真实 HTTP E2E 测试步骤见
[`wiki/dev/testing.md`](../../wiki/dev/testing.md)，接口字段和示例见
[`wiki/reference/http-api.md`](../../wiki/reference/http-api.md)。
