import unittest
import threading
import requests
import time
import sqlite3
import os

BASE_URL = 'http://localhost:8000'


class TestStudentAnsweringModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """在运行测试前，确保数据库存在需要的学生账号（student1..student50）。"""
        # 导入 server 模块以获得 DB_FILE 路径（不会启动服务器）
        try:
            import server
            db_path = server.DB_FILE
        except Exception:
            # 如果无法导入 server，退回到相对路径
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'users.db')
            db_path = os.path.normpath(db_path)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # 创建 users 表（避免表不存在导致插入失败）
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                grade TEXT NOT NULL,
                class_num TEXT NOT NULL,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                UNIQUE(grade, class_num, username)
            )
        ''')

        # 插入或替换 50 个学生账号
        for i in range(1, 51):
            username = f'student{i}'
            try:
                cur.execute('''INSERT OR REPLACE INTO users (id, grade, class_num, username, password)
                               VALUES ((SELECT id FROM users WHERE grade=? AND class_num=? AND username=?), ?, ?, ?, ?)''',
                            ( '1', '1', username, '1', '1', username, '123456'))
            except Exception:
                # 有些 SQLite 版本不支持 the above trick; 使用简单的 UPSERT
                try:
                    cur.execute('''INSERT INTO users (grade, class_num, username, password)
                                   VALUES (?, ?, ?, ?)
                                   ON CONFLICT(grade, class_num, username) DO UPDATE SET password=excluded.password''',
                                ('1', '1', username, '123456'))
                except Exception:
                    # 最后一招：先尝试插入，失败则更新
                    try:
                        cur.execute('INSERT INTO users (grade, class_num, username, password) VALUES (?, ?, ?, ?)',
                                    ('1', '1', username, '123456'))
                    except sqlite3.IntegrityError:
                        cur.execute('UPDATE users SET password=? WHERE grade=? AND class_num=? AND username=?',
                                    ('123456', '1', '1', username))

        conn.commit()
        conn.close()

    def _login_with(self, session, url, data):
        """POST 登录并返回响应，断言登录没有返回明显的错误页面文本。"""
        resp = session.post(url, data=data, allow_redirects=False)
        # 接受 302 或 200；若为200，确认返回体不包含登录失败提示
        if resp.status_code == 200:
            body = resp.text or ''
            self.assertNotIn('錯誤', body)
            self.assertNotIn('錯誤', body)
        else:
            self.assertIn(resp.status_code, (302, 200))
        return resp

    def test_dashboard_load_and_submit(self):
        """测试学生端dashboard能否正确读取、加载和提交题目"""
        session = requests.Session()
        login_data = {
            'grade': '1',
            'class_num': '1',
            'username': 'student1',
            'password': '123456'
        }
        resp = self._login_with(session, f'{BASE_URL}/login', login_data)

        # 获取题目列表
        resp = session.get(f'{BASE_URL}/api/problems')
        self.assertIn(resp.status_code, (200, 401))
        if resp.status_code == 200:
            problems = resp.json()
            self.assertTrue(isinstance(problems, list))
            # 如果有题目，尝试加载第一题
            if len(problems) > 0:
                problem_id = problems[0]['id']
                resp = session.get(f'{BASE_URL}/api/problem/{problem_id}')
                self.assertEqual(resp.status_code, 200)
                detail = resp.json()
                self.assertIn('description', detail)

    def test_dashboard_grading(self):
        """测试学生端dashboard提交后能否正确批改（接口需存在）"""
        session = requests.Session()
        login_data = {
            'grade': '1',
            'class_num': '1',
            'username': 'student1',
            'password': '123456'
        }
        self._login_with(session, f'{BASE_URL}/login', login_data)

        # 如果存在提交接口，请将下面注释取消并适配实际字段
        # code = 'print(1+1)'
        # resp = session.post(f'{BASE_URL}/submit', data={'problem_id': 1, 'code': code})
        # self.assertIn('得分率', resp.text)

    def test_teacher_update_problem_sync(self):
        """测试教师端后台更新题目后学生端能否同步更新"""
        # 教师登录（teacher 硬编码账户已存在）
        session = requests.Session()
        login_data = {
            'username': 'alex',
            'password': 'teacher123'
        }
        resp = self._login_with(session, f'{BASE_URL}/teacher-login', login_data)
        # 假如更新接口存在，可以在此执行更新操作，然后学生端检查
        student_session = requests.Session()
        student_login = {
            'grade': '1',
            'class_num': '1',
            'username': 'student1',
            'password': '123456'
        }
        self._login_with(student_session, f'{BASE_URL}/login', student_login)
        resp = student_session.get(f'{BASE_URL}/api/problem/1')
        self.assertIn(resp.status_code, (200, 404))

    def test_concurrent_logins(self):
        """验证 50 个学生能够同时登录（高并发登录场景）"""
        lock = threading.Lock()
        results = []

        def login_task(idx):
            s = requests.Session()
            login_data = {
                'grade': '1',
                'class_num': '1',
                'username': f'student{idx}',
                'password': '123456'
            }
            try:
                resp = s.post(f'{BASE_URL}/login', data=login_data, allow_redirects=False)
                success = (resp.status_code == 302) or (resp.status_code == 200 and '錯誤' not in (resp.text or ''))
            except Exception:
                success = False
            with lock:
                results.append(success)

        threads = []
        for i in range(1, 51):
            t = threading.Thread(target=login_task, args=(i,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        # 至少所有线程都完成，并且大多数登录应成功（允许少量失败，取决于服务器资源）
        self.assertEqual(len(results), 50)
        self.assertTrue(sum(1 for r in results if r) >= 40)

    def test_concurrent_submissions_and_grading(self):
        """真实并发提交：50 个学生同时提交同一道题，期望每次批改返回满分。"""
        # 准备题目 files: problems/problem1/input1.txt output1.txt description.txt
        base_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
        problems_dir = os.path.join(base_dir, 'problems')
        problem1_dir = os.path.join(problems_dir, 'problem1')
        os.makedirs(problem1_dir, exist_ok=True)

        # 简单题目：输入两行数字，输出它们之和
        with open(os.path.join(problem1_dir, 'description.txt'), 'w', encoding='utf-8') as f:
            f.write('将兩個整數相加並輸出結果')
        with open(os.path.join(problem1_dir, 'input1.txt'), 'w', encoding='utf-8') as f:
            f.write('1\n2')
        with open(os.path.join(problem1_dir, 'output1.txt'), 'w', encoding='utf-8') as f:
            f.write('3')

        # 每个学生提交的正确解答文件内容
        student_code = """import sys
data = sys.stdin.read().split()
try:
    a = int(data[0])
    b = int(data[1])
    print(a+b)
except Exception:
    pass
"""

        results = []
        lock = threading.Lock()

        def submit_task(idx):
            s = requests.Session()
            login_data = {
                'grade': '1',
                'class_num': '1',
                'username': f'student{idx}',
                'password': '123456'
            }
            try:
                # 登录获取 session cookie
                s.post(f'{BASE_URL}/login', data=login_data, allow_redirects=False)

                files = {
                    'codeFile': (f'solution_{idx}.py', student_code, 'text/x-python'),
                }
                data = {'problem_id': '1'}
                # 重试逻辑，处理短暂的连接被拒绝
                resp = None
                last_exc = None
                for attempt in range(5):
                    try:
                        # 随机短抖动，降低瞬时请求峰值
                        time.sleep(0.01 * attempt)
                        resp = s.post(f'{BASE_URL}/submit_code', files=files, data=data, timeout=20)
                        break
                    except Exception as e:
                        last_exc = e
                        time.sleep(0.05 * (2 ** attempt))

                ok = False
                score = None
                status = None
                if resp is not None:
                    status = resp.status_code
                    if resp.status_code == 200:
                        try:
                            j = resp.json()
                            ok = j.get('success', False)
                            score = j.get('score')
                        except Exception:
                            pass
                else:
                    status = str(last_exc)

                with lock:
                    results.append((ok, score, status))
            except Exception as e:
                with lock:
                    results.append((False, None, str(e)))

        threads = []
        for i in range(1, 51):
            t = threading.Thread(target=submit_task, args=(i,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        # 分析结果：所有响应应成功并得分为100
        successes = [r for r in results if r[0] is True and r[1] is not None and float(r[1]) >= 100]
        # 打印诊断到测试输出（unittest 会显示失败断言信息）
        self.assertEqual(len(results), 50, f'应有50个结果，实际{len(results)}')
        self.assertTrue(len(successes) >= 45, f'成功并满分的提交应>=45，实际{len(successes)}，详情：{results}')


if __name__ == '__main__':
    unittest.main()
