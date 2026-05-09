# AI 课在线 IDE — 产品需求文档

## 1. 背景与问题

当前 AI 课答题区域采用「上传 .py 档案」方式，学生在本地 IDE 编写代码后上传提交。这种方式存在以下问题：

- 学生无法确认代码是否正确，需反复上传测试
- 提交失败后修改成本高
- 文件管理繁琐，无法保留中间版本

引入在线 IDE 后，学生可实时编写、运行、调试代码，确认无误后再提交批改，降低试错成本。

---

## 2. 目标

在 `ProblemDetail.jsx` 中将文件上传区域替换为在线代码编辑器，功能：

- 代码编写区（语法高亮 + 自动缩进）
- **运行**按钮：交互式执行代码，支持 stdin 输入，10 秒超时
- **保存并提交**按钮：原有测试点批改逻辑

---

## 3. 用户故事

| 角色 | 场景 | 行为 |
|------|------|------|
| 学生 | 编写有 `input()` 的代码 | 点击运行 → 弹出输入框 → 输入内容 → 查看输出 |
| 学生 | 编写纯输出代码 | 点击运行 → 直接查看输出 |
| 学生 | 确认代码正确 | 点击保存并提交 → 查看批改结果 |
| 学生 | 代码死循环 | 运行超过 10 秒 → 自动终止 → 提示超时 |

---

## 4. 功能边界

### 4.1 代码编辑器

- **技术选型**: Monaco Editor（VS Code 同款，功能完整）
- **语言**: Python 语法高亮
- **功能**: 自动缩进、括号匹配、Tab/空格支持
- **主题**: 深色主题（与整体页面风格一致）
- **字号**: 14px
- **高度**: 400px（可调整）

### 4.2 运行功能

- **端点**: `POST /api/ai/run_code/`
- **请求体**:
  ```json
  {
    "code": "name = input()\nprint('Hello, ' + name)",
    "stdin": "张三"
  }
  ```
- **响应**:
  ```json
  {
    "output": "请输入姓名: Hello, 张三",
    "error": "",
    "execution_time": 0.23
  }
  ```
- **行为**:
  1. 点击「运行」→ 弹出 stdin 输入对话框
  2. 学生填写所有输入（多行用换行分隔）→ 确认
  3. 代码发送到后端，stdin 通过管道传入
  4. 后端 `subprocess.run(['python', '-c', code], input=stdin.encode(), timeout=10)`
  5. 返回 stdout/stderr/execution_time
  6. 输出显示在编辑器下方的输出区域
- **超时**: 10 秒，超时返回 `{error: "执行超时（10秒）"}`

### 4.3 保存并提交功能

- 复用现有 `POST /api/ai/submissions/` 端点
- 区别：现有接口从 FormData 取文件内容，改为同时支持纯文本 `code` 字段
  ```json
  {
    "problem_id": "p001",
    "code": "print('hello')"
  }
  ```
- 行为不变：测试点批改 → 返回 `{success, score, detail}`

### 4.4 模板代码（代码填空）

- **场景**: 部分题目难度较大，教师提供完整代码框架，挖去关键部分让学生填空
- **存储**: 题目文件夹下新增可选文件 `template.py`，存放预加载代码
- **约定**: 填空处用 `# ___` 注释标记或 `pass` 占位
- **行为**:
  - 有 `template.py` → 打开题目时 Monaco Editor 预填充模板内容
  - 无 `template.py` → 编辑器空白，学生从零开始（向后兼容）
- **重做按钮**: 位于「运行」和「保存并提交」之间，点击后：
  - 有模板代码 → 恢复编辑器内容为 `template_code`
  - 无模板代码 → 清空编辑器内容
- **数据流**: `sync_from_disk()` → `Problem.template_code` 字段 → `ProblemDetailSerializer` → 前端 `problem.template_code`

---

## 5. 后端改动

