# ReIndex Input 1.0

`reIndex.md` 是 raw Collection 的可选构建清单。没有该文件时，`rei` 按本标准的默认规则递归发现并解析目录；
有该文件时，它只补充或覆盖特殊 item 的来源关系、最终树位置和解析策略。用户不需要把普通文件逐一写入清单。

状态：`reindex/input@1.0` 当前输入协议。它是 authoring input，不是最终 package 文件，也不上传到服务器。

## 1. 文件与语法

如果需要声明特殊规则，`reIndex.md` 位于待扫描 Collection 根目录，使用 UTF-8、LF 和 YAML frontmatter：

```md
---
spec: "reindex/input@1.0"
collection:
  title: "Example"
---

这里可以写给人和 Agent 阅读的补充说明。
```

frontmatter 禁止重复 key、anchor、alias、自定义 tag 和多文档。Markdown body 可省略，只供人和 Agent 阅读，
不参与编译或缓存；所有机器关系必须写在 frontmatter 中。

## 2. 顶层字段

| 字段 | 规则 |
| --- | --- |
| `spec` | `reIndex.md` 存在时必需，固定为 `reindex/input@1.0` |
| `collection` | 可选；其中非空 `title` 和 `description` 也分别可选，缺失字段使用默认值 |
| `items` | 可选，以输入相对路径为 key、item 配置对象为 value 的 mapping；只需列出要覆盖默认行为的 item |

因此下面是完整且有效的最小声明文件，其行为与不创建 `reIndex.md` 相同：

```md
---
spec: "reindex/input@1.0"
---
```

item key 同时表示本地文件或目录，不再重复填写 `path`。它必须是已存在的 canonical POSIX 相对路径：禁止绝对
路径、反斜杠、`.`/`..`/空 segment，以及任意位置的保留目录 `reIndex`、`.rei`、`.git`、`__pycache__`。
路径按 Unicode NFC 规范化；两个路径规范化后冲突必须报错。扫描只接受 regular file/directory，不跟随 symlink。

实现必须拒绝未知顶层字段、未知 item 字段、错误类型和无效字段组合，不能静默忽略拼写错误。item value 必须是
mapping，空覆盖应写成 `{}`。未出现在 `items` 中的普通路径仍按默认规则处理；`items` 在 1.0 中不是 allowlist。

## 3. 无声明时的默认规则

没有 `reIndex.md`，或者声明中省略 `collection`/`items` 时，`rei` 必须使用以下确定性默认值：

1. Collection `title` 使用输入根目录的 basename；description 固定为 `Collection imported from "<title>".`。
2. 递归发现普通文件和目录；文件使用 `parse: auto`，类型由文件格式和内容确定。未知但安全的格式生成 `file`
   Node 和 warning；损坏、加密或不安全的输入进入 review 或使构建失败。只有 `ignore: true` 才完全排除 item。
3. 输入子目录编译为 group，其内容成为 children；输入根目录中的文件成为 Collection 根级 children。
4. YAML mapping 顺序没有语义。目录 children 按 NFC canonical path 的 UTF-8 bytes 排序；文档 children 依次按
   recipe order、locator、kind 和 canonical item path 排序，仍无法唯一排序时报错。
5. 普通本地文件的 `source` 指向自身 `raw://` URI。table content 必须复制到 package 的规范 CSV 位置；原始
   CSV 和 package CSV 字节相同时由内容寻址存储按 SHA-256 去重，但仍是两个逻辑 resource。
6. 排除控制文件 `reIndex.md`，以及 `reIndex/`、`.rei/`、`.git/`、`__pycache__/` 和未显式列入 `items` 的隐藏路径。
   显式隐藏文件只纳入该文件；显式隐藏目录纳入其普通 descendants，保留目录始终不能重新纳入。
7. 两个不同路径即使 SHA-256 相同，也仍是两个逻辑 item；hash 只负责内容变化检测和底层字节去重。

默认发现负责普通输入；`items` 只负责例外，例如把外部提取的 CSV 放进 PDF group、记录原始 URL、关闭某类
自动解析或忽略临时文件。

## 4. Item 字段

| 字段 | 默认 | 含义 |
| --- | --- | --- |
| `parse` | `auto` | 通用解析策略；可以是 `auto`，或按 `text/images/tables` 配置 |
| `origin_url` | 无 | 输入的原始 HTTP(S) 来源，仅作 provenance，不表示每次构建都联网下载 |
| `part_of` | 无 | 当前 item 来源于目标文件，并在最终树中成为目标 document group 的 child |
| `derived_from` | 无 | 当前 item 来源于目标文件，但在最终树中保持 Collection 根级 item |
| `pages` | 无 | 两个正整数 `[start, end]`，成为 `source.locator.pages` |
| `title` | 自动 | 覆盖自动生成的 Node title |
| `description` | 自动 | 覆盖自动生成的简述 |
| `quality` | 无 | 对 CSV 等显式产物执行的确定性质量要求 |
| `ignore` | `false` | 为 `true` 时完全排除该 item |

目录 item 只允许 `title`、`description` 和 `ignore`；目录 `ignore: true` 递归生效且不能由 descendant 覆盖。
文件 item 可以使用全部字段。`ignore: true` 不能与其他 item 字段组合。

