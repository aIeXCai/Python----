import http.server, socketserver, urllib.parse, os
import sqlite3, cgi, subprocess, glob, datetime
import uuid, time

PORT = 8000
DB_FILE = 'users.db'

# Session 管理
SESSIONS = {}  # {session_id: {'username': 'xxx', 'created_time': timestamp, 'role': 'student/teacher'}}
SESSION_TIMEOUT = 2 * 60 * 60  # 2小时过期

# 老师账号配置
TEACHER_CREDENTIALS = {
    'alex': 'teacher123',
}

def setup_database():
    """設定並建立資料庫表格"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 建立 users 表格
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            grade TEXT NOT NULL,
            class_num TEXT NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            UNIQUE(grade, class_num, username)
        )
    ''')
    # 建立 scores 表格
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY,
            grade TEXT NOT NULL,
            class_num TEXT NOT NULL,
            username TEXT NOT NULL,
            problem_id INTEGER NOT NULL,
            score REAL NOT NULL,
            submission_time TEXT NOT NULL,
            FOREIGN KEY (grade, class_num, username) REFERENCES users (grade, class_num, username),
            UNIQUE (grade, class_num, username, problem_id)
        )
    ''')
    conn.commit()
    conn.close()

def authenticate_user(grade, class_num, username, password):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE grade=? AND class_num=? AND username=? AND password=?", 
                   (grade, class_num, username, password))
    user = cursor.fetchone()
    conn.close()
    return user is not None

def authenticate_teacher(username, password):
    """验证老师账号密码（硬编码验证）"""
    return username in TEACHER_CREDENTIALS and TEACHER_CREDENTIALS[username] == password

def register_user(grade, class_num, username, password):
    """注册新用户"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (grade, class_num, username, password) VALUES (?, ?, ?, ?)", 
                       (grade, class_num, username, password))
        conn.commit()
        conn.close()
        return True, "注册成功！"
    except sqlite3.IntegrityError:
        conn.close()
        return False, f"该年级班级中已存在用户名 '{username}'，请选择其他用户名。"
    except Exception as e:
        conn.close()
        return False, f"注册失败：{str(e)}"

def generate_session_id():
    """生成唯一的 session ID"""
    return uuid.uuid4().hex

def create_session(username, role='student', grade=None, class_num=None):
    """为用户创建新的 session"""
    cleanup_expired_sessions()  # 先清理过期的 sessions
    
    session_id = generate_session_id()
    SESSIONS[session_id] = {
        'username': username,
        'role': role,
        'grade': grade,
        'class_num': class_num,
        'created_time': time.time()
    }
    return session_id

def get_user_from_session(session_id):
    """根据 session_id 获取用户信息"""
    if not session_id or session_id not in SESSIONS:
        return None
    
    session_data = SESSIONS[session_id]
    # 检查是否过期
    if time.time() - session_data['created_time'] > SESSION_TIMEOUT:
        del SESSIONS[session_id]
        return None
    
    return session_data

def cleanup_expired_sessions():
    """清理过期的 sessions"""
    current_time = time.time()
    expired_sessions = [
        sid for sid, data in SESSIONS.items() 
        if current_time - data['created_time'] > SESSION_TIMEOUT
    ]
    for sid in expired_sessions:
        del SESSIONS[sid]

def parse_cookies(cookie_header):
    """解析 Cookie 字符串，返回字典"""
    cookies = {}
    if cookie_header:
        for item in cookie_header.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
    return cookies

