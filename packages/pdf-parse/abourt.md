这个是任务说明，请 AI 不要修改这个文件。

# 目标
我要做一个利用 AI 的 PDF 解析器。
目标是结合 AI 的 workflow，把 PDF 转成 markdown， 其中的表格需要准确的提取。

# 你需要提前了解到
你需要先学习下 liteparse ，我想借助这个做，包扩如下的页面：
https://developers.llamaindex.ai/liteparse/getting_started/
https://developers.llamaindex.ai/liteparse/cli-reference/
https://developers.llamaindex.ai/liteparse/api/

你最好把这个功能都了解下，我们要利用这个库

然后可以看下
reIndex/packages/pdf-table-5 解析工具，这是我之前做的 PDF 解析表格的工具， 可以了解下。但是不要用这里面的代码，也不要借鉴，里面有很多啊问题，记住不要借鉴里面的一些内容。
项目里的其他文件都不要看了，有太多问题。

# 项目的架构概览
## 库目录
类似 pdf-table-5 ， 把核心的调度 runtime ，工具，提示词等都放到 reIndex/packages/pdf-parse 里，但要重新设计项目架构。
我想的是分 task， 并且中间根据不同的页面类型分不同的 task
项目的结果我建议这样划分
runitme 是整体调度， task 是各子部分， tools 是通用的工具

src/ 源代码
  tools/ 各种工具，脚本，有为 AI 使用的
    agentCLi/ 唤起 agent 流程等 工具
    // PDF 局部截图工具
    // 对 liteParse 生成的 geometry 进行裁剪的工具
  tasks/ 各个任务
    task1/
      index.py
      xxx 其他和这个 task 有关的代码，比如提示词等
    task2/
      index.py
      xxx 其他和这个 task 有关的代码，比如提示词等
    
  runtime/  调度器
    index.py 入口
  main.py 入口


## 项目目录
然后对于要解析的pdf成长项目目录，你以 l/Users/maxiao/Documents/code2/lab-table-parse/bielefelder-netz-2022/2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf 作为项目目录，AI work flow 生成的代码，内容都可以放到 l/Users/maxiao/Documents/code2/lab-table-parse/bielefelder-netz-2022/parse 这个里面。
生成的目录大概是
- parse
  - main.py  暴露2个对外的方法；1. execute，会解析所有的表格；2.verify，会检查表格提取的正确性 3.等
  - report/ 记录每个步骤的时间，异常，token 消耗
  -  helper/ 中间文件，全局的
  -  blocks/ 每一个表格的处理代码
- output 最后成品
   output.md 最终生成的资料 （生成的 md 最好业关联下表格的位置）
   assets
    - table1.csv 
    - talbe2.csv
    - image1.png
  - metadata.json 描述章节、图片、表格的顺序关系。

# 注意事项
- main agent： 主要的 agent，是在 codex 里对话的 agent
- xxxx cli agent: 由代码通过执行 codex cli 唤起的子agent， 用 gpt-5.6-luna，思考等级 high
- runtime： 调度代码
- 唤起 cli agent 时尽可能的把他需要的所有东西都放到提示词里，避免 agent 后续来回调用工具，浪费提示词， cli agent 有 parse/ 目录的完整读写权限。cli agent 输出内容 给 runtime，由 runtime 校验后落地代码、配置。
- 不要进行过度的防卫性的设计，过多的兜底， 需要简化整个流程。 
- 用python 代码，有些我写错了，写成js，你当python 处理
- 说表格的第几行是包含表格头的， 例如一个表格有1个头 + 5行内容， 说第二行其实是表格的第一个内容行。 如果表格没有表格头，第二行就是第二个内容行
- 提示词中要先出可以供 cli agent 适用的截图工具，
- cli agent 是可以调用 tool 的，也可以调用 liteParse 的，提示词应该说明
- 注意统一页面的坐标，可以用 liteParse 的，如果用不了，要搞个通用的方案，最好用 liteParse的 ，下文的 bbox 可以换成别的
- 为了防止一些PDF 页面太大，渲染慢，需要对截图的时候加上限制
- 给 AI 的提示词不应该是整段的，而是分开的，这样可以根据实际需要组合
- 如果可以用 LiteParse， 尽量用它，不要跟用pymupdf，保证技术栈的简单统一
- 生成的表格最好能处理换行符的问题，尽可能把数字改成数值类型
- 如果中间有步骤失败，只要不是程序错误卡住流程的，就继续完成PDF 所有内容的解析，例如如果解析的表格没通过校验，还可以继续