### 5.1 新增端点

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/ai/run_code/` | 运行代码（不落库） |

**视图** `backend/ai_courses/views.py`:

```python
class CodeRunView(APIView):
    """POST /api/ai/run_code/ — 运行学生代码（交互式）"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '')
        stdin = request.data.get('stdin', '')

        if not code:
            return Response({'error': '代码不能为空'}, status=400)

        try:
            result = run_code_interactive(code, stdin)
            return Response(result)
        except subprocess.TimeoutExpired:
            return Response({'error': '执行超时（10秒）'}, status=408)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
```

**执行函数** `backend/ai_courses/models.py` 或新工具函数:

```python
import subprocess

def run_code_interactive(code: str, stdin: str, timeout=10):
    try:
        result = subprocess.run(
            ['python', '-c', code],
            input=stdin.encode('utf-8'),
            capture_output=True,
            timeout=timeout,
        )
        return {
            'output': result.stdout.decode('utf-8', errors='replace'),
            'error': result.stderr.decode('utf-8', errors='replace'),
            'execution_time': 0,  # 可选：计算实际耗时
        }
    except subprocess.TimeoutExpired:
        raise
```

### 5.2 路由注册

`backend/ai_courses/urls.py` 添加:

```python
path('run_code/', views.CodeRunView.as_view()),
```

### 5.3 现有 SubmissionView 兼容

`SubmissionView.post()` 当前从 `request.FILES['code']` 取文件内容，需同时支持 `request.data['code']`（纯文本）:

```python
code = request.FILES.get('code') or request.data.get('code', '')
if hasattr(code, 'read'):
    code = code.read().decode('utf-8')
```

### 5.4 模型与序列化器 — 模板代码支持

**`Problem` 模型** 新增字段:

```python
template_code = models.TextField(blank=True, default='')
```

**`sync_from_disk()`** 读取逻辑追加:

```python
template_path = problem_dir / 'template.py'
if template_path.exists():
    problem.template_code = template_path.read_text(encoding='utf-8')
else:
    problem.template_code = ''
```

**`ProblemDetailSerializer`** fields 追加 `template_code`:

```python
fields = [..., 'template_code']
```

---

## 6. 前端改动

### 6.1 依赖

```bash
cd frontend
npm install @monaco-editor/react
```

### 6.2 ProblemDetail.jsx 改动

**移除**:
- `<input type="file">` + 文件上传 UI
- `selectedFile` state
- `submitByFile()` 函数

**新增**:
- Monaco Editor 组件（400px 高）
- `code` state（初始值取自 `problem.template_code`，无模板则为空字符串）
- `stdin` state（弹窗输入内容）
- `runOutput` state（运行结果展示）
- `running` state（运行中按钮置灰防抖）
- 重做按钮：有模板 → 恢复 `template_code`；无模板 → 清空 `code`

**UI 布局**:

```
┌──────────────────────────────────────────────────────┐
│ 题目描述 / 测试点                                     │
├──────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────┐ │
│ │  Monaco Editor (Python, 400px高)                  │ │
│ │  ...                                             │ │
│ └──────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────┤
│  [▶ 运行]  [🔄 重做]  [💾 保存并提交]               │
├──────────────────────────────────────────────────────┤
│  运行结果区域（stdout/stderr 输出）                  │
└──────────────────────────────────────────────────────┘
```

**运行弹窗逻辑**:
1. 点击「运行」→ 检测代码中是否含 `input()`
2. 若有 → 弹出 `<dialog>` 让用户填写 stdin（textarea，支持多行）
3. 若无 → 直接发送请求，不弹窗

**响应处理**:
- 运行成功：output 显示在输出区域，error 红色显示
- 运行超时/错误：error 显示在输出区域

### 6.3 API 层

`frontend/src/api/index.js` 新增:

```js
export const runCode = (code, stdin) => {
  const token = getToken()
  return fetch('http://localhost:8080/api/ai/run_code/', {
    method: 'POST',
    headers: {
      'Authorization': `Token ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ code, stdin }),
  }).then(r => r.json())
}
```

---

## 7. 非功能需求

| 项目 | 要求 |
|------|------|
| 执行超时 | 10 秒，超时强制终止 subprocess |
| 错误隔离 | 代码执行异常不能影响主进程 |
| 编码处理 | stdin/stdout/stderr 统一使用 UTF-8 |
| 前端兼容性 | 支持 Chrome/Edge/Safari 最新版本 |
| 向后兼容 | 保存并提交功能保持原有行为 |
| 前端防抖 | 运行按钮点击后置灰，收到响应才恢复，防止快速连点 |
| 后端限流 | `run_code` 端点每用户 3 次/秒，使用 DRF Throttle |

---

## 8. 验证方案

1. **纯输出代码** — `print("hello")` → 运行 → 输出 "hello"
2. **input 代码** — 弹窗输入，stdin 传入 → 正确输出
3. **死循环** — `while True: pass` → 10 秒后返回超时错误
4. **stderr** — `print(undeclared_var)` → 运行 → error 区域显示 NameError
5. **保存并提交** — 代码正确 → 返回 success: true, score: 100
6. **文件上传兼容** — 旧文件上传方式仍然有效（向后兼容）
7. **模板预加载** — 有 `template.py` 的题目打开后编辑器显示模板内容；无模板题目为空

---

## 9. 关键文件清单

| 操作 | 文件 |
|------|------|
| 新增 | `backend/ai_courses/utils.py`（run_code_interactive 函数） |
| 修改 | `backend/ai_courses/views.py`（新增 CodeRunView + 兼容 SubmissionView） |
| 修改 | `backend/ai_courses/urls.py`（路由注册） |
| 修改 | `backend/ai_courses/models.py`（Problem 模型加 template_code 字段 + sync_from_disk 读取 template.py） |
| 修改 | `backend/ai_courses/serializers.py`（ProblemDetailSerializer 加 template_code） |
| 新增 | `frontend/src/api/runCode.js`（或合并到 index.js） |
| 修改 | `frontend/src/pages/student/ai/ProblemDetail.jsx`（IDE + 运行 + 提交） |
| 修改 | `frontend/package.json`（添加 @monaco-editor/react） |
| 修改 | `docs/prd/YYYY-MM-DD-ai-course-online-ide-prd.md`（本文档） |

---

## 10. 成功指标

- [ ] 学生可在 IDE 中编写 Python 代码并实时运行
- [ ] stdin 输入弹窗正常工作
- [ ] 10 秒超时正确终止
- [ ] 保存并提交结果与原文件上传行为一致
- [ ] 页面无明显性能下降
- [ ] 有模板代码的题目编辑器预填充，无模板的题目编辑器空白