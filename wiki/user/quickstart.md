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
根部。PDF 同时使用 `tables: "off"` 关闭 Docling 表格输出；两张外部 CSV 通过 `part_of` 和页码保留来源。

此输入协议的完整字段和放置规则见
[`../reference/reindex-input-v1.0.md`](../reference/reindex-input-v1.0.md)。

## 创建和扫描 Collection

```bash
rei create testbase/test2
rei inspect testbase/test2
rei scan testbase/test2
rei check testbase/test2
```

`create` 只建立或复用 `.rei/collection.json` 和稳定身份空间，并用 `created: true|false` 区分两者。`inspect`
是只读预检，输出有效文件、CSV/PDF profile、关系、ignore 和相对上次构建的变化；它不会生成第二份 manifest，
也不会加载 Docling layout/OCR 模型。`scan` 使用 Docling 处理 PDF、使用通用解析器处理 Markdown/CSV，在
staging package 完整通过校验后才发布，并返回 changes、review 分类和完整 warnings。`check` 不重新解析，
只验证当前 package、CLI-owned frontmatter 和输入是否仍然 current，包括上次 scan 后新增的文件。

PDF 有文本层时 Docling OCR 默认关闭；检测不到有效文本时才使用 Docling OCR 重试。第一次 PDF 扫描可能初始化
本地模型，后续相同 source、manifest 和 parser 版本会命中 `.rei/cache/`。

Agent 可以直接补充生成后 `.node.md` 的 Markdown body，但不修改 YAML frontmatter。后续 scan 会比较上一次
生成 body 的 hash：人工修改过的 body 按稳定 Node ID 保留；若 source 同时变化，会报告需要重新审阅。
