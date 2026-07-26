# ReIndex 产品概览
ReIndex local files into agent-ready knowledge.

这是我想做的一个工具， 也可以说是一个套标准。

## 他是怎么运行的?

### STEP1 
假设你的有一个叫 data 的文件夹，里面文件如下

data
- someLargeA.pdf 
- reIndex.md      介绍这个文件夹里内容的 md
- someB.csv
  - folderC
    - somSmallA.pdf
    - reIndex.md  介绍这个文件夹里内容的 md
    - someC.png

### STEP2
用一些工具把上面的文件进行处理，
处理的过程不用管，后面写代码处理。

reIndex/
├── index.node.md
├── someLargeA/
│   ├── index.node.md
│   ├── 0001.node.md
│   ├── 0002.node.md
│   ├── 0003.node.md
│   ├── 0003.csv
│   ├── 0004.node.md
│   └── 0004.png
├── someB.node.md
└── folderC/
    ├── index.node.md
    ├── someSmallA.node.md
    └── someC.node.md

把文件夹，文件称作 node
文件夹或者大pdf 拆成的虚拟文件夹的 node 有 child
最顶级的 node 可以称为 collect，方便流程

.node.md 里分为一些内容，相当于 dataCard，有如下功能
- hashId 等唯一索引，版本控制，
- 文件从哪来的，溯源信息
- 由代码运行生成的结构化数据
- 由 AI 生成的数据，包括介绍和这个由什么用， 表格字段由哪些，行数
- 对于 表格由表格预览，对于 PDF 有 PDF 生成的文本，对于图片有文字描述

每个 card 都根据文件类型设置不同的标准类型

最后形成

raw -> node 的一个标准化的体系


### STEP3 
上传到数据库，数据库用 PostgreSQL
raw 也就是说原始数据上传到文件存储

node + card 这里的对应关系，上传到关系数据库

row + card 建立全文索引
row + card 建立向量索引


### STEP4
查询，给AI 提供如下查询供具

- search:
最常用的搜索， 根据全文搜索和向量搜索的结果排序繁华

- broswer:
可以搜索node 树结构，

- get:
直接下载原始文件，如果选择的有child，把子内容一口气全部下载

- query：
利用 duckDB 在数据库里精确查找数据
