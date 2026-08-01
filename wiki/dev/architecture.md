# Architecture

ReIndex 是 Python uv workspace，文件 package 是协议真相，服务器数据库是可重建投影。

```text
packages/cli     `rei`/`reindex` 命令入口；当前实现 `doctor`，编译工作流仍在任务设计阶段
packages/server  本地 resource 存储、当前态导入、索引和 HTTP API
testbase         Collection 源数据和生成后的 ReIndex packages
wiki             1.0 协议、用户和开发文档
tasks            活跃工作说明和历史记录
```

## 数据边界

```text
source files
    │
    ▼
ReIndex 1.0 package
  collection/index.node.md
  node cards + content + assets
    │
    ├──► local content-addressed resources
    └──► PostgreSQL/ParadeDB projections
             ├── Node tree and cards
             ├── BM25 search units
             ├── embeddings
             └── table catalog
```

- Package 使用 [`reindex/node@1.0`](../reference/reindex-v1.0-standard.md)，不接受旧格式。
- Collection 是根 Node；它的 `id` 是 collection ID。
- source/content/assets 是 package 角色，resource 是服务器存储实体。
- PostgreSQL path、parent、breadcrumb、chunk 和 embedding 都可从 package 重建。
- DuckDB 是受限查询引擎，不是持久化数据库。

## 迁移原则

1. 直接替换 loader、schema、fixture 和 API 契约，不增加旧格式分支。
2. 删除并重建现有数据库和对象存储测试数据。
3. 只接受 Collection 目录中带根 `index.node.md` 的 1.0 archive。
4. 以 `testbase/test1/reIndex/test1/` 作为首个协议 fixture。

服务端 1.0 目标结构见 [`backend-service.md`](backend-service.md)。
