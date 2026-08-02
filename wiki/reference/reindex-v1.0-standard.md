# ReIndex 1.0

ReIndex 把本地原始文件编译成程序可解析、Agent 可阅读、可搜索、可查询和可追溯的知识包。

状态：当前 package 协议。1.0 是破坏性协议，不接受旧格式。

## 1. 数据模型

```text
raw files → source/content/assets → Node cards → PostgreSQL/local resource storage → Agent tools
```

- **Collection**：隔离、上传、授权和搜索的最小范围；Collection 本身也是根 Node。
- **Node**：具有稳定 `id`、类型、标题、顺序和数据卡片的逻辑对象。
- **source**：Node 所依据的原始文件，例如 PDF 或原始 CSV。
- **content**：Node 的主要可读、可搜索或可查询内容，例如 Markdown、CSV 或图片。
- **assets**：content 之外的附属文件；文件名只编号，用途由卡片内 `role` 表达。
- **resource**：文件上传后的服务器存储对象，不是 package 字段。

同一份字节可以同时承担不同角色。table Node 的 `source` 可以指向原始 CSV，但 `content` 必须是 package 内的
规范 CSV；两者 SHA-256 相同时仍是两个逻辑 resource，底层对象字节只保存一次。

## 2. Collection 与目录

原始数据按 Collection 分组：

```text
data/
└── my-collection/
    ├── report.pdf
    └── customers.csv
```

生成包必须先出现 Collection 名称，再出现内容：

```text
reIndex/
└── my-collection/
    ├── index.node.md
    ├── report/
    │   ├── index.node.md
    │   ├── 00001--overview.md
    │   ├── 00001--overview.node.md
    │   ├── 00002--network-map.png
    │   ├── 00002--network-map.node.md
    │   ├── 00003--project-budget.csv
    │   ├── 00003--project-budget.assets001.png
    │   └── 00003--project-budget.node.md
    └── customers.node.md
```

目录规则：

1. `reIndex/<collection>/index.node.md` 是 Collection 根 Node。
2. 每个真实或虚拟容器目录恰好有一个 `index.node.md`。
3. 最近祖先目录的 `index.node.md` 是父 Node。
4. Collection 根 Node 没有 `order`；其他 Node 必须有正整数 `order`。
5. 同一父 Node 下的 `order` 必须唯一、连续并从 1 开始。
6. 大 PDF 是 group Node，完整内容由有序 children 覆盖，不生成聚合全文。
7. 路径表示当前位置，稳定 `id` 表示跨重命名和重复构建的逻辑身份。

## 3. 文件命名

Collection 根级的独立普通 Node 使用不带顺序号的短名称：

```text
<短名称>.<扩展名>
<短名称>.node.md
```

document group 或其他非根 group 内的有序普通 child 使用以下格式：

```text
<五位顺序号>--<短名称>.<扩展名>
<五位顺序号>--<短名称>.node.md
```

例如：

```text
00001--project-overview.md
00001--project-overview.node.md
00002--network-map.png
00002--network-map.node.md
```

附属文件使用主 stem 和三位资产编号：

```text
00003--project-budget.assets001.png
00003--project-budget.assets002.pdf
```

命名规则：

- Collection 根级普通 Node 文件不得使用五位 `order` 前缀；其展示顺序只读 Node metadata。
- 非根 group 内普通 Node 文件的五位顺序号必须与 Node 的 `order` 一致。
- group 目录使用可读短名称，不加顺序号；顺序只由其 `index.node.md` 的 `order` 表达。
- 同一普通 Node 的 card、content 和 assets 使用相同主 stem。
- 短名称由 title 生成，使用小写字母、数字和连字符；建议不超过 60 个字符。
- assets 从 `001` 连续编号；用途不得编码到文件名中。
- 程序必须使用显式 URI 建立关系，不能依靠同名文件猜测。
- title 是展示和搜索的权威值；文件短名称只用于人工浏览。

## 4. Node card

每个 Node 有一个 `*.node.md`：

```text
.node.md
├── YAML frontmatter   身份、结构、溯源和机器可读卡片
└── Markdown card      面向 Agent 的概览、关键事实、预览和使用提示
```

完整正文或主数据不得放进 `.node.md`；它们由 `content` 显式引用。

通用字段：

