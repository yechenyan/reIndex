# PDF 表格提取 Workflow

`packages/pdf-extractor-pdf` 用固定代码约束一次性的 Agent 工作，生成可重复运行的 PDF 专用表格 extractor。它不依赖一个通用解析器猜出所有表，而是先让 Agent 视觉覆盖全部页面，再冻结逻辑表清单。

## 项目交付

目标项目只有两个交付区域：

```text
project/
├── output/          最终 CSV 和 result.json
└── extractor/       除 output 外的全部代码和证据
    ├── job.yaml
    ├── main.py      统一运行入口
    ├── 其他专用代码
    └── evidence/    缩略图、裁图、清单、QA、Review 和 Metrics
```

package 自身保持在 `packages/pdf-extractor-pdf`，不得把项目产物写回 package。

## 七个阶段

1. 主 Agent 只澄清会改变结果的必要问题，然后创建 `job.yaml` 和任务指令。
2. 代码计算 PDF 哈希，生成全页低清缩略图、滑动 Contact Sheets 和尺寸/旋转/文字量信息。每张 Contact Sheet 默认 8 页，下一张重复上一张末页，帮助判断跨页连续关系。
3. 找表 Agent 逐页标记 `table/no_table/continuation/uncertain`，将物理 Segment 归入逻辑表。冻结前代码为每个 BBox 生成整页 overlay；Finder 必须复核四条边并提交 overlay 哈希。代码检查全页覆盖、截断文字、BBox 和结构；消除全部 uncertain 后冻结 Inventory（硬门 1）。
4. 代码为冻结 Segment 生成高清裁图与中性几何证据。提取 Agent 写版式规则和 Merge Policy；隔离 QA Agent 先填写表头和各 Segment 行数，代码据此生成适配当前表格的首尾/中间/跨页边界抽样索引，再由 QA 从源图填写样本值。
5. 代码在受控子进程执行 extractor，实际完成去重表头、去页脚、断行和跨页合并，保留逐行页码/BBox/Segment。Validator 双跑并与 reference 比对，生成面向主 Agent 的紧凑 `review.json`，其中只包含问题相关源截图、Extractor/QA 同行值、单元格差异和路由。合并候选依赖连续性证据，不以列宽相似单独判断。
6. Review 先把逐行/逐单元格错误聚合成每张表一个根因 case，再确定性路由。派发前冻结 Repair Scope，子 Agent 只能读取和处理错误表；固定代码保护其他表的 Inventory/reference/result 哈希。逻辑表合并/拆分必须显式 reopen Inventory，不能直接改冻结文件。
7. 全部检查通过且无高置信合并候选后，`finalize` 生成机器完成记录（硬门 2）。机器完成不等于人工审批。

## 开始一个项目

```bash
uv run pdf-extractor-pdf init PROJECT SOURCE.pdf --request "提取全部表格"
uv run pdf-extractor-pdf prepare PROJECT/extractor/job.yaml
```

后续命令和 draft JSON 格式见 package 的 [README](../../packages/pdf-extractor-pdf/README.md) 与 bundled `SKILL.md`。

## 可恢复性和度量

冻结时会把 Agent draft 按内容哈希保存在 `extractor/evidence/agent-output/`。每个项目命令的精确墙钟时间写入 `metrics/commands.jsonl`；Agent 的模型、活跃/等待时间、对话次数、修复轮次和 Token telemetry 写入 `metrics/agents.jsonl`。宿主不提供精确 Token 时必须记录 `null`，不能伪造精确值。

extractor 在超时、固定 hash seed、禁止 bytecode 和临时结果路径的受控子进程运行；这不是安全边界。运行不可信代码时，调用方仍需提供 OS 或容器 sandbox。

对具有跨页连续性信号但经源图确认应保持独立的相邻表，使用 `resolve-merges` 冻结带 Segment 证据哈希的主 Agent 裁决；不同表号/标题是强反证，列宽相似只说明版式相同，不足以产生候选。完成后可用只读 `verify-cache` 复核缓存，`check` 则只校验最近 Review 和 output 哈希，不再重复执行 extractor。

生产运行默认使用四个不同 `agent_id`：主 Agent、找表 Agent、执行 Agent、QA Agent。找表是 Inventory 硬门前的串行步骤；冻结并完成 `inspect` 后，执行与 QA 并行。硬门 2 会验证四个身份和两个并行时间区间。每个角色用 `stage-start/stage-finish` 自动计时，最后由 `metrics-report` 同时输出累计 Agent 时间和并行墙钟包络。

`inspect` 无需手工传 `--segments`。每个 Segment 用源文件、页码、BBox、旋转和 DPI 计算指纹；Inventory 局部重开后只重做指纹改变的裁图，未改变证据自动复用，旧证据仍保留用于追踪。