# 流程
## 1. 需求澄清
处理人： main agent
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
      // 获取举办geometry的 工具
  }，
  // 其他你认为必要的参数，也可以不添加
}
```
4. 创建 parse/helper/param.json , 内容如下：
{
  // 进行进一步解析的分辨率
}
1. 调用 run.py 运行调度程序。

## 项目初始化
处理人： runtime
1. 创建 parse/helper/states.json, 这个是当前的总体状态，执行到哪一步的追踪，是权威的状态，
2. 创建 parse/helper/steps.jsonl , 这个是对每一步的记录：
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
2. 调起 liteParse

## 3. litePares markdown 解析
执行人 taskLiteParse
运行 liteParse， 
1. 生成 PDF 的结构目录:
包括有哪些页， 每页有哪些分区，分区的 id，范围,是否为复杂等
（你需要了解下 liteParse 怎么统一 PDF 等坐标系，进行旋转/缩放等操作的）后续的代码需要统一下 PDF 的坐标系。最后生成一个。parse/helper/block.json ，类似(类型不一定和下面的完全一样): 
```
[
  {
    blockId:  // 如果 liteParse 有id，就用，如果没有就顺序 index
    page:
    bbox:
    liteParseType
    preType: liteParse 生成的type
    // ... 等到
    needsAgent: true // 图片，表格，公式，复杂的， 可疑表格，需要 OCR 的页面， 也就是 litParse 生成的 need_ocr, is_complex 等
     // 其他你认为必要的参数，也可以不添加
  }
]
```

2. 对类型进行划分路有处理：
2.1 简单的文本，也就是标记 needsAgent 为false的：
直接由 liteParse 生成 文档

2.2 对于复杂的部分，也就是 needsAgent 为true的：
对复杂的页面部分进行截图（较低分辨率，因为这里只用区分类型，不用看清文字），并且划分 block 块：
同时需要一个 一个 classifyBlock.json， 就是上面的 block.json 过滤出 complex 部分后的内容。


最后交由taskPreClassify 



## 4. block 分类准备
处理人 taskPreClassify
把 liteParse 的图进行聚合，整理 classifyBlock.json， 和提示词，唤起  Classify CLi agent。
也就是说只把含复杂元素的部分，交给 classify cli agent，并准备相关的内容，和提示词


## 5. block 分类
处理人 Classify CLi agent，通过 taskClassifyAgent 运行
利用其angent 的视觉能力，对类型进行分类：
生成 parse/helper/calssifyBlock.json:
```
[
  {
    classifyBlockId: ,
    blockId: [] // 映射 litePares 的 block id， 因为有可能会把 liteParse 生成的多个 blockId 合并，
    bbox: 最好和 liteParse 能统一坐标系
    preType： 类型（litePare 解析的类型，如表格）
    ClassifyType: 类型，这里主要是对 litePare 对解析结果进行纠正
    canMargePreTable：如果上页是一个表格， 并且可能和上页的表格 merge，返回 true（如果不能确定和上页的表格能否合并，页返回 true)
     // 其他你认为必要的参数，也可以不添加
  },
  //其他的 blcok
]
```
记住仅针对  needsAgent 的block 进行分类
相当于进行 blocks 的类型的纠正，以及拆分与合并。
给 Classify CLi agent 提供的是完整页面的截图，但是它只用给 needsAgent 进行再词分类，其他的不用。需要 OCR的，表格等都需要 needsAgent。


## 6. 对不同的 block 处理
处理人  taskBlockRoute.js

创建一个空的 parse/helper/parsedBlocks.json

根据 block 的类型对页面进行处理：
1. 对表格交由后面面对 taskPreTable 处理
2. 对其他的交由 taskDefault 处理， taskDefault 目前不做特殊处理，实际上最后还用 liteParse 最初的处理结果
  

## 7. 对表格提取准备
执行人 taskPreTable
1. 从 classifyBlock.json 找到下一个要处理的表格，如果没有表格直接去第11步
2. 给当前的PDF 页面block局部进行搞清截图（一定要加足够的边距），我觉的足够表示（10个页面中的文字的宽度）
3. 生成 PDF 相应范围的原始数据（geometry） (我没想好用 PyMuPDF，还是 liteParse 处理，是不是要截断防止数据太多) ，只带当前表格的，不用带后续可能可以 merge 的表格
4. 创建一个  parse/blocks/<table-table-<classifyBlockId>>/preTable.json, 里面包含：
5. 如果下一个表格（或多个表格）标记了 canMargePreTable，需要带上下面表格的清晰截图。 

```
{
  parseBlockId: ''
  blocks: [ // 数组是怕后需表格有合并
    {
    classifyBlockId： 用于映射会 clasiifyBlock
    bbox
    截图文件
    // 表格是不是图像
    // 其他你认为必要的参数，也可以不添加 
    }，
    { // 如果后么的表格是可以合并的，加上这个

 // 其他你认为必要的参数，也可以不添加 
    }
  ]
}
```

6. 以上内容构建为完整提示词后发给 tableParse agent （注意每一个新表格唤起一个 agent，如果后面需要修改这个表格，还用这个agent，不用唤起新的 agent）

最后给 agent 的提示包括：
1. 基础提示词
2. preTable.json
3. 低分辨率低全页截图
4. 高分辨率低部分区域截图
5. 部分 geometry
6. 如果后续也可能merge，后续页的全页截图+ 区域截图
7. 截图工具的用法， geometry 裁切工具的用法


## 8. 提取表格
处理人 tableParse agent，通过 taskTableParseAgent 运行

做什么：
1. 先读取截图
2. 判断是不是真是表格，如果不是表，也创建一个 parsedBlocks，但是 status 为 skipe的，交由 liteParse 的默认解析结果
3. 判断当前表的下一个（或连续的下几个）表格有没有 canMargePreTable，如果有先判断能否和后么的表格合并
4. 根据这个表格是不是图片分两个思路：
4.1如果这个表格是图片：
直接让 llm 视觉识别出这个表格，识别出的放到 blocks/<table>/parse.py， sample.py 中直接标注忽略采样校验


4.2如果是
4.2.1 对于表格的前三行后三进行视觉抽样(如果不超过 6行全部抽样)， 抽样时要设定规则，包括：1）如果有换行连字符，需要加准许换行连在符合的标记，2）如果是数字，要给数字标记， 生成一个文件放到 blocks/<table>/sample.py 中。 这里需要搞一个特殊的校验机制，准许插入新的功能，放置出现因数字、连字符导致的问题。对于数字之间采样成标准数字，去掉千分位，如果有都是相同前缀、后缀等也去掉（下面写parse.py 也是类似逻辑）。 规则提取预设好。有标准的 siample.py 模版
4.2.2. 生成能解析这个 PDF 的专有代码，放到 blocks/<table>/parse.py 中，过提示词规定不得 agent 用采样结果对 parse.py做特殊处理，防止作弊。（PDF 是不是可以有一套生成 parse.py 的流程？有的话加上，前提是有足够的灵活性）


5. 生成一个 blocks/<table>/summary.py, 如下：
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
    {}， 每一轮的记录，包括卡点，问题，用来给后人提供经验，还有包括它是依靠图片，还是依靠 PDF 源代码还是用什么样的方式提取表格的，以及对后续提取表格的建议，和已有框架的改良建议
    {}， 如果有修复，记录修复的情况，为什么要修复
   ],
  // 其他你认为必要的参数，也可以不添加
}

```
注意：
- parse.py 和 sample.py 都提供标准的模版 ，且每个表格都有一个单独的
- 让 LLM 直接视觉读取表格，而不是调用个 OCR 工具进行识别文字，包括整个表格为图片的也是让 llm 视觉提取
- 确认采样和 parse 都用一个 agent，这样速度快，效率高，并且万一不一致方便判断，而且 agent 只写代码，并不运行，因此也不知道 parse 是否合适。
- 确认图片表格只进行形式检查，不进行抽样检查，因为缺少比对对象， ORC的结果不可靠
- agent 要先进行采样，再进行解析。


