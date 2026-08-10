# PDF 解析图表的工具

你要做一个通过 AI workshop 从 PDF 中解析图表的工具。

## 当前实现

安装开发环境后，可用以下命令初始化、执行/恢复以及复核项目：

```bash
uv run pdf-table-5 init INPUT.pdf --project PROJECT_DIR
uv run pdf-table-5 run PROJECT_DIR
uv run pdf-table-5 verify PROJECT_DIR
```

也可以用 `all` 一次完成初始化和执行：

```bash
uv run pdf-table-5 all INPUT.pdf --project PROJECT_DIR
```

只处理原 PDF 中的指定页面时，在 `init` 或 `all` 使用 1-based 页面表达式。原 PDF
不会被拆分，后续产物继续使用原始页码：

```bash
uv run pdf-table-5 all INPUT.pdf --project PROJECT_DIR --pages 5,16-17
```

默认运行时 agent 为 `gpt-5.6-terra`、中等 reasoning。需要覆盖时可使用：

```bash
uv run pdf-table-5 run PROJECT_DIR --model MODEL --reasoning-effort EFFORT
```

初始化后，`PROJECT_DIR/parse/main.py` 暴露 `execute()` 和 `verify()`。工作流通过
Codex CLI 启动 Finder、仅对 `possible` 关系启动 Merge，并为每个逻辑表格启动独立
Parser。`yes` 由调度器直接合并，`no` 直接分开。中断后重复调用 `execute()` 会复用已验证
的中间结果并继续。

每次调用前，调度器把所需 JSON 内容、紧凑 geometry、strategy 文档与签名直接内联到
提示词；Parser 默认只用 `codex exec --image` 附加表格 crop，页面 context 保留精确路径供按需打开。
Agent 在项目根目录的 `workspace-write`
sandbox 中运行，可以读取源 PDF/geometry、执行 parser、重新截图并把诊断文件写入专用 scratch
目录；调度器仍负责正式产物的原子落盘、CSV 读取和确定性校验。提示词提供精确路径，避免无目的
仓库发现，但不限制必要的 shell/PDF 工具。初始化生成的最小 `AGENTS.md` 只澄清这是运行时解析
workspace，避免继承仓库开发任务规则后读取 Skill、创建任务记录或修改无关文件。

Parser 提示词要求按源网格和行中点检查跨行泄漏；相邻记录重复网络节点、分类或电压等级是合法
数据，不作为确定性硬失败。Finder 的跨页合并只允许同页或连续页，缺失中间页时必须先补齐所选
页面，不能把不连续页面静默合并。

每张表的首次 Parser 建立持久 Codex session；Repair 优先通过 `codex exec resume` 继续原会话。
每轮 Repair 都重新附加表格 crop，不能只依赖恢复会话中的旧视觉上下文；返回 patch 前必须在运行
工作区执行候选 parser，并对照 sample 检查所有报告中的抽样差异已经消失。
每表 session、累计 repair 次数、in-flight attempt 和 artifact revision 写入 `states.json`，进程恢复
不会重置 repair budget。首次 Parser 和 fallback-new 使用稳定固定前缀（规则、深层 schema、geometry
loader、验证契约）及 canonical JSON 动态后缀；恢复已有 session 时只发送 review/revision delta，
不重复固定协议或图片。

Parser 返回 `samplePy`，调度器写成 `sample.py` 后再写 `parse.py`/strategy。`sample.py
--table-json TABLE_JSON` 必须向 stdout 输出一个 sample JSON；没有特殊规则时直接输出固定 JSON，
需要处理 PDF 换行连字符时可输出受控 `compareRules`。解析代码以
`table.json`、geometry 或源 PDF 为运行时输入，不得读取 sample、summary、review 或已有
输出。规范 `pdf_table_5.runtime_geometry.load_segments()` 把磁盘 word object 与内联 evidence 统一成
`[x0,y0,x1,y1,text,block,line,word]`；`sample.py` stdout 中的完整 sample 超集由调度器确定性
裁剪/排序。生成在项目 `parse/` 下的 sample/parser/strategy 代码不附加 200/300 行限制；仓库
手工维护源码仍遵守仓库规则。