def grade_submission(submission_path, problem_num):
    """
    自動批改學生程式碼，採用測試點法則。
    """
    problem_dir = f'problems/problem{problem_num}'
    if not os.path.exists(problem_dir):
        return False, "❌ 找不到指定的題目資料夾。"

    # 找到所有測試點的輸入檔案
    input_files = sorted(glob.glob(os.path.join(problem_dir, 'input*.txt')))
    total_tests = len(input_files)
    passed_tests = 0
    test_results = []
    
    # 逐一執行每個測試點
    for i, input_file in enumerate(input_files, 1):
        output_file = input_file.replace('input', 'output')
        
        # 讀取輸入與正確輸出
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                test_input = f.read()
            with open(output_file, 'r', encoding='utf-8') as f:
                correct_output = f.read().strip()
        except FileNotFoundError:
            test_results.append(f"測試點 {i}: ❌ 找不到輸入或輸出檔案。")
            continue
        
        # 執行學生程式碼
        try:
            result = subprocess.run(
                ['python', submission_path],
                input=test_input,
                capture_output=True,
                text=True,
                timeout=5,
                check=True
            )
            student_output = result.stdout.strip()
            
            # 比對結果
            if student_output == correct_output:
                test_results.append(f"測試點 {i}: ✅ 通過！")
                passed_tests += 1
            else:
                test_results.append(f"測試點 {i}: ❌ 失敗。\n你的輸出：'{student_output}'\n正確輸出：'{correct_output}'")
        
        except subprocess.CalledProcessError as e:
            test_results.append(f"測試點 {i}: ❌ 程式碼執行時發生錯誤：\n{e.stderr}")
        except subprocess.TimeoutExpired:
            test_results.append(f"測試點 {i}: ❌ 程式碼執行超時！")
        except Exception as e:
            test_results.append(f"測試點 {i}: ❌ 發生意外錯誤：{e}")

    # 計算總分並回傳結果
    score_percentage = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    summary = f"總分: {passed_tests}/{total_tests} (得分率: {score_percentage:.2f}%)"
    full_report = '\n'.join(test_results)
    
    return True, f"{summary}\n\n詳細報告：\n{full_report}"

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = 'templates/index.html'
        elif self.path == '/teacher':
            # 老师登录页面
            self.path = 'templates/teacher_login.html'
        elif self.path == '/admin':
            # 检查老师是否已登录
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'teacher':
                # 未登录或不是老师，重定向到老师登录页面
                self.send_response(302)
                self.send_header('Location', '/teacher')
                self.end_headers()
                return
            
            # 读取管理后台模板并替换用户信息
            try:
                with open('templates/admin_dashboard.html', 'r', encoding='utf-8') as f:
                    admin_content = f.read()
                
                # 替换占位符
                admin_content = admin_content.replace('{{USERNAME}}', user_data['username'])
                
                # 发送自定义的 HTML 响应
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(admin_content.encode('utf-8'))
                return
            except FileNotFoundError:
                self.send_error(404, "Admin dashboard template not found")
        elif self.path == '/dashboard.html':
            # 检查学生是否已登录
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'student':
                # 未登录或不是学生，重定向到登录页面
                self.send_response(302)
                self.send_header('Location', '/')
                self.end_headers()
                return
            
            # 读取 dashboard 模板并替换用户信息
            try:
                with open('templates/dashboard.html', 'r', encoding='utf-8') as f:
                    dashboard_content = f.read()
                
                # 替换占位符
                dashboard_content = dashboard_content.replace('{{USERNAME}}', user_data['username'])
                dashboard_content = dashboard_content.replace('{{GRADE}}', user_data['grade'])
                dashboard_content = dashboard_content.replace('{{CLASS}}', user_data['class_num'])
                
                # 发送自定义的 HTML 响应
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(dashboard_content.encode('utf-8'))
                return
            except FileNotFoundError:
                self.send_error(404, "Dashboard template not found")
        elif self.path == '/logout':
            # 處理登出請求
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            if session_id and session_id in SESSIONS:
                del SESSIONS[session_id]
            
            # 重定向到登录页面并清除 Cookie
            self.send_response(302)
            self.send_header('Location', '/')
            self.send_header('Set-Cookie', 'session_id=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT')
            self.end_headers()
            return
        
        try:
            return http.server.SimpleHTTPRequestHandler.do_GET(self)
        except FileNotFoundError:
            self.send_error(404, "File Not Found")
            
    def do_POST(self):
        # 檢查是否為登入請求
        if self.path == '/login':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            post_data_str = post_data.decode('utf-8')
            parsed_data = urllib.parse.parse_qs(post_data_str)
            grade = parsed_data.get('grade', [''])[0]
            class_num = parsed_data.get('class_num', [''])[0]
            username = parsed_data.get('username', [''])[0]
            password = parsed_data.get('password', [''])[0]
            
            if authenticate_user(grade, class_num, username, password):
                # 创建学生 session
                session_id = create_session(username, 'student', grade, class_num)
                
                # 发送重定向响应，并设置 Cookie
                self.send_response(302)
                self.send_header('Location', '/dashboard.html')
                self.send_header('Set-Cookie', f'session_id={session_id}; Path=/; HttpOnly; Max-Age=7200')  # 2小时
                self.end_headers()
            else:
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                error_message = f"年級、班級、帳號或密碼錯誤！請返回<a href='/'>登入頁面</a>重試。"
                self.wfile.write(error_message.encode('utf-8'))
        
        # 檢查是否為老師登入請求
        elif self.path == '/teacher-login':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            post_data_str = post_data.decode('utf-8')
            parsed_data = urllib.parse.parse_qs(post_data_str)
            username = parsed_data.get('username', [''])[0]
            password = parsed_data.get('password', [''])[0]
            
            if authenticate_teacher(username, password):
                # 创建老师 session
                session_id = create_session(username, 'teacher')
                
                # 发送重定向响应到管理后台，并设置 Cookie
                self.send_response(302)
                self.send_header('Location', '/admin')
                self.send_header('Set-Cookie', f'session_id={session_id}; Path=/; HttpOnly; Max-Age=7200')  # 2小时
                self.end_headers()
            else:
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                error_message = f"帳號或密碼錯誤！請返回<a href='/teacher'>老師登入頁面</a>重試。"
                self.wfile.write(error_message.encode('utf-8'))
        
        # 檢查是否為註冊請求
        elif self.path == '/register':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            post_data_str = post_data.decode('utf-8')
            parsed_data = urllib.parse.parse_qs(post_data_str)
            grade = parsed_data.get('grade', [''])[0]
            class_num = parsed_data.get('class_num', [''])[0]
            username = parsed_data.get('username', [''])[0]
            password = parsed_data.get('password', [''])[0]
            confirm_password = parsed_data.get('confirm_password', [''])[0]
            
            # 验证输入
            if not grade or not class_num or not username or not password:
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                error_message = f"所有字段都不能为空！<a href='/'>返回</a>"
                self.wfile.write(error_message.encode('utf-8'))
                return
            
            if password != confirm_password:
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                error_message = f"两次输入的密码不一致！<a href='/'>返回</a>"
                self.wfile.write(error_message.encode('utf-8'))
                return
            
            # 尝试注册用户
            success, message = register_user(grade, class_num, username, password)
            if success:
                # 注册成功，自动登录
                session_id = create_session(grade, class_num, username)
                self.send_response(302)
                self.send_header('Location', '/dashboard.html')
                self.send_header('Set-Cookie', f'session_id={session_id}; Path=/; HttpOnly; Max-Age=7200')
                self.end_headers()
            else:
                # 注册失败，显示错误信息
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                error_message = f"{message}<a href='/'>返回</a>"
                self.wfile.write(error_message.encode('utf-8'))
        
        # 檢查是否為程式碼提交請求
        elif self.path == '/submit_code':
            # 验证 session
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'student':
                # 未登录或不是学生，重定向到登录页面
                self.send_response(302)
                self.send_header('Location', '/')
                self.end_headers()
                return
            
            # 注意：這裡不能先讀取 rfile，cgi.FieldStorage 需要直接從 rfile 解析 multipart/form-data
            form = cgi.FieldStorage(
                fp=self.rfile, 
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST',
                        'CONTENT_TYPE': self.headers['Content-Type'],
                        })
            
            if 'codeFile' in form:
                file_item = form['codeFile']
                if file_item.filename:
                    # 使用从 session 中获取的真实用户名和信息
                    username = user_data['username']
                    grade = user_data['grade']
                    class_num = user_data['class_num']
                    problem_id = 1
                    
                    submission_path = os.path.join('submissions', file_item.filename)
                    with open(submission_path, 'wb') as f:
                        f.write(file_item.file.read())
                    
                    is_ok, grade_result = grade_submission(submission_path, problem_id)
                    
                    # 從回傳結果中提取分數
                    score_percentage = 0
                    if "得分率:" in grade_result:
                        try:
                            score_percentage = float(grade_result.split("得分率:")[1].split("%")[0].strip())
                        except (ValueError, IndexError):
                            pass

                    # 將成績存入資料庫（存在即更新）
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute(
                        '''
                        INSERT INTO scores (grade, class_num, username, problem_id, score, submission_time)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(grade, class_num, username, problem_id) DO UPDATE SET
                            score = excluded.score,
                            submission_time = excluded.submission_time
                        ''',
                        (grade, class_num, username, problem_id, score_percentage, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    )
                    conn.commit()
                    conn.close()
                    
                    # 读取结果模板文件
                    with open('templates/result.html', 'r', encoding='utf-8') as f:
                        template = f.read()
                    
                    # 替换占位符
                    response_message = template.replace('{{GRADE_RESULT}}', grade_result)

                    # 返回渲染后的HTML页面
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(response_message.encode('utf-8'))
                else:
                    self.send_error(400, "沒有選擇檔案")
            else:
                self.send_error(400, "沒有找到 'codeFile' 欄位")
        
        else:
            self.send_error(404, "Not Found")

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

os.chdir(os.path.dirname(os.path.abspath(__file__)))
if not os.path.exists('submissions'):
    os.makedirs('submissions')
if not os.path.exists('problems'):
    os.makedirs('problems')
setup_database()
cleanup_expired_sessions()  # 服务器启动时清理过期 sessions
Handler = MyHandler
httpd = socketserver.TCPServer(("", PORT), Handler)

print(f"伺服器已啟動，請在瀏覽器中輸入 http://localhost:{PORT}")
print("按下 Ctrl + C 即可停止伺服器")

try:
    httpd.serve_forever()
except KeyboardInterrupt:
    pass

httpd.server_close()
print("伺服器已關閉")