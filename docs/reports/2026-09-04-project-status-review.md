# 项目状态复核报告

日期：2026-09-04
目的：核对 `docs/2026-09-01-alicloud-deployment-roadmap.md` 的标记状态与代码库实际情况是否一致，并清理过时条目。

## 1. 复核结论

路线图整体可信，但阶段 9 存在三处过时条目（记录的是阶段 5/6 之前的旧状态），阶段 5 的剩余项此前未标注阻塞原因。已在本轮修正。

## 2. 实测验证结果

在本机重新执行，不依赖历史报告：

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| Django 全量测试（SQLite） | `python manage.py test --noinput` | 399 通过 / 3 跳过 / 0 失败，67.9s |
| Django 系统检查 | 同上附带执行 | 0 问题 |
| 前端单元测试 | `npm test` | 24 文件 / 277 通过 / 2 跳过 / 0 失败 |
| ESLint | `npm run lint` | 0 error / 35 warning |
| Vite 生产构建 | `npx vite build --outDir <临时目录>` | 通过，2976 模块 |

构建验证输出到临时目录，未覆盖 `frontend/dist`。

## 3. 关键代码事实抽查

| 抽查项 | 结果 | 对应阶段 |
| --- | --- | --- |
| `frontend/src` 中硬编码 `localhost:8080` | 0 处 | 阶段 1 |
| 业务代码中 `plain_password` | 仅存在于历史 migration 文件与测试，模型字段已由 `0007_remove_plain_password` 移除 | 阶段 3 |
| Django 业务代码中的 `subprocess` / `Popen` / `os.system` | 0 处，另有护栏测试 `tests_code_run.py` 扫描 | 阶段 5 Step 6 |
| 测试文件数量 | 24 个（路线图原记 21 个） | 阶段 9 |

## 4. 环境事实

| 项目 | 状态 |
| --- | --- |
| 后端解释器 | `/Users/caijinbin/.workbuddy/binaries/python/envs/default/bin/python`，Django 5.2.15 |
| 前端运行时 | 隔离 Node 22.22.2，Vite 8.0.9 |
| MySQL | Homebrew `mysql@8.0` 已安装，当前未启动；阶段 2–6 演练使用 `127.0.0.1:3308` |
| Docker | 未安装，OrbStack 等替代也未安装 |
| `mysqlclient` | 本机默认 Python 环境未安装，MySQL 相关测试需先解决此依赖 |

## 5. 阻塞项

1. **阶段 5 Step 4（Runner Docker 沙箱）阻塞**：本机无 Docker，无法实施非 root 隔离、资源限制、只读根文件系统，也无法做恶意代码实测。阶段 5 剩余 6 项全部依赖此项。
2. **MySQL 回归当前不可执行**：`mysqlclient` 与本地 MySQL 实例均未就绪。阶段 2–6 的 MySQL 结论来自 2026-09-01 至 09-04 的历史演练，尚未在本轮复核中重跑。
3. **阶段 8 Runner Dockerfile 与阶段 10 部署联调**：同样依赖 Docker。

## 6. 需要用户决策的事项

| 编号 | 事项 | 建议 |
| --- | --- | --- |
| D-01 | 阶段 0–6 共 138 项改动（64 新增 / 73 修改 / 1 删除）尚未提交，最后一次提交停留在 2026-05-09 | 按阶段分批提交，先建立基线，再做阶段 7 |
| D-02 | `backend/submissions/` 残留 367 个历史文件（268 个 `.py`，约 1.4 MB），Step 6 明确未删 | 确认后单独清理，不并入其他阶段 |
| D-03 | `backend/.env` 含真实第三方模型 API Key，已被 `.gitignore` 排除 | 保持排除状态；上线前按阶段 8 统一走环境变量注入 |
| D-04 | ESLint 35 项 `react-hooks/exhaustive-deps` 警告 | 已记入阶段 9；不影响构建，可延后 |
| D-05 | 是否安装 Docker 以解除阶段 5 阻塞 | 由用户决定，属于独立任务 |

## 7. 建议的推进顺序

1. 用户完成阶段 6 手工验收（`docs/deployment/stage-6-manual-acceptance.md`）。
2. 提交阶段 0–6 改动，建立版本基线（D-01）。
3. 编写阶段 7「AI 辅导与未成年人数据治理」PRD —— 不依赖 Docker。
4. 阶段 7 确认后实施；同步处理 D-02 历史文件清理。
5. Docker 就绪后再回到阶段 5 Step 4，完成 Runner 沙箱与阶段 5 整体验收。
6. 之后进入阶段 8（生产构建与部署文件）。

## 8. 本轮改动的文件

- `docs/2026-09-01-alicloud-deployment-roadmap.md`：修正阶段 5、阶段 9 条目；新增「五、本机环境事实」；更新「四、当前正在推进的任务」。
- `docs/dev/2026-09-03-student-code-runner-isolation-dev.md`：补齐 Step 0–3 的完成标记，Step 7 标注为依赖 Step 4。
- `docs/dev/2026-09-04-data-normalization-business-permissions-dev.md`：补齐 Step 0–6 的完成标记。
- `docs/reports/2026-09-04-project-status-review.md`：本报告。