初始采样应检查每个文本列；只要 PDF 断行使空格或连字符形式不稳定，就在 `sample.py` 中立即为
该列声明 `ignore_space_hyphen`，而不是等 Repair 后再处理。规则必须包含非空 `columns`，通常以空
`rowIndexes` 覆盖整列；日期、范围、编号和数值列没有明确断行证据时不得启用。

Repair 可以直接调整 `sample.py` 的比较规则。调度器会执行修复前后的 sample，并在忽略
`compareRules` 后比较规范输出：原始 sample 未变化时直接应用规则修改；header、rows、totalRows、
mode 或 skipReason 发生变化时，必须启动新的 source-confirm agent。该 agent 只接收当前 sample、
被质疑的位置、PDF crop 和源 geometry，不接收生成 CSV、parser 输出或 Repair 建议值；其源确认
结果会写入 `sampleConfirmation.json` 并反馈给后续原 Parser session。确认提示词明确规定
`totalRows` 包含作为第一物理行的 header；header 单独返回且没有 `rowIndex`，数据 `rowIndex`
从 1 开始，末行索引为 `totalRows - 1`。确认 Agent 返回的 sample 若不满足契约，本次确认记为
`rejected_invalid`，不覆盖当前 sample，也不中止整份 PDF；工作流继续使用剩余 repair。
Repair 返回的 proposed `sample.py` 若自身不能运行或违反契约，记为
`rejected_invalid_proposed` 并进入下一轮 repair。current `sample.py` 已损坏时不再让异常逃出表格：
新的可运行 sample 由 source-confirm agent 从 PDF crop/geometry 独立重建和确认。

Review 对仅有连字符左右空格差异的值自动应用 `ignore_space_hyphen` 等价判断并记录
`hyphenEquivalentMatches`；其他拼写、大小写、数字或字符差异仍然失败。Parser 以 crop 中可见的
单元格边界、合并范围、字符大小写和清晰字形为准；geometry 出现 OCR 污染时必须回看 crop，不能
传播已知乱码。只有视觉证据证明单元格跨行时才复制合并值，缺少网格线本身不构成跨行证据。

运行时按表格区域内的图片覆盖率和原生 PDF words 分类，表格外的标题、表注和页脚不参与判断。
原生文本表格继续使用 PDF words、坐标和网格；真正的嵌入图片表格由 Parser LLM 直接读取附带截图
并转录到 parser。图像表格使用 `sample.py` 的 skip 模式，只做输出格式检查；如果截图被截断或文字
不清楚，Parser LLM 必须先扩大截图范围或提高 DPI，确认完整边界后再返回结果。

## 使用方法

1. 人在 codex 中告知你解析哪个 PDF，和生成的位置
2. AI agent 利用这个工具进解析。
3. 生成一个文件夹：
项目文件/
├── parse/
│   ├── main.py. 暴露2个对外的方法；1. execute，会解析所有的表格；2.verify，会检查表格提取的正确性
│   ├── report/ 记录每个步骤的时间，异常，token 消耗
│   ├── helper/ 中间文件，全局的
│   │   ├── job.json
│   │   └── 其他的文件，详见写书流程
│   ├── tables/ 中间文件，逐个表格的
│   │   └── <table>/
│   │       ├── parserContext.json // 已内联给 Parser 的完整精简上下文
│   │       ├── sample.py // 运行后向 stdout 输出表格抽样 JSON 与可选比较规则
│   │       └── parse.py // 解析表格的脚本
│   └── strategy/ // 策略文件
│       └── strategy*.py // 某种解析策略
└── output/ 最后生成的表格和香港资料

这是一个泛用型的工具，理论上支持 PDF 处理各种表格。但是项目的 parse 只支持指定表格


## 开发说明
请在 reIndex/packages/pdf-table-5/readme.md 这个文件里做逻辑，包括 run.py 调度，各类 task和 各类工具。