| 字段 | 规则 |
| --- | --- |
| `spec` | 必需，固定为 `reindex/node@1.0` |
| `id` | 必需，稳定 UUID，不得使用路径或内容 hash |
| `kind` | 必需：`group/text/table/image/file` |
| `order` | 除 Collection 根 Node 外必需，父 Node 内从 1 连续排序 |
| `title` | 必需，自然、完整且不带文件编号 |
| `description` | 必需，简短说明内容及可回答的问题 |
| `source` | 有原始来源时必需；纯逻辑 group 可省略 |
| `content` | 非 group Node 必需；group Node 禁止 |
| `assets` | 可选，按数组顺序与 `assetsNNN` 一一对应 |
| `warnings` | 可选，只记录确实影响使用或保真度的问题 |
| `table` | `kind: table` 必需 |

YAML 使用 UTF-8、LF 和 YAML 1.2 的 JSON 兼容数据模型。禁止 anchor、alias、merge key、
自定义 tag、多文档和重复 key。程序不得从 Markdown 标题或文件名推断身份、类型、来源或关系。

Markdown card 应提供新增价值：

- group：覆盖范围和 child 概览；
- text：关键事实、数字和结论；
- table：数据范围和最多 5 行真实 Preview；
- image：视觉描述、来源伴随文字和 OCR；
- file：用途、格式和读取提示。

card 不应重复 URI、SHA-256、完整 content 或可由 frontmatter 直接读取的字段。

## 5. source、content 与 assets

文本 Node 示例：

```md
---
spec: "reindex/node@1.0"
id: "019f9c2a-0000-7000-8000-000000000001"
kind: "text"
order: 1
title: "第一部分：项目概况"
description: "说明项目背景、建设目标和实施范围。"
source:
  uri: "raw://report.pdf"
  sha256: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  locator:
    pages: [1, 12]
content:
  uri: "./00001--project-overview.md"
  media_type: "text/markdown"
  sha256: "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
---
## 关键事实

- 项目覆盖三个建设阶段。
- 计划总投资为 1.2 亿元。
```

`source.uri` 必须是 Collection 内的 `raw://` 相对路径。`content.uri` 可以是同目录 `./`
相对路径；非 table Node 在 source 与 content 完全相同时也可以使用同一个 `raw://` URI。table content
必须使用 package 内的 `./` CSV，确保导入时可以完成结构校验和只读查询。

每个 source/content 必须包含 `uri` 和 `sha256`；content 还必须包含 `media_type`。
`source.locator` 可保存页码或其他原始定位信息，定位范围必须覆盖 card 和 content 引用的证据。

assets 示例：

```yaml
assets:
  - uri: "./00003--project-budget.assets001.png"
    media_type: "image/png"
    sha256: "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    role: "visual_reference"
    description: "原始表格布局的高清截图。"
```

assets 规则：

- 每项必须有 `uri/media_type/sha256/role/description`。
- `role` 是简短的 snake_case 机器标签，不写入文件名。
- description 说明资产内容和用途，不能只重复 role。
- asset 不是独立 Node，不参与父子树；若内容需要单独搜索、引用或授权，应建独立 Node。

## 6. Node 类型

| kind | content | card |
| --- | --- | --- |
| `group` | 无 | Collection、目录或大文档概览 |
| `text` | Markdown/TXT 等完整正文 | 摘要、关键事实和限制 |
| `table` | UTF-8 CSV | grain、schema、Preview 和规范化警告 |
| `image` | 原图或提取图片 | 视觉描述、伴随文字、OCR 和识别限制 |
| `file` | 其他主文件 | 用途、格式和读取提示 |

小 PDF 可以生成一个 text Node；大 PDF 生成一个 group 和语义 children。图片、表格与文本按
内容语义建 Node，而不是按固定页数切分。children 可引用重叠页码，但不得重复保存同一正文。

## 7. 表格

表格的完整权威数据是 `content` 指向的 CSV。表格 card 必须让 Agent 不读取全部 CSV 也能理解数据。

`table` 字段规则：

- `row_count` 是不含 header 的精确行数。
- `grain` 说明一行代表什么。
- `columns` 覆盖 CSV 全部列，名称和顺序与 header 一致。
- 每列有 `name/type/description`，`unit` 按需添加。
- 类型限于 `string/integer/decimal/boolean/date/datetime`。
- 代码、前导零、占位符或混合格式使用 `string`。
- `primary_key/foreign_keys` 只有权威依据存在时才填写。
- Preview 最多 5 行，单元格必须逐字来自 CSV；可以选择代表性列，但必须使用原列名。
- PDF 表格截图使用 `.assetsNNN`，在 assets 中声明 role 和 description，不在 card 重复 URI/hash。

