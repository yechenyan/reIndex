# 左侧树默认展开一级

状态：等待人工审核

## 原始请求

> 左侧的树状图默认只展开一级，修改完后直接部署

## 范围与验收

- Explore 页面首次加载或切换 Collection 时，仅展开顶层 group Node。
- 保留用户手动展开、收起及筛选时的现有行为。
- 运行 Web 构建检查，并将变更推送以触发 Render 部署。

## 决策

- 以 `NodeSummary.depth === 0` 识别顶层节点；只将顶层且为 group 的节点加入初始展开集合。

## 实施与验证

- 更新 `packages/web-app/src/components/CollectionTree.tsx`：每次节点列表载入时，仅初始化展开顶层 group Node。
- 已运行：`pnpm build`（在 `packages/web-app/`），通过。
- 文档审查：`packages/web-app/README.md` 仅说明页面包含 Collection 与 Node tree，不描述默认展开层级，无需修改。
