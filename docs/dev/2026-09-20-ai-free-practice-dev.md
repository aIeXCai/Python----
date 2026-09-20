# AI 课学生端“自由练习”实施路线图

对应 PRD：`docs/prd/2026-09-20-ai-free-practice-prd.md`

状态：✅ 全部完成

## 1. 现状与可复用能力

### 学生端入口

- `frontend/src/pages/student/StudentDashboard.jsx` 维护 AI 课的 `aiSection` 状态，现有 `quizzes` 与 `practice` 两个 Tab。
- `frontend/src/index.css` 已定义 `.ai-dashboard-tabs`、`.ai-dashboard-panel` 以及通用 IDE 弹窗样式。
- 学生端统一由 `ChatProvider` 和 `FloatingChat` 包裹，因此自由练习组件可直接通过 `useChat()` 注册页面上下文。

### 代码执行

- `frontend/src/api/index.js` 已提供 `runCode(code, stdin)` 与 `pollExecutionTask(taskId, options)`。
- `POST /api/ai/run_code/` 已支持 `code`、`stdin`、幂等键、学生权限、限流、大小限制和隔离执行。
- `ProblemDetail.jsx` 已验证 `input()` 检测、输入弹窗、异步运行与结果展示流程。

### 小 P 上下文

- `ChatContext` 使用 `contextRef`，发送消息时会读取当前最新上下文，不受 React 闭包中的旧值影响。
- `backend/chat/views.py::_build_system_prompt()` 已按上下文类型构建不同提示。
- `ai_quiz_programming` 已证明代码可作为上下文传递，并在后端限制为 20,000 字符。

## 2. 技术架构

```text
StudentDashboard
  ├─ AI Tab：我的小测
  ├─ AI Tab：题库练习
  └─ AI Tab：自由练习
       └─ FreePracticeWorkspace
            ├─ Monaco Editor
            ├─ input() 输入弹窗
            ├─ runCode(code, stdin)
            ├─ pollExecutionTask(taskId)
            ├─ 运行结果
            └─ ChatContext.setContext({ type, title, code })

ChatContext.sendMessage
  └─ POST /api/chat/send/
       └─ _build_system_prompt(ai_free_practice)
```

自由练习只新增前端工作区和聊天提示适配，不新增执行 API、数据库模型或 runner 协议。

## 3. 组件设计

新增 `frontend/src/pages/student/ai/FreePracticeWorkspace.jsx`，职责如下：

- 保存当前代码、运行状态、任务阶段、结果、输入弹窗状态和本次标准输入。
- 渲染 Monaco Editor、运行按钮、运行结果与条件弹窗。
- 调用现有 `runCode` 和 `pollExecutionTask`。
- 使用 `AbortController` 在卸载时取消轮询。
- 组件挂载或代码变化时注册 `ai_free_practice` 聊天上下文，卸载时清理上下文。

组件不负责：

- Dashboard Tab 导航。
- 代码持久化或评分。
- 新建聊天会话。
- 后端代码执行实现。

## 4. 状态与执行流程

### 前端状态

```text
code              当前编辑器代码
isRunning         是否正在排队或执行
taskStatus        queueing | queued | running | 空
result            { output, error, status } | null
stdinDialogOpen   输入弹窗是否打开
stdinValue        当前弹窗输入内容
```

### 点击运行

1. 空代码时按钮保持禁用。
2. 若检测到 `input(`，打开弹窗并结束本次点击流程。
3. 无输入调用时，以空 `stdin` 执行。
4. 弹窗确认时，以弹窗内容作为 `stdin` 执行，并立即清空临时输入。
5. 调用 `runCode` 创建任务。
6. 若接口返回兼容性同步结果，直接标准化并展示。
7. 若返回 `task_id`，调用 `pollExecutionTask`，通过 `onUpdate` 更新排队/运行状态。
8. 最终统一映射 `output`、`error`、`status` 后展示。
9. 异常或结束时恢复运行按钮。

### 输入检测

