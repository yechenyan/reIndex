# ReIndex 快速开始

本页提供两种用法：在源码仓库中运行完整项目，或让 AI Agent 把自己的数据制作并发布为 ReIndex
Collection。命令行入口统一是 `rei`；用户只需要使用 Collection name，不需要管理 UUID、package 名称或
服务端资源 ID。

## 让 AI Agent 运行源码项目

把下面整段提示词发给 Codex、Claude Code、Cursor 或 Copilot。将 `<REINDEX_REPO>` 替换为本仓库的绝对路径：

```text
请在 <REINDEX_REPO> 中运行并验证 ReIndex 项目。

要求：
1. 先阅读 AGENTS.md，并遵守仓库任务与文档规则。
2. 使用 uv sync 安装 workspace 依赖，然后运行 uv run pytest -q。
3. 在 127.0.0.1:8000 启动并保持本地 reindex-server 在后台运行，数据目录使用仓库内的 tmp/quickstart-server；本次不配置 DATABASE_URL，只验证本地 lexical search，不下载 embedding 模型；全部验证结束后停止服务。
4. 使用 testbase/test2-generage 做完整客户端验证：inspect、scan、check、push、pull、search、get。
5. pull 写到 tmp/quickstart-test2；确认其中除 .rei/remote.json 外，reIndex tree 只包含 .node.md。
6. 使用一个新的空 cache 目录，对 technology-costs-2020.node.md 的 content 连续执行两次 get，确认第一次下载、第二次复用 SHA-256 cache。
7. 如果端口已占用，可以选择其他空闲端口，但所有命令必须使用同一个 API URL。
8. 不部署服务，不改业务代码；如果运行暴露真实问题，先说明原因，再做最小修复并重新执行失败步骤和全量测试。
9. 最后报告服务健康状态、push 的 Node/Source/Resource 数量、pull 文件检查、search 结果数量、两次 get 的 source，以及测试结果。
```

AI Agent 应执行的等价步骤如下，便于人工核对。

## 1. 安装开发依赖

