# 启动本地 ReIndex 服务

本地服务需要两个常驻组件：ParadeDB 容器和 ReIndex API。CLI 按需运行，不需要常驻。

本指南采用以下默认配置：

- Qwen embeddings 启用，可使用 lexical、semantic 和 hybrid search。
- reranker 禁用，减少模型、内存和启动时间。
- PostgreSQL 数据保存在 Docker named volume。
- source、content、assets、Node cards 和版本 manifest 保存在 `.reindex-data`。

## 首次安装

在 ReIndex 仓库根目录安装服务端和 embedding 依赖：

```bash
uv sync --package reindex-server --extra embeddings
```

创建并启动 ParadeDB：

```bash
docker run -d \
  --name reindex-paradedb \
  -e POSTGRES_PASSWORD=reindex_local \
  -e POSTGRES_DB=reindex_local \
  -p 55434:5432 \
  -v reindex-paradedb-data:/var/lib/postgresql/data \
  paradedb/paradedb:0.24.3-pg18
```

首次创建数据库表：

```bash
DATABASE_URL='postgresql://postgres:reindex_local@127.0.0.1:55434/reindex_local' \
  uv run reindex-server init-db
```

`init-db` 会删除并重建 ReIndex 表。它只在首次初始化或明确允许清空测试数据时运行，日常启动不要执行。

## 日常启动

先启动已有数据库容器：

```bash
docker start reindex-paradedb
```

然后在仓库根目录启动 API：

```bash
DATABASE_URL='postgresql://postgres:reindex_local@127.0.0.1:55434/reindex_local' \
REINDEX_DATA_DIR="$PWD/.reindex-data" \
REINDEX_EMBEDDINGS=qwen \
REINDEX_RERANKER=disabled \
  uv run reindex-server run --host 127.0.0.1 --port 8000
```

首次启动会下载并加载 `Qwen/Qwen3-Embedding-0.6B`。看到 Uvicorn 的
`Application startup complete` 后服务才可用，后续启动会复用本机模型缓存。

## 验证和配置 CLI

另开一个终端检查服务：

```bash
curl http://127.0.0.1:8000/health
```

配置当前源码仓库中的 CLI：

```bash
uv run rei set-api http://127.0.0.1:8000
```

常用命令：

```bash
uv run rei push <data-dir>
uv run rei history <data-dir>
uv run rei pull <collection-name> --output <directory>
uv run rei search "<query>" --path <data-dir> --mode hybrid
```

交互 API 文档位于 <http://127.0.0.1:8000/docs>。

## 停止服务

在 API 终端按 `Ctrl-C`，再停止数据库容器：

```bash
docker stop reindex-paradedb
```

停止容器不会删除 named volume 或 `.reindex-data`。不要删除其中任意一项，否则数据库元数据和 CAS 文件会不完整。

## 常见问题

- `docker start` 提示容器不存在：先执行“首次安装”中的 `docker run`。
- 端口 `55434` 或 `8000` 被占用：更换映射或 API 端口，并同步修改 `DATABASE_URL` 或 `rei set-api`。
- semantic/hybrid 报 embedding profile 不匹配：使用相同的 `REINDEX_EMBEDDINGS=qwen` 重新发布 Collection。
- 只需要 lexical 临时调试：可设置 `REINDEX_EMBEDDINGS=disabled`，但这不是本指南的默认启动方式。
