## 学生管理模块 — 测试说明 (tests/StudentModule)

本目录包含对学生管理功能的单元测试、集成测试与前端自动化测试（Selenium）。本文档说明每个测试文件的用途、如何在本地运行测试、常见问题排查与两种推荐的测试运行方式。

## 目录与文件简介
- `test_backend.py` — 后端完整功能测试（用户注册/查询/修改/删除、认证、session、性能与集成流程）。
- `test_frontend.py` — 前端/UI 自动化测试（依赖 Chrome + ChromeDriver + selenium）。
- `test_data_manager.py` — 辅助脚本：用于创建/查看/清理测试数据（交互式）。
- `test_student_number.py` — 学号字段（student_number）相关的单元测试。
- `run_tests.py` — 统一测试运行器：先用 `unittest discovery` 运行后端测试，再运行可选的 `test_backend.py` 脚本，最后尝试运行前端测试（当环境可用时）。

## 快速开始（推荐）

1) 在项目根目录下创建并激活 Python 虚拟环境，安装依赖：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # 如果仓库有 requirements.txt
pip install selenium            # 仅当前端测试需要
```

2) 运行所有测试（包含后端与前端，前端会在缺少环境时跳过）：

```bash
python tests/StudentModule/run_tests.py
```

3) 仅运行后端单元测试（更快）：

```bash
python -m unittest discover -v -s tests/StudentModule -p 'test_*.py'
```

4) 仅运行前端某个用例（需要 Chrome + ChromeDriver）：

```bash
python -m unittest tests.StudentModule.test_frontend.TestStudentManagementFrontend.test_04_search_functionality -v
```

## 关于前端测试与数据库一致性（重要）

前端测试以子进程方式启动 `server.py`，子进程默认读取项目根的 `users.db`。测试框架中会为每次前端测试创建临时数据库并注入测试数据，然后需要确保子进程能够读取到相同的 DB。当前仓库提供两种常见做法：

- 方案 A（当前测试脚本采用）：在测试启动子进程前把临时 DB 覆盖到项目根的 `users.db`，测试结束后还原或删除该文件。优点：实现简单、兼容现有 `server.py`；缺点：会短暂修改项目文件。
- 方案 B（推荐长期方案）：修改 `server.py` 支持通过环境变量或命令行参数指定 DB 路径（例如 `DB_FILE=/path/to/tmp.db python server.py`），测试以该环境变量启动子进程。优点：不修改项目文件、更加明确和安全；缺点：需要在 `server.py` 中做小修改。

如果你希望我把方案 B 实现为默认行为，我可以把 `server.py` 增加对 `DB_FILE` 环境变量的优雅支持，并更新测试启动子进程的代码以传入该环境变量。

## 常见问题与排查步骤

- 问：启动前端测试时报 Timeout 或找不到元素？
	- 排查：先看 server 日志（测试运行时会在控制台打印），确认 `/admin/students` 页面返回 200 并包含学生行。若 `total_students` 为 0，说明子进程未读取到测试数据（见上面的 DB 一致性部分）。

- 问：Chrome/ChromeDriver 报错？
	- 排查：确保 Chrome 已安装且 ChromeDriver 与 Chrome 版本匹配；确保 `selenium` 已安装且可从当前 Python 环境导入。

- 问：端口占用导致服务器无法启动？
	- 排查：检查 8000 端口是否被占用：

```bash
lsof -i :8000
```

	- 若被占用，可 kill 对应 PID，或临时修改测试里的端口（`server.py` 中 PORT 变量）。

## CI 与自动化建议

- 在 CI 中运行前端测试之前，请保证运行环境包含 headless Chrome 或使用 `selenium` + `chromedriver` 服务（例如 GitHub Actions 的 windows-latest/ubuntu-latest 可配合 actions/setup-chromedriver）。
- 优先在 CI 中采用方案 B（通过 env 指定 DB 路径），避免修改仓库文件。

## 贡献与扩展

- 若需要新增用例，请遵循现有 `unittest` 风格并把文件命名为 `test_*.py`，放在 `tests/StudentModule` 下，这样 `run_tests.py` 会自动发现并执行。
- 如果想把前端测试改成更轻量的端到端（如 Playwright），我可以提供迁移建议和示例。

## 联系/作者备注

此测试套件由仓库维护者与自动化脚本共同维护。如遇无法解析的问题，可把完整运行输出贴到 issue 或直接联系维护者。欢迎改进测试覆盖与稳定性。
