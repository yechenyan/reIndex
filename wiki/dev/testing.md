# 本地测试指南

本项目有两层测试：默认测试验证 importer、协议校验和服务逻辑；HTTP E2E 测试连接已经启动的真实
ParadeDB 与 Uvicorn 服务，验证实际网络 API。E2E fixture 固定使用
`testbase/test1/reIndex/test1`，并上传 `testbase/test1/test1` 内的 PDF。

## 常规检查

在仓库根目录执行：

```bash
uv sync
uv run pytest -q
uvx ruff format --check packages tests
uvx ruff check packages tests
```

默认测试不要求 Docker。真实 ParadeDB 集成测试和 HTTP E2E 测试会在没有对应环境变量时跳过。

## CLI 与 raw → ReIndex fixture

CLI 的临时目录测试覆盖 Collection 创建和定位、只读 inspect/check、部分目录增量扫描、重命名后的
Node 身份复用、机器字段保护，以及 Agent 修改过的 card body 在后续 scan 中保留。

`testbase/test2` 是 Docling-only 的真实 PDF/CSV fixture。提交前依次运行：

```bash
uv run rei inspect testbase/test2
uv run rei scan testbase/test2
uv run rei check testbase/test2
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

E2E 等待导入的默认超时为 180 秒。首次在 CPU 上生成 embedding 较慢时，可用
`REINDEX_E2E_IMPORT_TIMEOUT=600` 延长。

该测试会创建（或复用）fixture 的 Collection，上传 raw PDF，导入 ZIP，然后断言：8 个 Node、直接
children 与递归子树顺序、card/source/content/asset 原始字节下载、ParadeDB lexical search，以及 DuckDB
`SELECT count(*)` 得到 24 行。每次都重新导入 fixture，因此可重复执行；它不会故意提交损坏 archive。

可直接在浏览器查看交互接口：<http://127.0.0.1:8000/docs>；机器可读 OpenAPI：
<http://127.0.0.1:8000/openapi.json>。

## 停止与清理

停止 Uvicorn 后，在运行 Docker 的终端按 `Ctrl-C` 即可删除带 `--rm` 的专用数据库容器。
若需删除本次写入的本地对象目录，先停止服务，再确认路径无误后删除仓库内的 `.reindex-data`。

接口参数、响应和错误语义见 [`../reference/http-api.md`](../reference/http-api.md)。
