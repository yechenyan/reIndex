# Architecture

ReIndex 是 Python uv workspace，文件 package 是协议真相，服务器数据库是可重建投影。

```text
packages/cli     `rei`/`reindex`；Collection 身份、输入检查、Docling 解析、增量编译和 package 校验
packages/server  本地 resource 存储、当前态导入、索引和 HTTP API
testbase         Collection 源数据和生成后的 ReIndex packages
wiki             1.0 协议、用户和开发文档
tasks            活跃工作说明和历史记录
```

## CLI 编译流水线

`rei scan` 使用八个稳定阶段：

```text
ResolveContext → PrepareInputs → BuildPlan → ParseItems
→ AssembleNodes → RenderPackage → ValidateAndPublish → CommitState
```

- `.rei/collection.json` 和 `.rei/node-identities.json` 是不可随 cache 删除的稳定身份记录。
- `.rei/cache/` 是按 source、manifest、parser 和 Docling 版本寻址的可删除解析缓存。
- `.rei/build.json` 记录当前输入 hash、Node 机器字段基线和生成 card body 基线。
- package 先写 staging，通过完整校验后才原子替换正式输出。
- Node frontmatter 由 CLI 拥有；Markdown body 是 Agent/curator 内容，后续 scan 按稳定 Node ID 保留。

CLI 是独立 package，不依赖 server。双方通过协议 fixture 和“CLI 生成 → 同步 push”测试保持一致；只有出现
第三个协议消费者或重复实现明显扩大时才考虑抽取共享 core。

## 数据边界

```text
source files + optional reIndex.md (`reindex/input@1.0`)
    │
    ▼
ReIndex 1.0 package
  collection/index.node.md
  node cards + content + assets
    │
    ├──► synchronous push: package ZIP + referenced sources ZIP
    ├──► local content-addressed resources
    └──► PostgreSQL/ParadeDB projections
             ├── Node tree and cards
             ├── BM25 search units
             ├── embeddings
             └── table catalog
```

- Package 使用 [`reindex/node@1.0`](../reference/reindex-v1.0-standard.md)，不接受旧格式。
- 可选 authoring manifest 使用 [`reindex/input@1.0`](../reference/reindex-input-v1.0.md)，只存在于 raw 构建边界。
- Collection 是根 Node；它的 `id` 是 collection ID。
- Collection name 是用户可读的唯一远端名称；改名不改变内部 ID 或 resource logical path。
- source/content/assets 是 package 角色，resource 是服务器存储实体。
- PostgreSQL path、parent、breadcrumb、chunk 和 embedding 都可从 package 重建。
- DuckDB 是受限查询引擎，不是持久化数据库。

## 迁移原则

1. 直接替换 loader、schema、fixture 和 API 契约，不增加旧格式分支。
2. 删除并重建现有数据库和对象存储测试数据。
3. 只接受 Collection 目录中带根 `index.node.md` 的 1.0 archive。
4. 以 `testbase/test1/reIndex/test1/` 作为首个协议 fixture。

服务端 1.0 目标结构见 [`backend-service.md`](backend-service.md)。
