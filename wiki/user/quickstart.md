# Quick start

ReIndex 1.0 使用 Collection 目录作为输入和 package 根边界。

## 查看首个 fixture

原始 Collection：

```text
testbase/test1/test1/
└── 2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf
```

生成后的 package：

```text
testbase/test1/reIndex/
└── test1/
    ├── index.node.md
    └── bielefelder-netz-gmbh-netzausbauplan-2022/
        ├── index.node.md
        ├── 00001--titel-inhalt-und-einleitung.md
        ├── 00001--titel-inhalt-und-einleitung.node.md
        ├── 00002--110kv-netzkarte-bielefeld.jpg
        ├── 00002--110kv-netzkarte-bielefeld.node.md
        ├── 00005--aggregierte-10-jahresplanung-untere-netzebenen.csv
        ├── 00005--aggregierte-10-jahresplanung-untere-netzebenen.assets001.png
        └── 00005--aggregierte-10-jahresplanung-untere-netzebenen.node.md
```

关键关系：

- `test1/index.node.md` 是 Collection 根 Node。
- 文档目录的 `index.node.md` 是它的第一个 child。
- `.node.md` 是数据卡片，Markdown/CSV/JPG 是 content。
- `.assets001.png` 是附属资产；用途由 card 内 `role` 表达。
- 所有 source、content 和 assets 都带 SHA-256。

## 开发环境

要求 Python 3.12、uv 和 PostgreSQL/ParadeDB。resource 默认保存在项目根的 `.reindex-data`，
可以通过 `REINDEX_DATA_DIR` 指向其他本地持久目录。

```bash
uv sync
uv run pytest
```

当前服务器可直接导入此 fixture；旧 loader、旧 schema 和旧数据不在支持范围内。协议详情见
[`../reference/reindex-v1.0-standard.md`](../reference/reindex-v1.0-standard.md)。

## 查看 reIndex.md 输入示例

`reIndex.md` 整个文件不是必需的：没有它时，`rei` 使用目录名作为 Collection title，递归发现文件并默认
`parse: auto`。创建该文件后只有 `spec` 必填，`collection` 和 `items` 都可省略；`items` 只覆盖特殊文件，
未列出的普通文件仍会被发现。

[`testbase/test2/reIndex.md`](../../testbase/test2/reIndex.md) 展示了可选的 `reindex/input@1.0`：两张 CSV
使用 `part_of` 声明为 PDF document group 的 children，另一张 CSV 没有关系声明，因此保持在 Collection
根部。PDF 同时使用 `tables: supplied` 关闭通用表格提取，避免 supplied CSV 与自动结果重复。

此输入协议的完整字段和放置规则见
[`../reference/reindex-input-v1.0.md`](../reference/reindex-input-v1.0.md)。
