import http.server
import socketserver
import urllib.parse
import os
import sqlite3
import cgi
import subprocess
import glob
import datetime

PORT = 8000
DB_FILE = 'users.db'

def setup_database():
    """設定並建立資料庫表格"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 建立 users 表格
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    # 建立 scores 表格
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            problem_id INTEGER NOT NULL,
            score REAL NOT NULL,
            submission_time TEXT NOT NULL,
            FOREIGN KEY (username) REFERENCES users (username),
            UNIQUE (username, problem_id)
        )
    ''')
    conn.commit()
    conn.close()

def authenticate_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = cursor.fetchone()
    conn.close()
    return user is not None

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
        elif self.path == '/dashboard.html':
            self.path = 'templates/dashboard.html'
        
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
            username = parsed_data.get('username', [''])[0]
            password = parsed_data.get('password', [''])[0]
            
            if authenticate_user(username, password):
                self.send_response(302)
                self.send_header('Location', '/dashboard.html')
                self.end_headers()
            else:
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                error_message = f"帳號或密碼錯誤！請返回<a href='/'>登入頁面</a>重試。"
                self.wfile.write(error_message.encode('utf-8'))
        
        # 檢查是否為程式碼提交請求
        elif self.path == '/submit_code':
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
                    # 暫時硬編碼使用者和題目ID
                    username = "test_user"
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

                    # 將成績存入資料庫
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute(
                        '''
                        INSERT INTO scores (username, problem_id, score, submission_time)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(username, problem_id) DO UPDATE SET
                            score = excluded.score,
                            submission_time = excluded.submission_time
                        ''',
                        (username, problem_id, score_percentage, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
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