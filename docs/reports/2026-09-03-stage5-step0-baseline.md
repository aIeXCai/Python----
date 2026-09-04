# 阶段 5 Step 0：基线、备份与安全护栏记录

记录日期：2026-09-03
状态：完成

## 1. 数据备份

### SQLite

- 目录：`backend/migration_artifacts/stage5-pre-runner-20260903/`
- `integrity_check=ok`
- 外键违规：0
- 备份前后源文件 SHA-256：一致
- 备份大小：372736 bytes
- 备份 SHA-256：`e5ae1ae6e7049bd4b0599c66744514c4eb330d88c45182696ce11865cc65d751`
- 目录权限：0700；文件权限：0600

### 隔离 MySQL 8.0

- 服务端版本：8.0.46
- 目录：`backend/migration_artifacts/stage5-mysql-pre-runner-20260903/`
- dump 大小：63406 bytes
- dump SHA-256：`40337a147f20439de8ed8a431ab470cf8dc003c4f7c4041c1867ab5f22355955`
- 迁移前业务库表数：21
- 目录权限：0700；文件权限：0600
- 完成后 `127.0.0.1:3308` 监听：false

以上 artifacts 均受 Git ignore 保护，不提交仓库。

## 2. 安全护栏

- 新增 `CODE_EXECUTION_ENABLED` 总开关。
- 开关关闭时，自由运行和自动评测均在写文件或执行代码前返回 503。
- 新增不可由环境变量覆盖的 `LEGACY_CODE_EXECUTION_ALLOWED`：仅 development/test 为 true，production 恒为 false。
- 即使生产环境显式开启总开关，也不能调用旧本机执行函数。
- 该护栏是阶段 5 过渡措施；Runner 接管后将彻底删除旧本机执行实现。

定向测试：`ai_courses.tests_code_run` 30/30 通过，其中包含关闭总开关和生产禁用本机回退测试。

## 3. 自动化基线

- Django SQLite 全量：352 项通过，1 项跳过。
- Vitest 单独复跑 `ProblemDetail.test.jsx`：26/26 通过。
- Vitest 顺序全量：23 个文件通过；268 项通过，2 项跳过。
- Vite production build：成功。
- ESLint：0 errors，42 warnings（既有警告，本步骤未新增前端代码）。

第一次并行执行 Vitest 与 Vite build 时，`ProblemDetail` 的 ChatContext 注册断言发生一次时序失败；该文件单独复跑及随后顺序全量均通过。本阶段后续基线采用顺序执行，避免构建竞争影响测试时序。

## 4. 环境前置条件

- 当前系统找不到 `docker` 命令。
- Step 1–3 的数据库模型、公共 API、私有协议和队列逻辑可继续开发。
- 进入 Step 4 Runner 真实沙箱前，必须安装并验证 Docker Desktop 或等价 Linux Docker Engine；真实安全测试不能用 mock 替代。
