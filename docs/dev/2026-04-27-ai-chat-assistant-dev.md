# DEV 文档：AI 学习助手 — 实施路线图

**关联 PRD**：`docs/prd/2026-04-27-ai-chat-assistant-prd.md`
**版本**：v1.0 | **日期**：2026-04-27

---

## 1. 技术架构

```
┌────────────────────────────────────────────────────────────┐
│  Frontend (React)                                          │
│                                                            │
│  App.jsx                                                   │
│   └─ ChatProvider (contexts/ChatContext.jsx)               │
│       ├─ 状态：isOpen, messages[], sessionId, context       │
│       ├─ 方法：toggle(), sendMessage(), setContext()        │
│       └─ FloatingChat (components/FloatingChat.jsx)        │
│           ├─ 悬浮按钮（右下角固定定位）                      │
│           ├─ 聊天面板（380×520px 弹窗）                     │
│           ├─ 消息列表（用户右对齐 / AI 左对齐 + 打字光标）    │
│           ├─ 上下文标签（当前题目/小测名）                   │
│           └─ 输入框 + 发送                                  │
│                                                            │
│  各学生页面                                                 │
│   ├─ ProblemDetail → setContext({type:'ai_problem', ...})  │
│   ├─ QuizPage      → setContext({type:'info_quiz', ...})   │
│   └─ StudentDashboard → 通用上下文或无上下文                │
└──────────────────────┬─────────────────────────────────────┘
                       │ POST /api/chat/send/ (SSE)
                       │ GET  /api/chat/sessions/
┌──────────────────────▼─────────────────────────────────────┐
│  Backend (Django)                                          │
│                                                            │
│  chat/views.py                                             │
│   ├─ ChatSendView (POST) — 核心：SSE 流式代理               │
│   ├─ ChatSessionListView (GET) — 会话列表                   │
│   ├─ ChatSessionDetailView (GET/DELETE) — 消息/删除         │
│                                                            │
│  chat/models.py                                            │
│   ├─ ChatSession (user, title, context_type, ...)          │
│   └─ ChatMessage (session, role, content, created_at)      │
│                       │                                     │
│                       ▼                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ MiniMax API 调用层（views.py 内）                    │   │
│  │                                                      │   │
│  │ Semaphore(3) ──→ OpenAI SDK (stream=True)            │   │
│  │                                                      │   │
│  │ 超限处理：                                            │   │
│  │  ├─ 获取 Semaphore（排队等待）                        │   │
│  │  ├─ 调用 MiniMax                                     │   │
│  │  ├─ 429 → sleep(1s) → 重试 → 3s → 5s（最多3次）     │   │
│  │  └─ 失败 → SSE error event                           │   │
│  └─────────────────────────────────────────────────────┘   │
│                       │                                     │
│                       ▼                                     │
│  MiniMax API (OpenAI 兼容)                                  │
│  Base: https://maas-api.ai-yuanjing.com/openapi/...        │
│  Model: minimax-m2.5                                       │
└────────────────────────────────────────────────────────────┘
```

### 1.1 SSE 数据流

```
1. 前端 POST /api/chat/send/
   Body: {message: "什么是变量？", session_id: "abc", context: {type: "ai_problem", ...}}

2. 后端 Django view:
   a. session_id 不存在 → 创建 ChatSession，生成标题（用户首条消息前20字）
   b. 保存 ChatMessage(role="user", content="什么是变量？")
   c. 构建 system prompt（注入 context 内容）
   d. 构建 messages 列表：[system_prompt, …历史消息, 最新用户消息]
   e. semaphore.acquire()  // 最多 3 路并发
   f. 调用 OpenAI SDK stream=True
   g. 以 StreamingHttpResponse 逐块返回 SSE

3. 前端接收 SSE 流：
   event: token
   data: {"content": "变"}

   event: token
   data: {"content": "量"}

   ...

   event: done
   data: {"session_id": "abc", "content": "变量是..."}

4. 流结束后，后端保存 ChatMessage(role="assistant", content=完整回复)
```

### 1.2 context 注入策略

根据 context.type 构建不同的 system prompt：

**ai_problem:**
```
你是 Python 学习助教。学生正在做以下编程题：
题目：{title}
描述：{description}

请帮助理解题目要求，引导解题思路，但不要直接给出完整代码答案。
```