请以 reIndex/testbase/test5-table5/sws-netze-solingen-2024/sws_netze_solingen_gmbh_netzausbauplan_2024_pdf.pdf 做第一轮测


reIndex 里还有很多类似测试项目，这些都不太好，不用借鉴流程。按我这个版本来做。

主调度程序拥有项目读写权限；运行时 Finder/Merge/Parser 使用项目根目录 `workspace-write`、
显式图片附件和结构化返回。Agent 可按提示词给出的精确路径使用本地工具，不自行扫描无关文件。



## 解析流程
注： 以下变量，key 的名字都可以改，我英文不好。 中文的都要换成英文
### 1. 需求澄清
发起者： 用户在 codex 里输入需求
执行者： main agent
做什么：
1. 根据用户的需求得到原PDF位置和输出的文件夹
2. 调用一个工具脚本得到 PDF 的必要信息
3. 创建parse/helper/job.json , 内容如下：
```
{
  demand: { // 需求
    inputPath: '' // pdf 目录
    outputPath: '' // 产生文件的目录
  },
  pdfInfo: {
    isValidPdf: true // 是不是可读pdf，不可读，退出
    totalPage： 100 // 一共多少页
    hash // 放置表被换了
    // 页面的形状
    // 其他你认为必要的参数，也可以不添加
  }，
  聚合图信息: {
    // 横向拼几个
    // 纵向拼几个
      // 其他你认为必要的参数，也可以不添加
  }，
  // 其他你认为必要的参数，也可以不添加
}
```
4. 创建 parse/helper/param.json , 内容如下：
{
  // 提取表格的默认分辨率
}
5. 调用 run.py 运行调度程序。


### 2.初始化项目
发起者： 上步之后
执行者： run.py（写在 pdf-table-5 中，其他的执行者工具也是如此）
做什么：
1. 创建 parse/helper/states.json, 内容如下：
```
{
  currentStep: {} // 当前步骤
  currentMergeTableId： -1 当前处理的parse表格
  // 其他你认为必要的参数
 
}
```
1. 创建 parse/helper/steps.jsonl , 内容如下：
{
    id: ''
    type: '',
    creacreatedAtteAt: ,
    endAt: ,
    // 持续时长
    // 话费token
    // 使用的模型
    // 成功or 失败
    // 其他你认为需要的参数，比如记录卡点，问题等
}
  
1. 找 run.py 记录当前的日志等信息， 下面每个步骤之后都要进行操作，不再叙述
2. 调起 taskPaperFindTables.py
  

### 3. 准备查找哪页有表格
发起者： 上步之后
执行者： taskPaperFindTables.py
做什么：

PDF 页面预处理与坐标统一

在 Finder Agent 开始查找表格之前，先通过 PyMuPDF 检查 PDF 页面结构，并建立整个后续解析流程统一使用的页面坐标系。

生成 taskPaperFindTables.json：

{
  "pageCount": 100,
  "pageNumbering": "1-based",
  "coordinateSystem": {
    "name": "visual-page",
    "origin": "top-left",
    "xDirection": "right",
    "yDirection": "down",
    "unit": "pt"
  },
  "pages": [
    {
      "page": 1,
      "width": 595,
      "height": 842,
      "sourceRotation": 0,
      "skipFinder": false，
      “skipReason": "",
      "overviewImage": "parse/helper/finder/pages/page-0001.png",
      "overviewImagePixels": {"width": 793, "height": 1123}
    }
  ]
}

规则：