本阶段与现有题目页保持一致，使用代码中是否包含 `input(` 作为触发条件。该方案不会执行学生代码，也不会引入 Python 解析器；其已知边界是注释或字符串中的 `input(` 也可能触发弹窗，但不会产生安全问题。

## 5. 小 P 上下文设计

### 前端上下文

```js
{
  type: 'ai_free_practice',
  title: '自由练习',
  code,
}
```

`FreePracticeWorkspace` 通过 effect 在每次 `code` 变化后调用 `chat.setContext()`。由于 `ChatContext` 同时更新 `contextRef`，学生点击发送时获取的是最近一次渲染的代码。

组件卸载时调用 `chat.setContext(null)`。Dashboard 只在 `aiSection === 'free-practice'` 时挂载组件，因此切换 Tab 即可完成上下文清理。

### 后端提示

在 `backend/chat/views.py::_build_system_prompt()` 增加 `ai_free_practice` 分支：

- 展示“学生当前自由练习代码”。
- 要求优先解释学生代码的行为、定位最关键问题、给出渐进提示。
- 沿用基础人设中“不直接给完整代码答案”的限制。

在 `ChatSendView.post()` 中对自由练习客户端上下文进行规范化：

- 只保留固定 `type`、固定 `title` 和字符串化后的 `code`。
- `code` 截断至 20,000 字符。
- 不接受客户端注入自由练习描述或系统提示字段。

如果学生正处于正式 AI 小测进行中，现有服务端防绕过逻辑继续优先执行，自由练习上下文不能绕过小测期间的助手限制。

## 6. 样式设计

在 `frontend/src/index.css` 增加独立的 `.free-practice-*` 样式：

- 工作区白色卡片和单栏布局。
- 编辑器固定合理高度，窄屏时降低高度。
- 操作区只保留运行按钮。
- 输出区使用深色等宽 `pre`，错误信息使用醒目但不过度刺激的颜色。
- 弹窗直接复用 `.ide-overlay`、`.ide-dialog`、`.ide-dialog-input`、`.ide-dialog-actions` 和 `.ide-btn-*`。
- 第三个 Tab 在窄屏下继续等宽排列；必要时允许文字不换行或横向滚动，避免标签拥挤。

## 7. 实施步骤

### Step 1：新增自由练习工作区组件 ✅ 已完成

状态：✅ 已完成

- 创建 `FreePracticeWorkspace.jsx`。
- 完成 Monaco 编辑、运行、异步轮询、结果展示、输入弹窗和卸载清理。
- 注册并实时更新 `ai_free_practice` 聊天上下文。

阶段验证：运行新增组件单元测试，确认普通运行、输入弹窗、取消、结果和上下文更新。

验证结果：`FreePracticeWorkspace.test.jsx` 共 8 项测试通过；组件与测试文件的 ESLint 检查通过。

### Step 2：接入学生 Dashboard Tab 与样式 ✅ 已完成

状态：✅ 已完成

- 在 AI 课 Tab 中增加“自由练习”。
- 仅在选中时挂载工作区。
- 增加对应 `role="tabpanel"`、`aria-controls` 和标签关联。
- 增加响应式工作区样式。

阶段验证：运行 Dashboard 测试，确认三个 Tab 互斥展示，信息科技课不出现自由练习。

验证结果：Dashboard 与自由练习组件共 22 项测试通过；生产构建通过。ESLint 无错误，保留 `StudentDashboard.jsx` 既有的 4 条 Hook 警告。

### Step 3：接入小 P 后端上下文 ✅ 已完成

状态：✅ 已完成

- 新增 `ai_free_practice` 系统提示分支。
- 在聊天入口规范化并截断自由练习代码上下文。
- 更新悬浮助手上下文徽标，使其显示“自由练习”。

阶段验证：运行聊天后端和 FloatingChat 测试，确认提示包含最新代码、超长代码被截断、上下文徽标正确且无法绕过小测限制。

验证结果：FloatingChat 与自由练习组件共 30 项前端测试通过，相关 ESLint 检查通过；后端 `chat.tests` 共 7 项测试通过，Django system check 无问题。

### Step 4：完整回归与构建验证 ✅ 已完成

状态：✅ 已完成

