# test2 input manifest example

此目录演示 [`reindex/input@1.0`](../../wiki/reference/reindex-input-v1.0.md)，现有原始文件保持不变：

- PDF 是原始 source；
- `00005...csv` 和 `00006...csv` 使用 `part_of`，属于 PDF document group；
- `costs_2020.csv` 没有来源或 parent 声明，是 Collection 根级独立 table；
- `README.md` 显式 ignore，避免示例说明本身被默认扫描成 Node；
- `collection` 被省略，因此 title 默认取目录名 `test2`，description 自动生成；
- `reIndex.md` 是构建控制文件，不作为 Node 或 resource 写入最终 package。

预期输出关系如下；具体短名称和 order 由 `rei` 编译：

```text
reIndex/test2/
├── index.node.md
├── bielefelder-netz-gmbh-netzausbauplan-2022/
│   ├── index.node.md
│   ├── ...text and image Nodes discovered with parse:auto...
│   ├── 000NN--aggregierte-10-jahresplanung.csv
│   ├── 000NN--aggregierte-10-jahresplanung.node.md
│   ├── 000NN--massnahmenplan.csv
│   └── 000NN--massnahmenplan.node.md
├── 000NN--technology-costs-2020.csv
└── 000NN--technology-costs-2020.node.md
```

两张 supplied table 只在 PDF 目录内生成 table Node；通用 text 解析还必须排除这些表格区域，避免单元格文字
重复进入正文。独立原始 CSV 的 source 指向 `raw://costs_2020.csv`，content 是 package 内的规范 CSV；两者
字节相同时由对象存储按 SHA-256 去重。