使用 PyMuPDF 检查每一页是否能够正常读取和渲染。
所有页面统一转换到正常视觉方向下的 visual-page 坐标系。
所有后续流程和 Agent 输出的 bbox 均使用该坐标系：
左上角为 (0, 0)
x 向右
y 向下
单位为 pt
width、height 表示页面经过视觉方向统一后，实际提供给 Agent 查看和截图的页面区域尺寸。
sourceRotation 仅记录 PDF 页面原始旋转信息，用于日志和调试。后续 Agent 不得根据 sourceRotation 再次旋转页面或 bbox。
page 统一使用 1-based 页码。PyMuPDF 所需的 0-based 页码转换由底层公共 helper 负责。
skipFinder=true 只用于能够通过程序确定无需 Finder 检查的页面，例如完全空白页、无法正常读取或无法渲染的异常页。
纯图片页、扫描页不得仅因为不存在 PDF 文本而设置为 skipFinder=true。
原始 PDF 坐标、visual-page 坐标和截图 pixel 坐标之间的转换统一由公共 geometry/screenshot helper 完成，Agent 不负责坐标转换。
   
2. 根据参数渲染逐页图片和聚合图，并把实际图片像素尺寸写回
   `taskPaperFindTables.json`。
3. 通过 Codex CLI 启动 Finder：把精简后的 `taskPaperFindTables.json` 和必要参数完整内联
   到提示词，把所有非跳过页作为初始图片附件。提示词给出建议步骤和结构化返回格式；正常
   路径直接看图并返回，不需要 Finder 自行列文件、读 JSON、探测 PDF 工具或做输出校验。

### 4.查找哪页有表格
发起者： 上步之后
执行者： finder agent
做什么：
1. 逐个的检查图片，看看哪里有表格
2. bbox 只需给出带大边距的近似范围，不追求文字块或绘图矩形级精度；后续准备阶段会再扩展
   并裁剪到页面范围，优先避免标题、边界行和续表被截断。
3. 以结构化结果返回 findTable.json 内容，由调度器校验并写入文件：
```
{
  tables: [
    {
      findTableId: 1,
      preFindTableId： 0
      page: 1,
      // 范围（多给点四周边距，防止截图截少了，如果可能包括表格标题）
      // 推荐 merge 时多分
      //  "mergeWithPrevious": "yes|possible|no", yes： 如果页面是相连，并且能确定是一致， possible：如果页面是相连，并且看起来一致，就算possible，不确定都算possible，其他事 no
      // 其他你认为需要的参数，也可以不添加

    }
  ]
}
```
4. 调度器写入推荐分辨率和最终校验结果。

### 5. 准备合并表格
发起者： 上步之后，
执行者： taskPaperMergeTables.py
做什么：
1. `mergeWithPrevious=yes` 由调度器直接并入前一组，`no` 直接新建一组；只有
   `possible` 进入 Merge Agent。
2. 只对 `possible` 当前段和前一段截图。
3. 生成只含必要 pair 记录、图片尺寸和图片映射的 `paperMergeTable.json`：
```
{
  tables: [
    {
      findTableId: 1,
      preFindTableId： 0
      page: 1,
     "mergeWithPrevious": "yes|possible|no"
    // 其他你认为的必要参数，也可以不佳

    }
  ]
}
```
4. 把 `paperMergeTable.json` 完整内联到提示词，并把 pair 图片作为初始附件。Merge 只返回
   每个 `possible` 关系的布尔决策和理由；调度器据此生成、校验 `mergeTable.json`。

### 6. 合并表格
发起者： 上步之后
执行者： merge agent
做什么：
1. 通过内联 pair 信息和附件判断 `possible` 表格是否连续；无法判断按 false。
2. 返回 `mergeDecisionsJson`，不重复处理已确定的 `yes`/`no`。
3. 调度器生成 mergeTable.json：
{
  tables: [
    { // 可合并的表格放到一个数组里
      tables: [{ 
         findTableId: 1,
      截图文
      page: 1,
      // 范围（多给点四周边距，防止截图截少了，如果可能包括表格标题）可以更新范围如果需要
      // 推荐提取表格时多分辩率，可以更新分辩率 如果需要
      // 可以和前一个表合并： true or false， 如果无分判断按 false，但尽可能要准确判断
      // 其他你认为需要的参数，也可以不添加
      }]
     
    }
  ]
}
4. Agent 正常路径不读取 workflow skill、helper 文件、旧项目、实现代码或 contract；这些
   必要信息已经汇总在提示词中，最终校验由调度器完成。

