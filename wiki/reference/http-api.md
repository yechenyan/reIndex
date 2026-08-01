# ReIndex HTTP API（当前态）

基础地址由服务监听地址决定，例如 `http://127.0.0.1:8000`。所有业务接口均为 `POST /v1/...`，除
`GET /health` 外。交互式完整 schema 位于 `/docs`，OpenAPI JSON 位于 `/openapi.json`；本页说明稳定的
使用顺序和主要请求/响应字段。

## 请求流程

1. 以 multipart 上传根 `index.node.md` 创建 Collection。
2. 以 multipart 上传 package 中 `raw://` source 所引用的原始文件。
3. 以 multipart 上传只包含一个 Collection 目录的 `reindex/node@1.0` ZIP。
4. 轮询状态至 `ready`，再浏览、下载、搜索或查询表格。

`collection_id` 等于 package 根 Node UUID。导入是异步的；响应 `202` 只表示已入队，不能代表数据已可查。

## 端点

| 方法与路径 | Content-Type | 用途 |
| --- | --- | --- |
| `GET /health` | — | 存活检查，返回 `{status, version}`。 |
| `POST /v1/collections/create` | `multipart/form-data` | 上传 `root_node`（根 `index.node.md`），创建 draft Collection。 |
| `POST /v1/raw/upload` | `multipart/form-data` | 字段：`collection_id`、`raw_path`、`file`。同路径但不同字节返回 `409`。 |
| `POST /v1/raw/download` | JSON | 下载 `raw_path` 指向的原始 resource。 |
| `POST /v1/reindex/import` | `multipart/form-data` | 字段：`collection_id`、`archive`；异步验证并原子替换当前态。 |
| `POST /v1/collections/status` | JSON | 返回导入状态、当前 `package_hash`、进度和错误。 |
| `POST /v1/nodes/browse` | JSON | 默认查直接 children；`recursive: true` 查完整后代。 |
| `POST /v1/nodes/get` | JSON | 返回一个 Node 的 card、attributes 和 resource 元数据。 |
| `POST /v1/nodes/download` | JSON | 下载 Node 的 card/source/content/asset。 |
| `POST /v1/search` | JSON | ParadeDB lexical、semantic 或 hybrid 检索。 |
| `POST /v1/grep` | JSON | 在当前 Collection 的检索单元中进行 literal/regex 匹配。 |
| `POST /v1/tables/query` | JSON | 对 table Node 的 CSV 执行受限 DuckDB `SELECT`/CTE。 |

## 常用请求

创建与导入使用 multipart；这里的 UUID 仅为示例：

```bash
curl -X POST http://127.0.0.1:8000/v1/collections/create \
  -F 'root_node=@testbase/test1/reIndex/test1/index.node.md'

curl -X POST http://127.0.0.1:8000/v1/raw/upload \
  -F 'collection_id=056e95b3-aad8-4740-af7e-973356ec4e44' \
  -F 'raw_path=2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf' \
  -F 'file=@testbase/test1/test1/2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf'

curl -X POST http://127.0.0.1:8000/v1/reindex/import \
  -F 'collection_id=056e95b3-aad8-4740-af7e-973356ec4e44' \
  -F 'archive=@test1.zip'
```

查询状态、Node 与下载：

```json
POST /v1/collections/status
{"collection_id":"056e95b3-aad8-4740-af7e-973356ec4e44"}
```

```json
POST /v1/nodes/browse
{
  "collection_id":"056e95b3-aad8-4740-af7e-973356ec4e44",
  "parent_node_id":"be043b2f-0d57-40f7-aaa4-c7d6a99b55e6",
  "recursive":true
}
```

```json
POST /v1/nodes/download
{
  "collection_id":"056e95b3-aad8-4740-af7e-973356ec4e44",
  "node_id":"333563cf-1334-45a5-9d19-55f53f79757f",
  "target":"asset",
  "asset_ordinal":1,
  "disposition":"attachment"
}
```

`raw/download` 仅需要 `collection_id`、`raw_path` 和可选 `disposition`（`inline` 或 `attachment`）。
`nodes/download.target` 为 `card`、`source`、`content` 时不能带 `asset_ordinal`；为 `asset` 时必须带从 1
开始的 `asset_ordinal`。下载响应为文件字节，并带 `Content-Disposition`。

## Collection 与 Node 响应

创建或状态查询返回：

```json
{
  "collection_id":"...",
  "root_node_id":"...",
  "status":"draft|queued|validating|indexing|ready|failed",
  "package_hash":"sha256 或 null",
  "embedding_profile":"string 或 null",
  "progress":{"nodes":8,"resources":17},
  "error":null
}
```

`nodes/browse` 返回 `nodes` 数组，每项为 `id/path/parent_id/order/depth/kind/title/description`。`nodes/get`
额外返回 `card_markdown`、`attributes`、`node_hash` 和 `resources`；每个 resource 给出 `role`、`ordinal`、
`resource_id`、`namespace`、`logical_path`、`media_type`、`sha256`、`byte_size` 与可选 locator/asset 描述。

## 搜索与 grep

```json
POST /v1/search
{
  "collection_id":"...",
  "query":"Bielefelder",
  "mode":"lexical",
  "limit":10,
  "candidate_limit":100,
  "filters":{"node_ids":[],"kinds":[],"path_prefix":null,"subtree_node_id":null},
  "ranking":{"lexical_weight":0.5,"semantic_weight":1.0,"rrf_k":60,"max_per_node":3}
}
```

`mode` 可为 `lexical`、`semantic` 或 `hybrid`。semantic/hybrid 需要服务配置 embedding provider；lexical
依赖 ParadeDB BM25。filters 可按 Node IDs、Node kind、path 前缀或一个 subtree 过滤。响应含
`executed_mode`、`candidate_count`、`next_cursor` 和 `results`；每个结果有 `rank/score/channels/ranks/scores`
以及 Evidence。Evidence 的 `unit_type` 明确为 `card`、`content_text` 或 `table_row`，并给出 Node、resource、
excerpt、行号或文本行范围。

`POST /v1/grep` 与搜索一样必须指定 `collection_id`：

```json
{
  "collection_id":"...",
  "pattern":"Bielefelder",
  "regex":false,
  "case_sensitive":false,
  "limit":10
}
```

响应结构与搜索相同，`executed_mode` 为 `grep`。

## 表查询

```json
POST /v1/tables/query
{
  "collection_id":"...",
  "node_id":"333563cf-1334-45a5-9d19-55f53f79757f",
  "sql":"SELECT count(*) AS total FROM data",
  "params":[]
}
```

只有 kind 为 `table` 的 Node 可查询。CSV 在内存中注册为单张 `data` 表，响应为
`{"columns":[...],"rows":[...],"truncated":false}`。服务拒绝非单条 SELECT/CTE、外部文件访问和扩展安装。

## 错误

业务错误统一为：

```json
{"error":{"code":"not_found","message":"...","request_id":"...","details":null}}
```

常见 HTTP 状态：`400` 请求、SQL 或 cursor 无效；`404` Collection/Node/resource 不存在；`409` Collection
状态冲突或同一 raw path 字节不一致；`422` JSON/form 字段不符合 schema；`500` 未预期错误。导入校验失败
会在异步任务内写入 Collection 的 `failed` 状态和 `error`，HTTP `202` 本身仍表示成功入队。
