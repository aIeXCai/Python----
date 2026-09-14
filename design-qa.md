# Design QA — AI 选择题库筛选区与选择列

## Comparison metadata

- Source visual truth: `/var/folders/bn/61rtkld10mx6zykws10ps7800000gn/T/codex-clipboard-4c0fea62-bbfe-497d-91cd-21030b03136f.png`
- Implementation: `http://127.0.0.1:5173/teacher/ai`，选择题库 Tab
- Implementation screenshot: `docs/reports/assets/ai-choice-bank-filter-after.png`
- Normalized comparison: `docs/reports/assets/ai-choice-bank-filter-comparison.png`
- Source size: 2880 × 1556 px
- Implementation viewport: 1280 × 720 CSS px；截图 1280 × 720 px
- State: 七年级、12 道题、未选中题目、批量删除按钮禁用

## Findings and fixes

- P1：筛选控件仍呈原生表单观感，尺寸和间距不统一。已改为响应式网格，统一 40 px 高度、9 px 圆角、边框、悬停与焦点状态，搜索框占据剩余空间。
- P1：表格“选择”列宽度不足，表头文字被拆成两行。已固定为 72 px，并设置居中与不换行。
- P2：窄屏下筛选项可能过度拥挤。已增加 1100 px 两列布局和 640 px 单列布局。

## Fidelity surfaces

- Typography: 延用现有教师端字体层级；“选择”表头单行显示。
- Spacing: 筛选控件间距统一为 10 px，筛选卡片与批量操作卡片保持现有页面节奏。
- Color: 延用现有紫蓝主题、浅灰边框和焦点色，不引入新的视觉体系。
- Assets: 无新增位图资源；保留现有 Lucide 图标。
- Copy: 原有筛选项、搜索提示和表格字段均保持不变。

## Interaction and regression checks

- 全选后 12 个题目复选框全部选中，取消全选后全部恢复。
- 浏览器控制台无 error/warning。
- 相关前端测试：9/9 通过。
- 前端生产构建：通过。

final result: passed