**info_quiz:**
```
你是信息科技课助教。学生正在做小测：
小测：{title}
题数：{num_questions}

请帮助理解知识点，可以解释概念，但不要直接透露小测答案。
```

**无 context:**
```
你是 Python/信息科技学习助教。请用通俗易懂的方式回答学生问题。
```

---

## 2. 数据库设计（Django ORM）

### ChatSession

| 字段 | 类型 | 说明 |
|------|------|------|
| id | AutoField (PK) | |
| user | FK → users.CustomUser | 学生用户 |
| title | CharField(200) | 会话标题（取首条消息前20字） |
| context_type | CharField(50), nullable | 'ai_problem' / 'info_quiz' |
| context_id | CharField(100), nullable | problem_id 或 session_id |
| context_snapshot | JSONField, nullable | 冻结的 context 数据 |
| created_at | DateTimeField | auto_now_add |
| updated_at | DateTimeField | auto_now |

### ChatMessage

| 字段 | 类型 | 说明 |
|------|------|------|
| id | AutoField (PK) | |
| session | FK → ChatSession | |
| role | CharField(20) | 'user' / 'assistant' |
| content | TextField | 消息内容 |
| created_at | DateTimeField | auto_now_add |

---

## 3. API 契约

### 3.1 POST /api/chat/send/

**请求：**
```json
{
  "message": "什么是变量？",
  "session_id": "abc123",          // 可选，首次为空
  "context": {                      // 可选
    "type": "ai_problem",
    "id": "problem1",
    "title": "变量与赋值",
    "description": "请编写程序..."
  }
}
```

**响应（SSE 流）：**
```
Content-Type: text/event-stream

event: token
data: {"content": "变"}

event: token
data: {"content": "量"}

event: token
data: {"content": "是"}

...

event: done
data: {"session_id": "abc123", "title": "什么是变量？"}

event: error
data: {"error": "AI 服务繁忙，请稍后重试"}
```

### 3.2 GET /api/chat/sessions/

**响应：**
```json
{
  "sessions": [
    {
      "id": "abc123",
      "title": "什么是变量？",
      "context_type": "ai_problem",
      "updated_at": "2026-04-27T10:30:00Z",
      "message_count": 6
    }
  ]
}
```

### 3.3 GET /api/chat/sessions/<id>/messages/

**响应：**
```json
{
  "session": {"id": "abc123", "title": "什么是变量？"},
  "messages": [
    {"id": 1, "role": "user", "content": "什么是变量？", "created_at": "..."},
    {"id": 2, "role": "assistant", "content": "变量是...", "created_at": "..."}
  ]
}
```

### 3.4 DELETE /api/chat/sessions/<id>/

**响应：** `{"ok": true}`

---

## 4. 实施步骤

### Step 1: 后端 Django app 骨架 ✅ 已完成

**操作：**
- 新建 `backend/chat/__init__.py`
- 新建 `backend/chat/models.py` — ChatSession + ChatMessage
- 新建 `backend/chat/admin.py` — 注册两个 model
- 运行 `python manage.py makemigrations chat && migrate`
- 在 `backend/school_platform/settings.py` 添加：
  - `INSTALLED_APPS` 追加 `'chat'`
  - 新增 `MINIMAX_API_KEY`、`MINIMAX_API_BASE`、`MINIMAX_MODEL` 三项配置
- 在 `backend/school_platform/urls.py` 添加 `path('api/chat/', include('chat.urls'))`
- 更新 `requirements.txt`：添加 `openai>=1.0.0`

**验证：** `python manage.py makemigrations chat` 无报错，migrate 成功。

### Step 2: 后端 views.py — ChatSendView ✅ 已完成

**操作：**
- 新建 `backend/chat/views.py`
  - `ChatSendView(APIView)` — POST 方法
    - 解析 request body（message, session_id?, context?）
    - session_id 不存在 → 创建 ChatSession
    - 保存用户消息
    - 构建 system prompt（根据 context）
    - 拼接 messages 历史
    - Semaphore(3) 获取
    - 调用 OpenAI SDK 流式请求 MiniMax
    - `StreamingHttpResponse` 返回 SSE
    - 流结束后保存 assistant 消息
    - 更新 session.updated_at
  - `ChatSessionListView(APIView)` — GET
  - `ChatSessionDetailView(APIView)` — GET（消息）/ DELETE
