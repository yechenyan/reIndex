# ReIndex HTTP API（当前态）

基础地址例如 `http://127.0.0.1:8000`。普通 CLI 工作流只需要四个业务接口：同步 push、Node-only pull、search 和精确 get。Collection 使用唯一 `name` 对用户寻址；根 Node UUID 仍是内部稳定 ID。

## 接口

| 方法与路径 | Content-Type | 用途 |
| --- | --- | --- |
| `GET /health` | — | 返回服务状态和版本。 |
| `POST /v1/push` | multipart | 同步上传 package ZIP 和 sources ZIP，验证、索引并返回 ready。 |
| `POST /v1/pull` | JSON | 按 Collection name 下载只包含 `.node.md` 的 ZIP。 |
| `POST /v1/search` | JSON | lexical、semantic 或 hybrid 检索。 |
| `POST /v1/get` | JSON | 按 Node path/ID 或 `raw://` URI 下载一个精确 resource。 |
| `POST /v1/grep` | JSON | 当前 Collection 内的 literal/regex 匹配。 |
| `POST /v1/tables/query` | JSON | 对 table Node 的 CSV 执行受限 DuckDB SELECT/CTE。 |

OpenAPI JSON 位于 `/openapi.json`，交互文档位于 `/docs`。

## Push

```bash
curl -X POST http://127.0.0.1:8000/v1/push \
  -F 'name=test2' \
  -F 'package=@package.zip;type=application/zip' \
  -F 'sources=@sources.zip;type=application/zip'
```

`package.zip` 必须包含唯一 Collection 目录。`sources.zip` 直接以 Collection-relative raw path 保存文件；其文件集合必须与 package 中全部 `raw://` 引用完全一致。服务端重新计算每个 SHA-256，并同步完成验证、检索投影和当前态写入。

```json
{
  "status":"ready",
  "name":"test2",
  "collection_id":"76abf08f-83b0-4406-be38-cf3a9bb4bb80",
  "package_hash":"...",
  "nodes":7,
  "sources":2,
  "resources":16,
  "search_units":1176,
  "embedding_profile":null
}
```

相同根 UUID 与新 name 表示改名；相同 name 已属于另一 UUID 时返回 `409`。同 raw path 的内容可在下一次完整 push 中更新。

## Pull

```json
POST /v1/pull
{"collection":"test2"}
```

响应为 ZIP，保持服务端 Node path，只包含根和后代的原始 `.node.md` card bytes，不含 source、content、assets 或 `.rei`。响应头 `X-ReIndex-Package-Hash` 给出当前快照 hash。

## Search

```json
POST /v1/search
{
  "collection":"test2",
  "query":"technology costs",
  "mode":"lexical",
  "limit":10,
  "candidate_limit":100,
  "filters":{"node_ids":[],"kinds":[],"path_prefix":null,"subtree_node_id":null},
  "ranking":{"lexical_weight":0.5,"semantic_weight":1.0,"rrf_k":60,"max_per_node":3}
}
```

每条结果含 `Evidence` 和可直接传给 get 的目标：

```json
{
  "evidence":{
    "node_id":"...",
    "path":"technology-costs-2020.node.md",
    "unit_type":"table_row",
    "excerpt":"..."
  },
  "get":{
    "node_id":"...",
    "node_path":"technology-costs-2020.node.md",
    "target":"content"
  }
}
```

`unit_type` 为 `card`、`content_text` 或 `table_row`。semantic/hybrid 需要 Collection 当前 embedding profile 与服务配置一致。

## Get

按 Node path 下载 content：

```json
POST /v1/get
{
  "collection":"test2",
  "node_path":"technology-costs-2020.node.md",
  "target":"content"
}
```

下载 asset 时增加从 1 开始的 `asset_ordinal`。也可以传内部 `node_id` 代替 path。直接下载 raw：

```json
POST /v1/get
{"collection":"test2","raw_uri":"raw://costs_2020.csv"}
```

响应头包含 `Content-Type`、`Content-Length`、`Content-Disposition`、`ETag` 和 `X-ReIndex-SHA256`。CLI 必须验证 SHA-256 后才写入缓存。

## Grep 与表查询

```json
POST /v1/grep
{"collection":"test2","pattern":"Bielefelder","regex":false,"case_sensitive":false,"limit":10}
```

```json
POST /v1/tables/query
{
  "collection":"test2",
  "node_id":"333563cf-1334-45a5-9d19-55f53f79757f",
  "sql":"SELECT count(*) AS total FROM data",
  "params":[]
}
```

表查询拒绝非单条 SELECT/CTE、外部文件访问和扩展安装。

## 错误

```json
{"error":{"code":"not_found","message":"...","request_id":"...","details":null}}
```

常见状态为：`400` package、path、SQL 或 cursor 无效；`404` Collection/Node/resource 不存在；`409` Collection name 冲突；`422` 请求字段错误；`500` 未预期错误。同步 push 只有完整成功才返回 `200 ready`。