- 运行自由练习与 Dashboard 前端定向测试。
- 运行 ChatContext、FloatingChat、ProblemDetail 和 API 前端回归测试。
- 运行后端聊天与代码执行定向测试。
- 运行前端生产构建。
- 检查 `git diff`，确认无数据库迁移、无无关文件变更。

阶段验证：汇总命令、通过数量及任何既有失败。

验证结果：

- 前端完整 Vitest：33 个测试文件通过，320 项通过，2 项跳过。
- 前端生产构建：通过；仅保留既有 Monaco 大体积 chunk 提示。
- 后端聊天与代码执行：29 项通过，Django system check 无问题。
- 数据库迁移检查：`No changes detected`。
- 完整 ESLint：0 错误、33 条既有警告；本次新增和直接修改的核心文件定向 ESLint 通过。
- `git diff --check`：通过，无构建产物或数据库文件进入变更集。

## 8. 关键文件清单

### 新增

- `frontend/src/pages/student/ai/FreePracticeWorkspace.jsx`
- `frontend/src/pages/student/ai/FreePracticeWorkspace.test.jsx`
- `docs/dev/2026-09-20-ai-free-practice-dev.md`

### 修改

- `frontend/src/pages/student/StudentDashboard.jsx`
- `frontend/src/pages/student/StudentDashboard.test.jsx`
- `frontend/src/components/FloatingChat.jsx`
- `frontend/src/components/FloatingChat.test.jsx`
- `frontend/src/index.css`
- `backend/chat/views.py`
- `backend/chat/tests.py`

### 复用但预计不修改

- `frontend/src/api/index.js`
- `frontend/src/contexts/ChatContext.jsx`
- `backend/ai_courses/views.py`
- `backend/execution/services.py`
- runner 相关文件

## 9. 测试方案

### 前端组件测试

- 初始只显示编辑器和运行相关界面，不出现题目、提交或评分内容。
- 空代码禁用运行。
- 普通代码直接调用 `runCode(code, '')`。
- 含 `input()` 的代码先弹窗，填写后调用 `runCode(code, stdin)`。
- 取消输入不运行。
- 异步任务正确轮询并展示输出、无输出与错误。
- 运行中禁用重复点击。
- 编辑代码后 `setContext` 收到最新代码。
- 卸载组件后上下文被清空，轮询被取消。

### Dashboard 测试

- AI 课展示三个 Tab，默认仍选中“我的小测”。
- 三个面板互斥展示。
- 切换离开自由练习后其上下文通过组件卸载清理。
- 信息科技课不展示自由练习 Tab。

### 小 P 测试

- `_build_system_prompt()` 对自由练习包含当前代码和专用辅导规则。
- Chat API 保存的是规范化后的自由练习上下文。
- 超过 20,000 字符的代码被截断。
- 活跃正式 AI 小测仍拒绝自由练习上下文。
- FloatingChat 显示“自由练习”徽标。

### 回归命令

```bash
cd frontend
npm test -- src/pages/student/ai/FreePracticeWorkspace.test.jsx src/pages/student/StudentDashboard.test.jsx src/components/FloatingChat.test.jsx src/contexts/ChatContext.test.jsx src/pages/student/ai/ProblemDetail.test.jsx src/api/index.test.js
npm run build

cd ../backend
python manage.py test chat.tests ai_courses.tests.test_code_run
```

如定向测试通过，再视耗时运行完整前端 Vitest 与相关后端测试集。

## 10. 风险与处理

- `input()` 静态检测可能误判注释或字符串：与现有行为保持一致，误判只会多显示一次可取消弹窗。
- 编辑器每次输入都更新 React 状态与聊天上下文：上下文仅保存本地对象，不触发网络请求，性能开销可控。
- 学生快速切换 Tab 时异步任务仍在后端执行：前端取消轮询和状态更新，但不强制取消已入队任务，符合现有执行模型。
- 超长代码增加聊天成本：后端固定截断 20,000 字符，不信任客户端长度控制。
- 正式小测期间潜在绕过：保留并测试后端 `active_ai_attempts` 防护，自由练习类型不会成为例外。