## 9. 检查表格
处理人 taskReviewTable.py
1. 如果是不用提取的表格跳过，并做标记
2. 由调度器运行 parse/blocks/<table>/parse.py 生成表格到 output 中
3. 对生成表格的格式检查，包括 UTF-8、矩形列宽和禁止全空数据行
4. 执行 `sample.py` 取得抽样 JSON，再与生成表格做内容比较， 如果加了些规则，要用这些规则进行比较， 防止 sample 过于严格，把连字符分开的表格，数字因为小数点格式等不一致导致问题。


4. 通过或跳过上述检查后在 parse/helper/parsedBlocks.json 增加一个 item：
```
{
  parseBlockId,
  // title
  blocks: [
    {
      blockId:
      classifyBlockId:
       // 其他你认为必要的参数，也可以不添加 
    },
  ]，
  status
  // 其他你认为必要的参数，也可以不添加
}
```
1. 如果检查成功就回到第7步 解析下一个表格
2. 如果检查失败，进行下一步：修复表格，并给与完整的提示词，包括错误原因，生成表格的结果


关于生成的结果类型分为：
status:
- pass: 通过校验，图片表格仅形式检查，非图片表格要形式检查+抽样检查， 或者本身不是表格
- failed：应该有，表格生成，表格没有生成
- wrong: 生成了表格，但是表格存在错误
- pending： 未处理
- running： 开始处理，但未完成处理
- skip： 跳过，不需当作表格处理的 block，继续用 liteParse 的解析结果