### 7. 列举表格
发起者： 上步之后或第5步跳来
执行者： taskListTables.py
做什么：
1. 合并 mergeTable.json 和 findTable.json，生成 listTable.json,如：
{
  tables: [{
    parseTableId,
    findTableId: []
    tables: [ // 数组是考虑表格可以合并
      {
        page: 
        范围
        // 其他你认为必要的参数，也可以不添加
      }
    ],
    // 其他你认为必要的擦拭，也可以不添加 
}]
}
2. 创建一个空的， parse/helper/finalTable.json


### 8. 单个表格提取准备
发起者： 上步完成后
执行者: taskPaperTable.py
做什么：
1. 增加当前表格索引（第一个表格从 -1 变成了0），如果发现没有表格来就到第 12步 整理结果
2. 给当前表格截图，放到 parse/tables/<table> 中
3. 调取PyMuPDF解析当前页，放到  parses/table/<table> 中
4. 创建一个  parse/tables/<table>/table.json, 里面包含：
```
{
    parseTableId,
    findTableId: []
    tables: [ // 数组是考虑表格可以合并
      {
        page: 
        范围
       // 截图文件
       // PyMuPDF 提取的文件
        // 其他你认为必要的参数，也可以不添加
        // 表格是不是图像
      }
    ],
    // 其他你认为必要的参数，也可以不添加

```

5. 生成 `parse/tables/<table>/parserContext.json`：包含精简后的 table packet 和 word geometry。
   少于 4 个 segment 时内联全部 geometry；4 个及以上连续 segment 默认只内联首段和尾段，并只
   附加首尾 crop，中间段保留页码、bbox、geometry 绝对/相对路径及 word/image count。生成代码通过
   runtime loader 直接运行所有 segment；只有 Review 失败或首尾证据冲突时才按需检查中间页。
   提示词传输时按视觉线共享 `y0/y1`，线内保留每个 word 的 `x0/x1`、文本及原始
   block/line/word 索引，可无损展开；另附左边缘 visual-line 计数提示、附件映射、规范 runtime
   geometry loader，以及已有 strategy 的适用说明
   和公开函数签名。Runtime paths 同时给出项目根目录、源 PDF、table.json、scratch、geometry 的
   project-relative/absolute path、word/image count，以及 crop/context 的绝对路径。生成 parser 优先
   直接调用 `pdf_table_5.runtime_geometry.load_segments(table_json)`；返回的 segment 是字典并以
   `segment["words"]` 访问，不自行猜测磁盘 word shape 或使用属性访问。同一 cell 的有序 words
   优先交给 `join_word_text()`，依据 visual-line 坐标区分断行连字符与同一行的 `Schutz- und`，并统一
   处理 `MS-/NS-/ONS-` 复合词和独立短横线。
6. 通过 Codex CLI 启动一个持久 Parser session，把 `parserContext.json` 完整内联到提示词，并
   附加当前表格 crop；页面 context 已有按需路径。正常建议路径直接返回深层 schema 约束的
   sample.py、summary、parse.py 和可选 strategy，由调度器执行；只有证据冲突或 Repair 诊断才使用
   Shell/PDF/scratch。session id 写入状态，后续 Repair 恢复同一会话。


## 9 提取表格
发起者：上步完成后
执行者：parse agent
做什么：
1. 直接使用提示词内联的紧凑 evidence 和初始图片附件
2. 判断是不是需要处理的表格， 比如目录、缩写、图表这些不属于图表直接跳过
3. `imageTable` 由调度器根据 vector word/image count 确定，Parser 只能复制严格 boolean。运行时
   读不到已知存在的 geometry 是 loader failure，不得据此改判图像表。

如果表格是图像：
1. 直接视觉提取表格数据，房东啊 parse.py 里
2. sample.py 输出 skip sample，直接标记忽略内容检查
   

