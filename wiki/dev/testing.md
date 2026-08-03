# 本地测试指南

本项目有两层测试：默认测试验证三阶段增量 push、版本冲突、协议校验、CLI 真实 HTTP 流程和服务逻辑；HTTP E2E 测试连接已经启动的真实
ParadeDB 与 Uvicorn 服务，验证实际网络 API。E2E fixture 固定使用
`testbase/test1/reIndex/test1`，并上传 `testbase/test1/test1` 内的 PDF。

## 常规检查

在仓库根目录执行：

```bash
uv sync
uv run python scripts/check_http_contract.py
uv run pytest -q
uvx ruff format --check packages tests
uvx ruff check packages tests
```

HTTP 契约检查从 FastAPI 路由重新生成 OpenAPI，并与 package 内的权威
`reindex-http-v1.yaml` 比较。新增或修改接口时先更新契约，再更新实现；未同步的路径、请求、响应、状态码或
媒体类型会使检查失败。

默认测试不要求 Docker。真实 ParadeDB 集成测试和 HTTP E2E 测试会在没有对应环境变量时跳过。

## CLI 与 raw → ReIndex fixture

CLI 的临时目录测试覆盖 Collection 创建和定位、只读 inspect/check、部分目录增量扫描、重命名后的
Node 身份复用、机器字段保护，以及 Agent 修改过的 card body 在后续 scan 中保留。

`testbase/test2-generage` 是 Docling-only 的真实 PDF/CSV fixture。提交前依次运行：

```bash
uv run rei inspect testbase/test2-generage
uv run rei scan testbase/test2-generage
uv run rei check testbase/test2-generage
uv run rei push testbase/test2-generage --api-url http://127.0.0.1:8000
uv run pytest -q tests/test_cli.py tests/test_cli_workspace.py
```

workspace 测试还会把 CLI 生成的 package 交给 server importer 读取，避免 CLI 与服务端协议各自通过、
组合后失败。PDF 有可用文本层时禁用 OCR；只有提取不到有效文本的扫描件才用 Docling OCR 重试。
Docling 首次使用某个本地模型时可能初始化或下载模型文件，后续扫描复用本机缓存，源文件不会因此
上传到外部服务。

## 启动本地 HTTP E2E 环境

以下命令创建一个专用、可删除的本地数据库。不要把 `init-db` 指向已有业务数据库：该命令会删除
ReIndex 表并重建 schema。端口 `55434` 与数据目录 `.reindex-data` 均可按需替换。

```bash
docker run --rm --name reindex-local-api-paradedb \
  -e POSTGRES_PASSWORD=reindex_local \
  -e POSTGRES_DB=reindex_local \
  -p 55434:5432 \
  paradedb/paradedb:0.24.3-pg18
```

在另一个终端初始化数据库并启动 API：

```bash
export DATABASE_URL='postgresql://postgres:reindex_local@127.0.0.1:55434/reindex_local'
export REINDEX_DATA_DIR="$PWD/.reindex-data"
export REINDEX_RERANKER=disabled

uv run reindex-server init-db
uv run reindex-server run --host 127.0.0.1 --port 8000
```

`REINDEX_RERANKER=disabled` 让基础开发环境只验证 ParadeDB lexical/grep，不下载或加载本地模型。若要验证
semantic/hybrid 与二阶段重排，请安装 `reindex-server[embeddings]`，设置 `REINDEX_EMBEDDINGS=qwen`，并将
`REINDEX_RERANKER` 设为 `minilm`；首次启动会下载模型。

服务就绪后，健康检查应返回 `{"status":"ok", ...}`：

```bash
curl http://127.0.0.1:8000/health
```

## 执行真实 HTTP E2E

保持 API 运行，在第三个终端执行：

```bash
REINDEX_E2E_BASE_URL=http://127.0.0.1:8000 \
  uv run pytest -q tests/test_api_e2e.py
```

完整版本流程还可指向同一真实服务：

```bash
REINDEX_E2E_BASE_URL=http://127.0.0.1:8000 \
REINDEX_VERSION_E2E_BASE_URL=http://127.0.0.1:8000 \
TEST_PARADEDB_URL="$DATABASE_URL" \
  uv run pytest -q
```

`TEST_PARADEDB_URL` 测试会执行破坏性的 schema 初始化，只能指向专用测试数据库，不能指向业务库。

E2E HTTP client 超时为 1800 秒，可覆盖首次在 CPU 上生成 embedding 的较慢情况。

该测试增量 push fixture 的 package 与 sources，然后断言 Node-only pull、content/raw 精确 get、
ParadeDB lexical search，以及 DuckDB `SELECT count(*)`。默认测试中的 `test_cli_http_flow.py` 还会在
真实本地 HTTP 端口模拟 test2 push、`test3-download` pull，以及复制 test2 数据后执行 test4 init/scan/push/search/get，
并验证同 raw path 的新内容可由下一版本更新。`test_versioned_http_flow.py` 复制 `test4-all` 的 5 个输入到
临时目录，覆盖 no-op、V2 缺失 blob、stale base、本地冲突、历史 get/pull、rollback、active search 和
embedding cache；`test_server.py` 另验证两个同 base session 的 commit race。

可直接在浏览器查看 Scalar 交互接口：<http://127.0.0.1:8000/docs>；机器可读 OpenAPI：
<http://127.0.0.1:8000/openapi.json>。

## 停止与清理

停止 Uvicorn 后，在运行 Docker 的终端按 `Ctrl-C` 即可删除带 `--rm` 的专用数据库容器。
若需删除本次写入的本地对象目录，先停止服务，再确认路径无误后删除仓库内的 `.reindex-data`。

接口参数、响应和错误语义见 [`../reference/http-api.md`](../reference/http-api.md)。