要求 Python 3.12 和 [uv](https://docs.astral.sh/uv/)：

```bash
cd <REINDEX_REPO>
uv sync
uv run pytest -q
```

## 2. 启动本地服务

需要持久化 ParadeDB、默认启用 Qwen embeddings 且禁用 reranker 时，使用
[`本地服务启动指南`](start-local-service.md)。下面的无数据库模式只用于快速验证编译和 HTTP 流程。

在第一个终端运行：

```bash
cd <REINDEX_REPO>
REINDEX_DATA_DIR=tmp/quickstart-server \
  uv run reindex-server run --host 127.0.0.1 --port 8000
```

未配置 `DATABASE_URL` 时，服务使用内存 catalog 和本地 lexical search，适合跑通流程；进程重启后远端
Collection 状态会消失。此模式默认不加载 embedding 或 reranker 模型，不能使用 semantic/hybrid search。

在第二个终端验证服务：

```bash
curl http://127.0.0.1:8000/health
```

## 3. 运行完整 CLI 流程

`testbase/test2-generage` 同时包含真实输入与已生成 package；先重新 scan，以验证编译器并保证 package 与当前输入一致：

```bash
cd <REINDEX_REPO>
export REINDEX_CONFIG_HOME="$PWD/tmp/quickstart-config"
export REINDEX_CACHE_HOME="$PWD/tmp/quickstart-cache"
uv run rei set-api http://127.0.0.1:8000
uv run rei inspect testbase/test2-generage
uv run rei scan testbase/test2-generage
uv run rei check testbase/test2-generage
uv run rei push testbase/test2-generage
uv run rei pull test2 --output tmp/quickstart-test2
uv run rei search "Technology costs" --path tmp/quickstart-test2
uv run rei get technology-costs-2020.node.md \
  --target content \
  --path tmp/quickstart-test2
uv run rei get technology-costs-2020.node.md \
  --target content \
  --path tmp/quickstart-test2
```

预期结果：

- `push` 返回 `ready` 与 `version_id`，只上传服务端缺失 blob；当前 test2 应报告 7 Nodes、2 Sources、16 Resources 和 1176 SearchUnits。
- `pull` 在 `tmp/quickstart-test2/reIndex/test2/` 生成完整 Node tree，其中只有 `.node.md`。
- `search` 返回 Evidence 和可直接交给 `get` 的 `node_path/target`。
- 第一次 `get` 的 `source` 是 `download`；相同资源再次执行时是 `cache`。

首次 `pull --output` 不覆盖非空目录。已有 Node-only checkout 用 `pull --path <dir>` fast-forward；双方变化时
写 `.rei/conflicts.json` 并停止，解决后运行 `pull --path <dir> --continue`。服务端不会自动 merge。

## 输入、输出和身份说明

- 数据目录中的 `reIndex.md` 是可选构建清单；没有它时，`rei` 会递归发现普通文件并使用默认解析策略。
- `.rei/collection.json` 和 `.rei/node-identities.json` 保存稳定身份，不能当作普通 cache 删除。
- `rei scan` 在 `reIndex/<collection-id>--<name>/` 生成完整 package。这个内部目录名无需用户输入。
- `.node.md` 保存 Node 身份、结构、数据卡片及 resource 引用；Markdown、CSV、图片等真实内容按引用独立存放。
- Agent 可以补充 `.node.md` 的 Markdown body，但不应修改 YAML frontmatter；后续 scan 会按稳定 Node UUID 保留已审阅内容。
- `rei pull` 只取得 Node cards；source、content 和 assets 由 `rei get` 精确取得。

需要控制文件选择、解析方式或 `part_of/derived_from` 关系时，参考
[`testbase/test2-generage/reIndex.md`](../../testbase/test2-generage/reIndex.md)和
[`reindex/input@1.0`](../reference/reindex-input-v1.0.md)。

## 让 AI Agent 处理自己的数据

安装发布版 CLI 后，可以把下面提示词中的 `<DATA_DIR>`、`<COLLECTION_NAME>` 和 `<API_URL>` 替换为真实值：

```text
请把 <DATA_DIR> 制作并发布为 ReIndex Collection，名称为 <COLLECTION_NAME>，API 是 <API_URL>。

先运行 uv tool install --upgrade reindex，然后执行 rei init <DATA_DIR> --name <COLLECTION_NAME> --agent <CURRENT_AGENT>，安装或安全更新 ReIndex skills。不要创建或下载教程数据。
接着检查真实文件和 reIndex.md，依次运行 rei inspect、rei scan、rei check。只有 check 返回 valid 后才运行 rei set-api <API_URL> 和 rei push <DATA_DIR>。
push 成功后选择一个与数据相关的代表性问题，运行 rei search "<代表性问题>" --path <DATA_DIR> --mode lexical；再依据搜索结果运行 rei get <node-path> --target content --path <DATA_DIR>，精确取得一个 content 或 source，并验证本地文件或 SHA-256 cache 可复用。
不要让我选择或输入 UUID、package 路径或服务端资源 ID。若 push 报 stale base，先 fetch/pull，所有冲突只在本地解决，不要求服务端 merge。最后汇报 Collection name、version ID、Node/Source/Resource 数量、搜索结果和 get 的来源。
```

`<CURRENT_AGENT>` 可取 `codex`、`claude`、`cursor` 或 `copilot`。`rei init` 是幂等操作，会创建或复用
Collection 身份并安装三个 skills，但不会自动 scan、push 或下载教程数据。

## 常用命令

```bash
rei init <data-dir> --name <name> --agent codex
rei inspect <data-dir>
rei scan <data-dir>
rei check <data-dir>
rei set-api <api-url>
rei push <data-dir>
rei fetch <data-dir>
rei history <data-dir>
rei diff <data-dir> --remote
rei pull <name> --output <directory>
rei pull --path <directory>
rei rollback <name> <version-id> --message "Restore known-good state"
rei search "<query>" --remote <name> --mode lexical
rei get <node-path> --target content
rei get raw://<source-path>
```

生产服务需要 PostgreSQL/ParadeDB、持久化 `REINDEX_DATA_DIR`，以及按需安装的 embedding/reranker 模型；
配置方法见[开发环境](../dev/setup.md)、[后端服务](../dev/backend-service.md)和
[HTTP API](../reference/http-api.md)。
