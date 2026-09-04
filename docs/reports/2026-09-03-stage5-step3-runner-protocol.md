# 阶段 5 Step 3：Runner 私有协议与队列状态机验证记录

记录日期：2026-09-03
状态：完成

## 1. 完成内容

- 新增 Runner HMAC-SHA256 鉴权，签名覆盖 HTTP 方法、完整路径、时间戳、请求 UUID 和 body SHA-256。
- 拒绝缺失、错误、过期签名和协议版本不匹配的请求。
- 新增持久化 `RunnerRequestReceipt` 防重放记录和 migration；claim 重放不会领取第二个任务。
- 防重放记录不保存 claim 返回的明文租约；数据库只保存租约 SHA-256。
- Runner 必须先上报有效心跳，只有 online、未过期且未超容量的节点可以 claim。
- claim 按 `priority, queued_at, id` 领取，排除已有 running 任务的学生，MySQL 使用 `select_for_update(skip_locked=True)`。
- 实现租约续期、租约所有者/令牌/过期检查，迟到或伪造结果不能覆盖任务。
- 实现结果状态、得分、输出、耗时和测试点数量校验；超限或矛盾结果整体拒绝。
- 评测结果中的正确答案只从 Web 保存的测试快照生成，不信任 Runner 回传的 expected output。
- `ExecutionTask` 和 `Submission` 在同一事务中更新；系统错误保持 `score=NULL`，不伪造 0 分。
- 实现排队过期取消、第一次租约中断重新入队、第二次中断转系统错误，并增加 `recover_execution_tasks` 管理命令。

## 2. 私有接口

- `POST /internal/runner/v1/tasks/claim`
- `POST /internal/runner/v1/tasks/<id>/heartbeat`
- `POST /internal/runner/v1/tasks/<id>/complete`
- `POST /internal/runner/v1/nodes/heartbeat`

这些接口由 HMAC 保护；阿里云部署时仍必须在 Nginx 和安全组层禁止公网访问。

## 3. Migration 与数据

- 新增 `execution.0002_runnerrequestreceipt`。
- SQLite 和 MySQL 8.0.46 migration 均已成功应用。
- 两个环境中原有 Submission 均为 9 条，空分数 0 条，没有因 migration 丢失历史成绩。
- SQLite `integrity_check=ok`，外键违规 0。

## 4. 自动验证

### SQLite

- `execution.tests`：39 项通过，2 项 MySQL 专用并发测试跳过。
- Django 全量：共运行 393 项，390 项通过，3 项跳过（其中 2 项为 MySQL 专用）。
- `makemigrations --check --dry-run`：无未生成 migration。
- `manage.py check`、`migrate --check`、`git diff --check`：通过。

### MySQL 8.0

- `execution.tests`：41/41 通过。
- 两项真实并发 claim 验证通过：不重复领取；同一学生最多一个 running 任务。
- 验证后 MySQL 已停止，`127.0.0.1:3308` 不监听。

## 5. 阶段边界与下一步

Step 3 只实现 Web 侧协议、队列和结果落库。独立 Runner Controller 和真实非 root Docker 沙箱将在 Step 4 实现。

当前机器缺少 Docker CLI/运行时，因此进入 Step 4 前需先安装并验证 Docker。没有真实沙箱验收之前，不启用这套代码执行链路用于上课。
