# 阶段 5 Step 1：任务模型与 Migration 验证记录

记录日期：2026-09-03
状态：完成

## 1. 完成内容

- 新增 `execution` Django app。
- 新增持久化 `ExecutionTask`，包括任务类型、状态、代码/测试快照、限制、幂等键、队列时间、租约、有限结果和得分字段。
- 新增 `RunnerNode` 健康元数据模型，不存储服务密钥。
- 增加每用户幂等唯一约束、得分范围约束及队列/用户/租约索引。
- `Submission` 新增一对一任务关联，并允许 pending/running 阶段使用空分数。
- Django Admin 对任务与 Runner 节点只读，状态只能由后续领域服务修改。
- 新增 6 项模型、约束、关联和数据保留测试。

## 2. Migration

- `execution.0001_initial`
- `ai_courses.0004_submission_execution_task`
- `makemigrations --check --dry-run`：No changes detected。
- `migrate --check`：通过。

## 3. SQLite 验证

- 两项 migration 应用成功。
- 旧 Submission：9 条，迁移后仍为 9 条。
- 旧空分数：0 条。
- 新 ExecutionTask：0 条；RunnerNode：0 条。
- `PRAGMA integrity_check=ok`。
- 外键违规：0。
- 模型及既有 AI 模型定向测试：41/41 通过。
- Django 全量：358 项通过，1 项跳过。

## 4. MySQL 8.0 验证

- 隔离服务版本：8.0.46。
- 两项 migration 应用成功，同时补齐阶段4的 `info_tech.0007`。
- 旧 Submission：9 条，迁移后仍为 9 条；空分数 0。
- 新 ExecutionTask 与 RunnerNode 均为空。
- `execution.tests`：6/6 通过。
- 验证后 MySQL 已停止，`127.0.0.1:3308` 不监听。

MySQL 全量回归和并发 `claim` 锁验证将在 Step 3/Step 7 完成。

## 5. 下一步

进入 Step 2：实现测试点快照、幂等入队、每用户任务上限、HTTP 202 创建接口、本人任务查询与活动任务恢复。Step 2 仍不需要 Docker。
