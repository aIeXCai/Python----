# 阶段 5 Step 2：公共入队 API 验证记录

记录日期：2026-09-03
状态：完成

## 1. 完成内容

- `POST /api/ai/run_code/` 改为只创建 `run` 任务并返回 HTTP 202。
- `POST /api/ai/submissions/` 在一个事务中创建不可变测试点快照、`grade` 任务和 `pending/score=NULL` 提交。
- Web 请求不再写入 `backend/submissions/*.py`，也不再调用本机运行或批改函数。
- `Idempotency-Key` 支持 UUID 校验、重试返回原任务，不同请求复用同一 key 返回 409。
- 每学生默认最多 1 个 running 和 2 个 queued 任务；代码、stdin、测试点数量和字节大小由服务端限制。
- 新增本人任务详情和活动任务恢复接口，不返回代码、隐藏测试点、限制快照或租约信息。
- 只允许学生角色创建和查询代码任务。
- 成绩列表和教师成绩查询排除 `score IS NULL` 的未完成提交。

## 2. 公共接口

- `POST /api/ai/run_code/`
- `POST /api/ai/submissions/`
- `GET /api/ai/executions/<task_id>/`
- `GET /api/ai/executions/active/?task_type=run`
- `GET /api/ai/executions/active/?task_type=grade&problem_id=<id>`

## 3. 自动验证

### SQLite

- `python manage.py check`：通过。
- `python manage.py makemigrations --check --dry-run`：`No changes detected`。
- `python manage.py migrate --check`：通过。
- Step 2 相关定向测试：123/123 通过。
- Django 全量：374 项通过，1 项跳过。

### MySQL 8.0

- 隔离实例版本：8.0.46，使用保留的本地测试库。
- `execution.tests` 及 run/submit 公共 API 定向测试：49/49 通过。
- 验证后 MySQL 已停止，`127.0.0.1:3308` 不监听。

## 4. 阶段边界

Step 2 只完成可持久入队和查询。Runner 尚未实现，因此任务会停留在 `queued`；前端异步轮询会在 Step 5 完成。在 Step 3–5 完成前，不将这个中间状态用于真实上课。

## 5. 下一步

进入 Step 3：实现 Runner HMAC 私有协议、公平 claim、续租、完成回传、过期恢复，以及 `ExecutionTask`/`Submission` 的原子状态更新。
