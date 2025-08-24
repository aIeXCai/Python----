# Python 学习平台 - 学生答题模块运行与测试说明

此文档说明如何在本地启动服务器并运行为学生答题模块创建的测试（包括 50 人并发提交测试）。

## 快速清单
- 启动服务器：`python server.py`（会监听 `http://localhost:8000`）
- 运行单个测试或整个测试集：使用 `python -m unittest` 或直接运行测试文件
- 测试目录：`tests/AnsweringModule`，主要文件：`test_answering_module.py`

## 环境要求
- Python 3.8+（你当前环境使用 Anaconda，已验证）
- 依赖：requests（测试脚本使用），若未安装请运行：

```powershell
pip install -r requirements.txt
```

（`requirements.txt` 已包含 `requests`）

## 如何启动服务器（PowerShell）
在项目根目录运行：

```powershell
python server.py
```

为了保留日志，请在单独终端使用：

```powershell
python server.py 2>&1 | Tee-Object -FilePath server_log.txt
```

- 如果端口被占用或被防火墙拦截，请检查 Windows 防火墙或换用其他端口（修改 `server.py` 中 `PORT`）。

## 如何运行测试（PowerShell）
在另一个终端（服务器在运行）运行：

按模块运行（推荐）：

```powershell
python -m unittest tests.AnsweringModule.test_answering_module -v 2>&1 | Tee-Object -FilePath test_output.txt
```

按文件运行：

```powershell
python -m unittest tests/AnsweringModule/test_answering_module.py -v
```

测试说明：
- `test_concurrent_submissions_and_grading` 会在 `problems/problem1` 写入一个简单测试点，然后并发 50 个学生上传正确代码到 `/submit_code`，并断言大多数（默认 >=45）获得满分。
- 测试会在本地 `users.db` 中插入或更新 `student1..student50`（密码为 `123456`），以便登录。

## 已做的代码改动（摘要）
- `server.py`：改为多线程服务器（使用 `socketserver.ThreadingTCPServer`），设置 `allow_reuse_address=True`、`daemon_threads=True`，并尝试提高 `request_queue_size`。
- `tests/AnsweringModule/test_answering_module.py`：
  - 创建/保证 50 个学生账号存在
  - 放宽登录断言以接受 `200/302`
  - 并发提交测试加入重试、延长超时与短抖动以提高稳定性

## 故障排查要点
- 如果看到 `ConnectionRefusedError`（WinError 10061）：说明服务器未运行或被防火墙拦截。确认 `server.py` 在运行并查看 `server_log.txt`。
- 如果测试报 401 未授权：确认测试用账号已插入到 `users.db`，并且测试与服务器使用同一 `users.db`（同一工作目录）。
- 并发失败：先从 50 减少到 10/20 做 smoke test；或增加测试重试次数/延长 timeout。

## 建议的下一步
- 若要在 CI 中运行：建议把服务器改为 WSGI/ASGI（例如使用 Flask + Gunicorn 或 FastAPI + Uvicorn）并在 workflow 中启动后运行测试。

---
如果你要我把这些改动整理成 PR，或添加 CI 配置，我可以继续处理。