`part_of` 与 `derived_from` 互斥。`pages` 只能与两者之一同时出现，并使用目标文件从 1 开始的闭区间页码；必须
满足 `start <= end <= page_count`，且目标格式必须支持分页。关系禁止 self-reference 和 cycle，每个 item 只能有
一个 canonical parent。被引用的目标可以省略于 `items`，但必须能由默认扫描发现、不能被 ignore，并且必须是
文件；拥有 `part_of` children 的目标必须编译为 group，即使它原本可作为单个 text Node。

## 5. 放置与来源

```yaml
items:
  "report.pdf": {}

  "table-inside.csv":
    part_of: "report.pdf"
    pages: [5, 5]

  "table-at-root.csv":
    derived_from: "report.pdf"
    pages: [5, 5]
```

关系必须确定地展开为：

| 声明 | source | 最终 parent |
| --- | --- | --- |
| `part_of: report.pdf` | `raw://report.pdf` | `report.pdf` 对应的 document group |
| `derived_from: report.pdf` | `raw://report.pdf` | Collection root |
| 两者都没有 | 本地文件为 `raw://<item>`；目录 group 无 source | 输入目录层级确定的默认 parent |

输入 CSV 只在最终 package 的规范位置出现一次。`part_of` 不把 CSV 字节写回 PDF，也不在 Collection 根部再建
一个副本；它表达的是 ReIndex Node tree 中的文档组成关系。

## 6. 通用解析策略

`parse: auto` 是默认值，等价于三类全部为 `auto`。需要按内容类型控制时使用 mapping；省略的类别仍为 `auto`：

```yaml
parse:
  text: auto
  images: auto
  tables: "off"
```

每项只允许：

| 值 | 含义 |
| --- | --- |
| `auto` | 使用 `rei` 通用能力发现并生成该类内容 |
| `off` | 不生成该类内容 |

只允许类别 `text/images/tables` 和值 `auto/off`。外部解析结果不需要第三种 parse 值：使用
`part_of`/`derived_from` 表达来源和放置，使用 `pages` 表达 provenance，并使用 `quality` 校验产物自身。
例如 Docling 漏表时，可以设置 `tables: "off"` 并把权威 CSV 声明为 `part_of`；这不要求通用解析器先检测到
对应表格，也不虚假保证几何区域可以严格匹配。

通用解析器应尽量从正文中排除已识别的表格区域；无法识别时，Agent 必须审阅是否仍有线性化单元格文本。
解析器不得机械地把每个识别标题都变成独立 Node；相邻短章节应按合理正文规模合并，并在 content 内保留标题。
如果保留 `tables: auto` 并同时声明外部 CSV，系统会保留两类候选，不能在没有 bbox 或其他明确标识时声称已经
自动去重。构建状态必须记录关系 target 的 source hash；target 改变后，相关外部产物进入 review。

## 7. 质量要求

表格 item 可以声明：

```yaml
quality:
  expected_rows: 52
  expected_columns:
    - "id"
    - "description"
  primary_key: ["id"]
```

- `expected_rows` 是不含 header 的精确非负整数。
- `expected_columns` 必须与 CSV header 名称和顺序完全一致。
- `primary_key` 中的列必须存在，组合值必须非空且唯一。

任何 `quality` 失败都是构建错误，不得只记录 warning 或退回通用解析。

无论是否声明 `quality`，最终 package 仍必须通过 ReIndex 1.0 的 CSV、资源、树、URI 和 hash 校验。结构校验不能
证明 PDF 表格语义正确；特殊提取程序仍应保留视觉参考和业务断言。

## 8. 身份与增量

identity 与 cache 必须分离。Collection 和 logical item UUID 保存于可迁移的持久 identity record；该记录不是
可随时删除的提取缓存。identity record 丢失时视为新 Collection，不得从路径、title、order 或内容 hash 猜旧 UUID。

item key 和关系 target 只是当前位置 locator。内容更新、title/description 覆盖、parent/order 变化或暂时 ignore
都不得改变已有 UUID；目录或文档从单 Node 展开为 group 时，原 anchor UUID 保留给 group。rename 只有在已有
身份映射、显式 move，或旧/新文件 hash 唯一一对一匹配时才自动继承；歧义必须要求确认。新增 sibling 可以改变
连续 order、文件名和 node hash，但不能改变其他 Node UUID。

## 9. 完整示例

```md
---
spec: "reindex/input@1.0"
collection:
  title: "Network planning"
items:
  "network-plan.pdf":
    parse:
      text: auto
      images: auto
      tables: "off"

  "aggregate-plan.csv":
    part_of: "network-plan.pdf"
    pages: [5, 5]
    description: "Aggregate investment plan."
    quality:
      expected_rows: 24

  "collection-summary.csv":
    derived_from: "network-plan.pdf"
    pages: [5, 5]

  "scratch.csv":
    ignore: true
---

## Notes

The external CSV files were reviewed against the PDF tables.
```

仓库中的完整输入示例见 [`testbase/test2-generage/reIndex.md`](../../testbase/test2-generage/reIndex.md)。

## 与 package 的边界

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
