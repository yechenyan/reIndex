# ReIndex HTTP API

基础地址例如 `http://127.0.0.1:8000`。Collection name 是用户标识，Collection UUID 是稳定内部身份；
`version_id` 标识一次提交，`package_hash` 标识内容。OpenAPI 位于 `/openapi.json`，Scalar 交互文档位于
`/docs`。

HTTP v1 采用契约优先流程。机器可读的权威契约是
[`packages/server/src/reindex_server/openapi/reindex-http-v1.yaml`](../../packages/server/src/reindex_server/openapi/reindex-http-v1.yaml)；
本页解释跨接口语义，不重复充当第二份 Schema。接口变更必须先修改权威契约，再修改 FastAPI 实现，并运行
`uv run python scripts/check_http_contract.py`。`/v1` 内不得删除字段、改变已有字段类型或收紧已有请求；破坏性
变更使用新的 API major version。

## 接口

| 方法与路径 | 类型 | 用途 |
| --- | --- | --- |
| `GET /health` | — | 服务状态。 |
| `GET /v1/collections` | — | 列出当前服务中的 Collection 及 active 状态。 |
| `POST /v1/nodes/browse` | JSON | 按 Collection 浏览直接 children 或完整 Node tree。 |
| `POST /v1/push` | JSON | 检查 base 与完整目标 manifest，创建上传 session。 |
| `POST /v1/push/blob` | multipart | 上传 session 声明的一个缺失 blob。 |
| `POST /v1/push/commit` | JSON | 二次检查 base，完整验证并原子发布。 |
| `POST /v1/fetch` | JSON | 返回 active 或指定历史版本及 manifest。 |
| `POST /v1/history` | JSON | 分页列出 retained versions。 |
| `POST /v1/pull` | JSON | 下载 active/历史版本的 Node-only ZIP。 |
| `POST /v1/get` | JSON | 下载 active/历史版本的精确 resource。 |
| `POST /v1/search`、`/v1/grep` | JSON | 只查询 active version。 |
| `POST /v1/tables/query` | JSON | 对 active table CSV 执行受限 SELECT/CTE。 |

Explore 页面先使用 `GET /v1/collections` 发现 Collection，再请求
`POST /v1/nodes/browse`。browse 请求使用 Collection name；`parent_node_id=null` 从根开始，
`recursive=true` 返回完整树，`false` 只返回直接 children。Node card 和真实内容继续通过现有
`POST /v1/get` 的 `target=card|content|source|asset` 取得。

## 三阶段 push

开始请求提交完整状态，不提交差异：

```json
POST /v1/push
{
  "name":"test2",
  "collection_id":"76abf08f-83b0-4406-be38-cf3a9bb4bb80",
  "base_version_id":null,
  "message":"Initial import",
  "operation":"publish",
  "dry_run":false,
  "manifest":{
    "spec":"reindex/transport@1.0",
    "package_root":"76abf08f-83b0-4406-be38-cf3a9bb4bb80--test2",
    "files":[{
      "namespace":"package",
      "logical_path":"index.node.md",
      "sha256":"<64 lowercase hex>",
      "byte_size":123,
      "media_type":"text/markdown"
    }]
  }
}
```

响应含 `upload_id`、`head_version_id`、`missing_blobs`、`expires_at` 和 `no_op`。上传缺失对象：

```text
POST /v1/push/blob
multipart: upload_id=<uuid>, sha256=<digest>, blob=@<file>
```

对象 hash/size 必须等于 manifest。最后提交：

```json
POST /v1/push/commit
{"upload_id":"..."}
```

commit 在 Collection 事务锁内再次比较 session base 与 active head，验证完整 package/raw 集合，重算
`package_hash`，完整重建 active SearchUnit/BM25 投影，复用 embedding cache，写 version 并切换 active。
同内容重复 publish 是 no-op；并发 session 的后提交者返回 `409 stale_base`。服务端不 merge/rebase。

## Fetch、history 与回滚

```json
POST /v1/fetch
{"collection":"test2","version_id":"<optional uuid>"}
```

响应含 version metadata 与完整 transport manifest。`history` 请求为
`{"collection":"test2","limit":20,"cursor":null}`，版本摘要含 parent、message、operation、stats 和
`is_active`。默认保留 active、最近 10 版以及最近 30 天版本；对象在无 retained manifest/session 引用并超过
24 小时宽限后才可回收。

没有服务端 rollback 端点。CLI fetch 目标历史 manifest，以当前 head 为 base 走普通三阶段 push，并设置
`operation=rollback/source_version_id=<old>`；它创建新的 head，不改写旧历史。

## Pull 与 get

`POST /v1/pull` 请求 `{"collection":"test2","version_id":"<optional>"}`。响应 ZIP 只包含原始
`.node.md`，响应头含 `X-ReIndex-Version-ID` 与 `X-ReIndex-Package-Hash`。

`POST /v1/get` 通过 `node_path`/`node_id` 加 `target=card|source|content|asset`，或通过 `raw_uri` 选择资源；
可增加 `version_id` 精确读取 retained version。asset ordinal 从 1 开始。响应含 `ETag`、
`X-ReIndex-SHA256`、长度和媒体类型。

## Search 与表查询

search 支持 lexical、semantic、hybrid、filters 和 ranking；Evidence 的 `unit_type` 为
`card/content_text/table_row`。grep、search 与 table query 始终读取 active version，不接受历史版本参数。
表查询把目标 CSV 注册为 `data`，拒绝非单条 SELECT/CTE、外部文件访问和扩展安装。

## 错误

```json
{"error":{"code":"stale_base","message":"...","request_id":"...","details":[{"base_version_id":"...","head_version_id":"..."}]}}
```

常见状态：`400` 内容/path/cursor 无效；`404` Collection/version/resource 不存在；`409 stale_base` 或
name/state 冲突；`422` schema 错误；`500` 未预期错误。只有 commit 全部成功才返回 `200 ready`。