- 新建 `backend/chat/urls.py`
  - `POST /api/chat/send/`
  - `GET /api/chat/sessions/`
  - `GET /api/chat/sessions/<id>/messages/`
  - `DELETE /api/chat/sessions/<id>/`
- 权限：`IsAuthenticated` + 角色检查（student only）

**验证：** curl 测试 send 端点，模拟发送消息 → 收到 SSE 流式回复。

### Step 3: 前端 API 层 ✅ 已完成

**操作：**
- 新建 `frontend/src/api/chat.js`
  - `sendChatMessage({message, sessionId, context, signal})` — 使用 fetch + ReadableStream 解析 SSE
  - `getChatSessions()` — 调用 GET 端点
  - `getChatMessages(sessionId)` — 调用 GET 端点
  - `deleteChatSession(sessionId)` — 调用 DELETE 端点

**验证：** 用 curl 或浏览器 devtools 检查返回格式。

### Step 4: 前端 ChatContext ✅ 已完成

**操作：**
- 新建 `frontend/src/contexts/ChatContext.jsx`
  - `ChatProvider` — 包裹子组件
    - 状态：`isOpen`, `messages[]`, `sessionId`, `context`, `inputText`, `isStreaming`, `error`
    - 方法：
      - `open()` / `close()` / `toggle()`
      - `setContext(ctx)` — 页面注册/清除上下文
      - `sendMessage(text)` — 调用 API，处理 SSE 流，追加消息
      - `newSession()` — 重置 sessionId 和 messages
  - `useChat()` — 自定义 hook
  - 导出 `ChatProvider`, `useChat`

**验证：** 编写上下文测试，验证初始状态。

### Step 5: 前端 FloatingChat 组件 ✅ 已完成

**操作：**
- 新建 `frontend/src/components/FloatingChat.jsx`
  - 悬浮按钮：`position: fixed; bottom: 24px; right: 24px`，圆形 48px
  - 面板：展开后 380×520px，底部滑入动画
  - 消息气泡：用户右对齐蓝色，AI 左对齐白色灰底
  - 打字光标：AI 最后一条消息末尾闪烁 `|`（CSS animation blink）
  - 输入：`textarea` + `onKeyDown`（Enter 发送，Shift+Enter 换行）
  - 上下文标签：蓝色 pill，显示 "📌 {title}"
  - 顶部栏：标题 + 新建按钮 + 关闭按钮
  - 状态处理：loading 动画、error 红色提示

**样式：** 追加到 `frontend/src/index.css` 末尾（~120 行）

**验证：** 纯 UI 测试：点击打开/关闭面板，输入文字，消息气泡样式。

### Step 6: 集成到 App.jsx ✅ 已完成

**操作：**
- 修改 `frontend/src/App.jsx`
  - 导入 `ChatProvider`, `FloatingChat`
  - 在学生路由的父级包裹 `ChatProvider`
  - 在 `ChatProvider` 内部渲染 `FloatingChat`

```jsx
// 伪代码示意
<AuthProvider>
  <Routes>
    {/* 学生路由 */}
    <Route element={<ChatProvider><Outlet /><FloatingChat /></ChatProvider>}>
      <Route path="/student/dashboard" element={<StudentDashboard />} />
      <Route path="/problem/:problemId" element={<ProblemDetail />} />
      <Route path="/student/quiz/:sessionId" element={<QuizPage />} />
      <Route path="/student/quiz-result/:sessionId" element={<QuizResult />} />
      <Route path="/course-select" element={<CourseSelect />} />
    </Route>
    {/* 老师路由不包含 ChatProvider */}
  </Routes>
</AuthProvider>
```

**验证：** 学生登录后确认右下角有悬浮按钮。

### Step 7: 页面注册上下文 ✅ 已完成

**修改文件：**

1. `ProblemDetail.jsx`:
   ```jsx
   import { useChat } from '../../contexts/ChatContext'
   // 加载题目成功后
   const chat = useChat()
   useEffect(() => {
     if (problem) {
       chat.setContext({type: 'ai_problem', id: problemId, title: problem.title, description: problem.description})
     }
     return () => chat.setContext(null)
   }, [problem])
   ```