## 10 修复表格
执行者 tableParse agent
做什么：
1. 根据反馈，判断是 parse.py 生成的结果错还是 sample.py 采样错。
2. 根据错误类型进行响应修改。 如果判断是  parse.py  错，则修改 parse.py ;如采样错就修改采样。通过提示词规定不得 agent 用采样结果对 parse.py做特殊处理，防止作弊。
3. 修复后，要在 summary.json 中增加修复记录，包括错误办法和错误原因
4. 如果多次修复失败后，可以标记 ·failed·，到第7步准备解析表格，处理下一个表。





## 11， 整理结果
执行者: taskFinaly.py
1. 把生成的表格以及其他的blcok 最后组装成 markdown，复杂的用 html 标签，简单的用 markdown 的表格格式。 如果 status 是 skip，就还用 liteParse 的解析结果。 我建议不要从 liteParse 生成的 markdown 组装，而是通过 block.json 组装这样更加可靠， 组装的表格最好能架构标注
2. 生成生成 parse/report，包括各个block，子截断的耗时， token数， agent 对话数，错误数， reaperi 数等到内容。以及最后有哪些 block 是 false 或者 wrong 的

### 13.主agent 处理
1. 检查当前是出现问题，还是完成

如果出现问题：
重新调用 run.py ,继续执行，并可做适当调整，如果多次都失败，跳出

如果是完成：
告知用户完成，列出生成表格的目录，用时，消耗的 token，一共多少表，哪些表存在问题， 后续提取过程的优化建议， 相当于一个简要报告。


# 最终流程：

初始化
  ↓
LiteParse 一次性提取 JSON
  ├─ 页面信息、文本 geometry
  ├─ layout blocks / table cells
  ├─ complexity / needs_ocr
  └─ 页面截图
建立统一 document block，即 ->block.json (blockId)
  ↓
筛选具有block 的页面，得到 
对不确定block的页面用 AI agent 进行区分block
  ↓
对表格进行特殊的处理，用 AI agent, 即 -> classifyBlock.json (classifyBlockId)
  ↓
将连续/跨页 table block 组成 table group -(parseBlockId)
按难度选择表格提取策略
  ├─ 直接使用 LiteParse 表格
  ├─ geometry 规则解析
  └─ AI 视觉解析
  >parsedBlocks.json
  ↓
独立验证
  ├─ 结构检查
  ├─ 内容抽样
  └─ 完整性/覆盖率检查
  ↓
有限次数修复
  ↓
按照 document graph 生产 dockment
  ↓
生成 output.md、assets、metadata、report