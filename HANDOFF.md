# HANDOFF

## 1. 定位

面向学校教师和学生的信息技术与 AI 编程教学平台，提供账号、题库、小测、在线编程、成绩统计和 AI 辅导功能。
本学期不投入正式教学，当前代码用于本地改造、验收及后续部署准备（`docs/2026-09-01-alicloud-deployment-roadmap.md:7`）。

## 2. 技术栈

| 层 | 选型 | 理由 |
| --- | --- | --- |
| 前端 | React 19、Vite 8、Monaco Editor | 单页教学界面与在线代码编辑（`frontend/package.json:6`） |
| 后端 | Django 5、Django REST Framework | 账号、课程和教学 API（`requirements.txt:2`） |
| 数据库 | MySQL；测试兼容 SQLite | 正式环境统一持久化教学数据（`backend/school_platform/settings.py:185`） |
| AI | OpenAI Python SDK | 调用第三方模型服务（`requirements.txt:8`） |
| 执行 | ExecutionTask、Runner 私有协议 | Web 只入队，不直接运行学生代码（`backend/school_platform/settings.py:58`） |

## 3. 结构速览

```text
Python-----1/
├── frontend/               # React 前端
├── backend/                # Django 服务、模型和迁移
├── docs/                   # PRD、DEV、验收与部署记录
└── scripts/、problems/     # 运维脚本与本地题目备份
```

## 4. 数据模型

| 领域 | 实体与关系 |
| --- | --- |
| 账号 | CustomUser 关联学生身份、教师管理年级及 PasswordSecurityAudit |
| AI 课程 | Problem 关联 ProblemAudience、Submission 和 ProblemManagementAudit |
| 代码执行 | Submission 一对一关联 ExecutionTask；RunnerNode 处理任务 |
| 信息课 | Unit 包含 Question；QuizSession 关联多次 QuizSubmission |
| AI 对话 | ChatSession 包含 ChatMessage |

## 5. 关键决策

- 先完成本地改造再部署，下学期前完成生产化和整班验证（`docs/2026-09-01-alicloud-deployment-roadmap.md:7`）。
- 生产架构采用 Nginx、React、Django、RDS MySQL 和独立 Runner，并使用同源 `/api`（`docs/2026-09-01-alicloud-deployment-roadmap.md:12`）。
- 学生密码只保存密文，同时保留受控查看、重置和审计能力，便于处理忘记密码（`backend/users/models.py:42`、`backend/users/models.py:151`）。
- 信息课小测允许重复作答，每次打乱试卷，教师端使用最近一次完成成绩（`docs/2026-09-01-alicloud-deployment-roadmap.md:95`）。
- 每道 AI Problem 独立供学生练习，并支持年级标签和全校/年级/班级发布范围（`ca2664a`、`backend/ai_courses/models.py:44`、`backend/ai_courses/models.py:266`）。

## 6. 启动 & 验证

安装：`pip install -r requirements.txt && cd frontend && npm install`。
启动：在项目根目录执行 `bash start_all.sh`（`start_all.sh:97`）。
测试：后端执行 `python manage.py test`；前端执行 `npm test -- --run`。
跑通标志：学生和教师都能登录；学生能看到课程并完成一次小测；教师端能查看题库和成绩。

## 7. 陷阱清单

- 不要提交 `.env`、真实密钥或数据库，因为它们包含敏感信息（`.gitignore:7`）。
- 不要把 Git 克隆当作完整数据迁移，因为学生账号、作答、成绩和聊天记录不在教学内容 fixture 中。
- 不要在生产环境使用 Django/Vite 开发服务器，因为它们不是生产服务进程（`start_all.sh:100`、`start_all.sh:107`）。
- 不要在 Django Web 进程运行学生代码，因为当前设计只允许入队给隔离 Runner（`backend/school_platform/settings.py:58`）。
- 不要正式开放代码执行，因为 Runner Controller 与 Docker 沙箱尚未完成（`docs/2026-09-01-alicloud-deployment-roadmap.md:113`）。

## 用户备注(skill 永不自动覆盖)
<!-- handoff:manual-zone -->
<!-- /handoff:manual-zone -->
