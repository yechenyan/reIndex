---
spec: "reindex/input@1.0"

items:
  "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf":
    parse:
      text: auto
      images: auto
      tables: "off"
    description: "Bielefelder Netz GmbH 2022 年配电网扩建计划及附录。"

  "00005--aggregierte-10-jahresplanung-untere-netzebenen.csv":
    part_of: "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
    pages: [5, 5]
    title: "Aggregierte 10-Jahresplanung der unteren Netzebenen"
    description: "按电压层级和投资类型整理的十年投资计划。"


  "00006--massnahmenplan-aller-spannungsebenen.csv":
    part_of: "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
    pages: [5, 5]
    title: "Maßnahmenplan aller Spannungsebenen für zehn Jahre"
    description: "52 项电网措施及项目、时间、成本和状态信息。"

  "costs_2020.csv":
    title: "Technology costs 2020"
    description: "独立于 PDF 的技术成本数据，作为 Collection 根级 table Node。"

---

## 处理说明

这里省略了 `collection`，所以 Collection title 默认使用目录名 `test2`，description 由 `rei` 自动生成。

两张德文 CSV 是 PDF 第 5 页表格的权威提取结果，应放进 PDF 对应的 document group。PDF 的通用正文和
图片解析保持开启，通用表格解析关闭，避免再次生成重复或错误的表格。

`costs_2020.csv` 没有 `part_of` 或 `derived_from`，因此保持为 Collection 根级的独立数据表。

## 补充说明

此目录演示 [`reindex/input@1.0`](../../wiki/reference/reindex-input-v1.0.md)，现有原始文件保持不变：

- PDF 是原始 source；
- `00005...csv` 和 `00006...csv` 使用 `part_of`，属于 PDF document group；
- `costs_2020.csv` 没有来源或 parent 声明，是 Collection 根级独立 table；
- 原 README 说明已合并到本 `reIndex.md`，因此没有额外 README 输入；
- `collection` 被省略，因此 title 默认取目录名 `test2`，description 自动生成；
- `reIndex.md` 是构建控制文件，不作为 Node 或 resource 写入最终 package。

预期输出关系如下；具体短名称和 order 由 `rei` 编译：

```text
reIndex/<collection-id>--test2/
├── index.node.md
├── bielefelder-netz-gmbh-netzausbauplan-2022/
│   ├── index.node.md
│   ├── 00001--document-text.md
│   ├── 00001--document-text.node.md
│   ├── ...significant image Nodes discovered with parse:auto...
│   ├── 000NN--aggregierte-10-jahresplanung.csv
│   ├── 000NN--aggregierte-10-jahresplanung.node.md
│   ├── 000NN--massnahmenplan.csv
│   └── 000NN--massnahmenplan.node.md
├── technology-costs-2020.csv
└── technology-costs-2020.node.md
```

两张外部 table 只在 PDF 目录内生成 table Node；PDF 使用 `tables: "off"`，通用 text 解析还应尽量排除这些
表格页的单元格文字。独立原始 CSV 的 source 指向 `raw://costs_2020.csv`，content 是 package 内的规范 CSV；两者
字节相同时由对象存储按 SHA-256 去重。Collection 根级独立普通 Node 不在文件名中编码 `order`；PDF
document group 内有阅读顺序的 children 继续使用五位顺序号。

Docling 标题不会机械地一一生成 Node。相邻章节按正文规模合并，内部保留 Markdown 标题；本例第 1–4 页正文
合并为一个 `Document text` Node，地图和两张可查询表格继续保持独立 Node。

本目录已经由 `rei create` 建立稳定 Collection 身份，并由 `rei scan testbase/test2` 生成实际 package。
`.rei/cache/` 可删除；`.rei/collection.json` 和 `.rei/identities.json` 不可作为普通解析缓存清理。