如果表格不是图像：
1. 如果数据行不超过 6 行，全部抽样；否则抽表头、前 3 行、后 3 行及总行数。`totalRows` 包含
   表头，`rows[]` 固定为 `{rowIndex, values}`。Parser 在
   结构化结果中先设计 sample.py；调度器先写 `sample.py`，执行后读取 stdout JSON，再执行解析
   代码。总行数必须由 source
   geometry 的记录锚点精确核对，禁止为匹配错误总数而生成、插入或保留全空数据行。
2. 判断这个表格是否可以用已有 strategy：
   1. 如果能用且不需要修改 strategy*.py或不对 strategy*.py 进行破坏性变更： 创建 parse/tables/<table>/parse.py（ 执行这个函数可以提取表格）， 里面可以调用  strategy*.py，（这里运行修改 strategy*.py 是因为有时前面写策略考虑不充分，但如果一单回破坏性变更，如参数的破坏性变更，不能用词方案。
   2. 如果能用但需要对  strategy*.py 做破坏性变更：  创建 parse/tables/<table>s/parse.py（ 执行这个函数可以提取表格）， 里面不可以调用  strategy*.py，提前说明用了哪个策略， 
   3. 如果没合适的策略： 创建 parse/strategy/strategy*.py ,上面用固定的格式写好策略适用的条件，和策略的用法和经验， 建 parse/tables/<table>/parse.py（ 执行这个函数可以提取表格）
   注意 sample.py、parse.py 和 strategy*.py 只以 table.json、geometry 或源 PDF 为运行时输入；
   sample.py 不读取 parse.py、review、sampleConfirmation 或已有 CSV，parse.py/strategy 不读取
   sample、review、sampleConfirmation、summary 或已有 CSV。生成代码不附加 200/300 行限制。
3. 已有 strategy 只向 Parser 提供适用说明和调用签名；匹配时按需选择，不匹配时直接返回
   新 strategy，不自行读取全部 strategy 源码。
4. 生成一个 summary.json, 如下：
```
{   
   // 表格的类型
   // 表格的页面
   // 表格页面中的位置
   // 表格前面的文本
   // 表格后么的文本
   // 不是需要提前的表格， 如果为true 就步按表格做了
   // 时不是图像表给， 如果为 true， 就不做抽样检测了
   // 提取用到的策略
   // 是否是一个可以 SQL 化的表格
   // 提取改表的分辨率
   steps： [
    {}， 第一轮的记录，包括卡点，问题，用来给后人提供经验
    {}， 如果有修复，记录修复的情况，为什么要修复
   ],
  // 其他你认为必要的参数，也可以不添加
}
```

## 10 检查表格
发起者：上步完成后
执行者：taskReviewTable.py
1. 如果是不用提取的表格跳过
1. 由调度器运行 parse/tables/<table>/parse.py 生成表格到 output 中
2. 对生成表格的格式检查，包括 UTF-8、矩形列宽和禁止全空数据行
3. 执行 `sample.py` 取得抽样 JSON，再与生成表格做内容比较。默认精确比较；sample 输出的
   `ignore_space_hyphen` 必须按列启用，也可再用抽样行收窄；它忽略空白及 PDF 连字符差异，并在
   review 中记录等价命中的单元格而不启动 Repair。只有调度器判定的真图像表可以 `format_only`；
   vector table 必须内容和格式都通过才能 accepted。
4. 通过或跳过上述检查后在 parse/helper/finalTable.json 增加一个 item：
```
{
  parseTableId,
  // title
  tables: [
    {
      page:
      位置：
      是不是图像表格，
    }
  ]，
  // 前面的文本
  // 后么的文本
  // 其他你认为必要的参数，也可以不添加
}
```
1. 如果检查成功就回到第8步 单个表格提取准备
2. 如果检查失败，调度器恢复该表原 Parser session，并发送精确 review、artifact revision 和路径。
   Resume 只发送动态 delta，不重复固定协议或原始图片；Repair 仍可按路径读取 PDF/geometry、运行
   候选 parser 和截图。返回 nullable field-level patch，`null` 字段保持原值。会话不可恢复时才用
   完整 context 和表格 crop fallback 到新 session，且不增加 repair budget。