原始 CSV 本身就是主数据时，source 指向 `raw://` 原文件，content 是 package 内的规范 CSV。两者 hash
相同时由内容寻址对象存储去重，不代表两个逻辑 URI 或 resource 合并。

## 8. 校验与版本

Validator 至少检查：

1. frontmatter 语法和 JSON Schema。
2. Collection 根 Node 和每个 group 的 `index.node.md`。
3. Node ID 在 package 内唯一。
4. parent/order 连续；根级普通 Node 不带顺序前缀，非根 group 内普通 Node 的五位前缀及 assets 三位编号与 metadata 一致。
5. source/content/assets URI 安全、存在且 SHA-256 匹配。
6. source locator 在原始文件范围内并覆盖证据来源。
7. content media type 与文件内容一致。
8. CSV header 非空且唯一；row_count 和 columns 与 CSV 一致。
9. Preview 行和单元格真实存在于 CSV。
10. 主键、外键引用的 Node 和列存在。
11. package 中没有未声明的 content/assets 或重复聚合正文。

package 本身不包含 revision 字段。服务器可把完整 package/raw manifest 保存为轻量历史版本，并只将 active
version 投影到搜索表；`version_id`、base 和提交消息属于传输/服务端协议，不写入 `.node.md`。Node hash 为：

```text
node_hash = SHA-256(normalized frontmatter + markdown card + content sha256 + ordered asset sha256s)
```

任何 frontmatter、card、content 或 asset 变化都会产生新的 `node_hash`；稳定 `id` 不变。

## 9. 服务器存储与搜索

- 本地内容寻址存储保存 source、content、assets 和原始 `.node.md` 字节。
- PostgreSQL/ParadeDB 保存 Collection 当前态、Node 树、解析后的 card、resource 关系、
  BM25 单元和 embeddings；表格定义保存在解析后的 Node attributes。
- 本地对象字节按 SHA-256 去重；不同 namespace/path 的逻辑 resource 可以指向同一个 object key。
- DuckDB 只作为 CSV/Parquet 的受限只读查询引擎，不是协议存储。
- 搜索高权重索引 title，中高权重索引 description/card，正常权重索引 content。
- 搜索 Evidence 必须标明命中来自 card、content 还是 table row；正文行号指向 content 文件。
- assets 默认不独立建立搜索单元；其描述进入所属 Node card 索引。

数据库派生字段包括 `path/parent_id/depth/breadcrumb/node_hash/chunks/embeddings/resource_id`
和索引日志，不写回 package。

## 10. 明确禁止

- 把完整正文继续放在 `.node.md` body。
- 在 package 中使用旧 `resource` 字段表示主文件。
- 从同名 stem 隐式推断 content/assets 关系。
- 在 asset 文件名中编码 visual、preview、thumbnail 等用途。
- 用 title、path 或内容 hash 代替稳定 Node ID。
- 在多个 Node 中复制同一段聚合全文。
- 把服务器 object key、resource ID、package hash、chunk 或 embedding 写入 package。

## 11. Raw authoring input

ReIndex 1.0 的 raw authoring 语法以 [`reindex-input-v1.0.md`](reindex-input-v1.0.md) 为规范性来源。
`reIndex.md` 整个文件可省略：此时 `rei` 以输入目录名作为 Collection title，递归发现普通文件和目录，并使用
默认 `parse: auto`。只有需要覆盖默认行为时，才创建该文件。

声明文件存在时只有 `spec: reindex/input@1.0` 必填；`collection` 和 `items` 均可省略。`items` 是稀疏覆盖，
不是 allowlist，未列出的普通路径仍按默认规则处理。item key 是当前相对路径 locator，不是稳定身份或 `path`
字段；机器关系全部位于 YAML frontmatter，Markdown body 不参与编译。

`part_of` 同时表达 provenance 和 parent：derived item 的 `source` 指向目标 raw 文件，并成为该文档 group 的
child。`derived_from` 只表达 provenance，item 保持为 Collection 根级 Node。最终 package 中每个逻辑 item
只能有一个规范位置，不得同时在文档目录和 Collection 根部复制。`parse` 可以按 `text/images/tables` 选择
`auto/off`。外部解析结果使用关系、页码和 quality 表达，不要求通用解析器先检测到对应内容；quality 失败必须
终止，不能静默回退通用结果。

最小合法文件只有版本标记：

```md
---
spec: "reindex/input@1.0"
---
```

`reIndex.md` 是构建输入，不是 `reindex/node@1.0` package 成员，服务器 loader 仍然只接受最终 package。