2. `QuizPage.jsx`:
   ```jsx
   import { useChat } from '../contexts/ChatContext'  // 注意路径
   // 加载小测成功后
   const chat = useChat()
   useEffect(() => {
     if (quiz) {
       chat.setContext({type: 'info_quiz', id: sessionId, title: quiz.title, description: `${quiz.num_questions}题`})
     }
     return () => chat.setContext(null)
   }, [quiz])
   ```

3. `StudentDashboard.jsx`:
   ```jsx
   import { useChat } from '../../contexts/ChatContext'
   const chat = useChat()
   useEffect(() => {
     chat.setContext(null)  // dashboard 不设特定上下文
   }, [])
   ```

**验证：** 在题目页检查上下文标签显示，切换页面后标签变化。

### Step 8: 测试 ✅ 已完成

**新建文件：** `frontend/src/components/FloatingChat.test.jsx`

测试用例：
- 悬浮按钮渲染
- 点击按钮打开/关闭面板
- 输入框输入文字
- 按 Enter 触发 sendMessage
- 上下文标签显示/隐藏
- 打字光标闪烁

**运行：** `npx vitest run src/components/FloatingChat.test.jsx`

---

## 5. 关键文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `backend/chat/__init__.py` | |
| 新建 | `backend/chat/models.py` | ChatSession + ChatMessage |
| 新建 | `backend/chat/views.py` | SSE 流式端点 + 会话 CRUD |
| 新建 | `backend/chat/urls.py` | 4 条路由 |
| 新建 | `backend/chat/admin.py` | Django Admin 注册 |
| 修改 | `backend/school_platform/settings.py` | INSTALLED_APPS + MiniMax 配置 |
| 修改 | `backend/school_platform/urls.py` | include chat.urls |
| 修改 | `requirements.txt` | 添加 openai |
| 新建 | `frontend/src/api/chat.js` | SSE fetch 封装 |
| 新建 | `frontend/src/contexts/ChatContext.jsx` | 全局聊天状态 |
| 新建 | `frontend/src/components/FloatingChat.jsx` | 悬浮聊天 UI |
| 修改 | `frontend/src/App.jsx` | 包裹 ChatProvider |
| 修改 | `frontend/src/index.css` | 聊天组件样式 |
| 修改 | `frontend/src/pages/student/ai/ProblemDetail.jsx` | 注册 AI 题上下文 |
| 修改 | `frontend/src/pages/student/info/QuizPage.jsx` | 注册小测上下文 |
| 修改 | `frontend/src/pages/student/StudentDashboard.jsx` | 清除上下文 |

---

## 6. 验证方案

### 6.1 后端验证

```bash
# 1. 设置 API Key
export MINIMAX_API_KEY="your_key_here"

# 2. 启动 Django
cd backend && python manage.py runserver 8080

# 3. 先获取学生 token
curl -X POST http://localhost:8080/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"grade":"七年级","class_num":"1","student_number":"1","password":"123456"}'

# 4. 测试发送消息（SSE 流式）
curl -N -X POST http://localhost:8080/api/chat/send/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token <token>" \
  -d '{"message":"你好，Python中什么是变量？"}'
# 预期：逐步返回 event: token + data: {...}

# 5. 测试带 context 的发送
curl -N -X POST http://localhost:8080/api/chat/send/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token <token>" \
  -d '{"message":"这道题怎么做？","context":{"type":"ai_problem","id":"problem1","title":"变量与赋值","description":"编写一个程序，交换两个变量的值。"}}'

# 6. 测试获取会话列表
curl -H "Authorization: Token <token>" http://localhost:8080/api/chat/sessions/
```

### 6.2 前端验证

1. 启动前端：`cd frontend && npm run dev`
2. 学生登录，确认右下角出现悬浮聊天按钮
3. 点击按钮 → 面板展开
4. 发送消息 → 观察流式回复（逐字出现）
5. 进入 `/problem/1` 页面 → 上下文标签显示 "📌 变量与赋值"
6. 切换到 `/student/quiz/1` → 标签变化为小测名
7. 回到 dashboard → 标签消失
8. 点击新建对话 → 清空消息，新 session

### 6.3 测试用例

```bash
cd frontend && npx vitest run src/components/FloatingChat.test.jsx
```

预期全部通过。