## 11 修复表格
发起者： 上一步完成后
执行者：parse agent
做什么：
1. 根据内联反馈、紧凑 CSV profile 和 geometry 提示判断是 sample.py、parse.py 还是两者的问题。
   Repair 可以修改 samplePy；调度器执行当前和建议脚本后，先比较忽略 compareRules 的规范 sample。
   只有规则变化时直接应用；原始 sample 有变化时必须先由新的 source-confirm agent 独立确认。
2. PDF 换行连字符只影响等价形式时，优先在 sample stdout 的 `compareRules` 中声明规则；sample
   内容或总行数本身可能错误时提出 samplePy 变更，CSV 提取错误时修 parsePy，两者都错时可同时提出。
   source-confirm agent 只看当前 sample、变化位置和 PDF crop/geometry，不看 CSV actual、parse.py 或
   Repair 建议值；其确认结果决定最终 sample。对可 SQL 化表格，跨多个数据记录的源合并单元格必须
   把完整多行值复制到每个记录；不得把日期范围与括号限定词拆到相邻 CSV/sample 行，也不得为了
   匹配错误 CSV 把正确 sample 改成这种碎片。
3. 修复后可在 summary.json 增加修复记录；调度器只合并非空字段并校验 base revision，随后重新
   执行 sample.py、parse.py 和内容检查。已确认的 sample 来源结果写入 sampleConfirmation.json 并
   反馈原 Parser session，但生成代码不得读取该文件。未修改的 artifact 保持原值；step 日志记录
   本次实际修改的 artifact 名称，便于区分 sample 修复和 Parser 修复。
4. 累计 repair budget 耗尽后标记 `failed`，继续处理其他表；不得通过修改 `imageTable`、sample mode
   或 skip-content 标记降低 vector table 的验证门槛。
5. 任一表在 prepare、Parser、Repair 或 Review 中抛出未预期异常时，只将该表标为 `failed`，记录
   异常并继续后续表；最终复核同样按表隔离，整体报告保持 `accepted=false`。

### 12 整理结果
发起者， 第10步检查表格触发
执行者： taskReprotTable.py
做什么：
1. 删除 output，运行所有的表格再做一遍最终检查
2. 把 parse/helper/finalTable.json 复制的 output/finalTable.json
3. 如果检查错误，回到第 11 步修复
4. 生成 parse/report，记录所有表格内容；失败项另外写入 `failedTables`，包含页码、累计 attempts、
   最后错误、日志目录和可能存在的部分输出。
5. 如果所有表格检查通过，结束 run.py 交回主 agent

### 13.主agent 处理
1. 检查当前是出现问题，还是完成

如果出现问题：
重新调用 run.py ,继续执行，并可做适当调整，如果多次都失败，跳出

如果是完成：
告知用户完成，列出生成表格的目录，用时，消耗的 token，一共多少表，哪些表存在问题， 后续提取过程的优化建议， 相当于一个简要报告。


注意：
表格的最终状态：
verified：格式 + sample 内容检查通过。
format_only：仅限调度器确认的真图像表通过格式检查。
skipped：目录、缩写表、非目标表等，本来就不提取。
failed：执行、格式或 vector sample 内容未通过且修复耗尽；流程继续，但整体 accepted=false。
以及一个 accepted true （图像表通过形式检查，矢量表通过 内容+形式检查，没有表不用提取）or false


我确认 sample.py 让 parse agent 自己生成，原因：
1. 生成 sample.py 时 parse agent 并不知道 parse.py 的执行结果；sample.py 也不能读取 CSV
2. 如果找两个 agent，分别生成，如果不一致到底是谁的问题，怎么评判挺难的，一下子能拖慢解析速度。
3. 提示词的时候要强调下不能作弊

我确认 图像类的表格，不做内容检查，原因：
1. 如果进行内容检查，又要调一个 agent 解析，耗token
2. 如果不一致，听谁的？
