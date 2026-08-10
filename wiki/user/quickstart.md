# ReIndex 快速开始

本页提供两种用法：在源码仓库中运行完整项目，或让 AI Agent 把自己的数据制作并发布为 ReIndex
Collection。命令行入口统一是 `rei`；用户只需要使用 Collection name，不需要管理 UUID、package 名称或
服务端资源 ID。

## 让 AI Agent 运行源码项目

把下面整段提示词发给 Codex、Claude Code、Cursor 或 Copilot。将 `<REINDEX_REPO>` 替换为本仓库的绝对路径：

```text
Führe das ReIndex-Projekt in <REINDEX_REPO> aus und validiere es.

Anforderungen:
1. Lies zuerst AGENTS.md und beachte die Aufgaben- und Dokumentationsregeln des Repositorys.
2. Installiere die Workspace-Abhängigkeiten mit uv sync und führe anschließend uv run pytest -q aus.
3. Starte und halte den lokalen reindex-server unter 127.0.0.1:8000 im Hintergrund. Verwende tmp/quickstart-server im Repository als Datenverzeichnis; konfiguriere diesmal keine DATABASE_URL, prüfe nur die lokale lexikalische Suche, lade kein Embedding-Modell herunter und stoppe den Dienst nach allen Prüfungen.
4. Führe mit testbase/test2-generage die vollständige Client-Validierung aus: inspect, scan, check, push, pull, search und get.
5. Schreibe pull nach tmp/quickstart-test2 und bestätige, dass der reIndex-Baum außer .rei/remote.json nur .node.md enthält.
6. Führe get für den content von technology-costs-2020.node.md mit einem neuen leeren Cache-Verzeichnis zweimal aus; bestätige beim ersten Lauf download und beim zweiten die Wiederverwendung des SHA-256-Cache.
7. Wenn der Port belegt ist, wähle einen freien Port, aber verwende für alle Befehle dieselbe API-URL.
8. Stelle keinen Dienst bereit und ändere keinen Produktcode. Falls ein echter Fehler auftritt, erkläre zuerst die Ursache, nimm dann die kleinste Korrektur vor und wiederhole den fehlgeschlagenen Schritt sowie alle Tests.
9. Berichte abschließend Dienststatus, Node/Source/Resource-Anzahlen des push, die pull-Dateiprüfung, die Anzahl der search-Ergebnisse, die Quellen beider get-Aufrufe und die Testergebnisse.
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
Erstelle und veröffentliche aus <DATA_DIR> eine ReIndex-Collection namens <COLLECTION_NAME>; die API lautet <API_URL>.

Führe zuerst uv tool install --upgrade reindex aus und danach rei init <DATA_DIR> --name <COLLECTION_NAME> --agent <CURRENT_AGENT>, um die ReIndex-Skills zu installieren oder sicher zu aktualisieren. Erstelle oder lade keine Tutorialdaten herunter.
Prüfe dann die echten Dateien und reIndex.md und führe nacheinander rei inspect, rei scan und rei check aus. Erst wenn check valid zurückgibt, führe rei set-api <API_URL> und rei push <DATA_DIR> aus.
Wähle nach einem erfolgreichen push eine repräsentative datenbezogene Frage und führe rei search "<repräsentative Frage>" --path <DATA_DIR> --mode lexical aus. Verwende danach das Suchergebnis für rei get <node-path> --target content --path <DATA_DIR>, um genau einen content oder source abzurufen, und bestätige die Wiederverwendung einer lokalen Datei oder des SHA-256-Cache.
Bitte lass mich weder UUIDs noch Package-Pfade oder serverseitige Ressourcen-IDs auswählen oder eingeben. Bei stale base zuerst fetch/pull ausführen; alle Konflikte nur lokal lösen und keinen Server-Merge verlangen. Abschließend Collection-Name, Versions-ID, Node/Source/Resource-Anzahlen, Suchergebnisse und die Quelle von get berichten.
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
