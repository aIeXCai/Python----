import http.server, socketserver, urllib.parse, os
import sqlite3, cgi, subprocess, glob, datetime
import uuid, time

PORT = 8000
DB_FILE = 'users.db'

# <!-- 组件模块 -->
# 加载模板组件
def load_template_component(component_name):
    """加载模板组件"""
    try:
        component_path = f'templates/components/{component_name}.html'
        with open(component_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"<!-- Template component {component_name} not found -->"

# 渲染模板组件
def render_template_component(component_name, **kwargs):
    """渲染模板组件"""
    template = load_template_component(component_name)
    for key, value in kwargs.items():
        template = template.replace(f'{{{{{key}}}}}', str(value))
    return template

# 渲染主模板
def render_main_template(template_path, **kwargs):
    """渲染主模板文件"""
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        for key, value in kwargs.items():
            template_content = template_content.replace(f'{{{{{key}}}}}', str(value))
        
        return template_content
    except FileNotFoundError:
        return f"<!-- Template {template_path} not found -->"

# Session 管理
SESSIONS = {}  # {session_id: {'username': 'xxx', 'created_time': timestamp, 'role': 'student/teacher'}}
SESSION_TIMEOUT = 2 * 60 * 60  # 2小时过期

# 老师账号配置
TEACHER_CREDENTIALS = {
    'alex': 'teacher123',
}

# 数据库初始化
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

# <!-- 认证与注册 -->
# 用户认证
def authenticate_user(grade, class_num, username, password):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE grade=? AND class_num=? AND username=? AND password=?", 
                   (grade, class_num, username, password))
    user = cursor.fetchone()
    conn.close()
    return user is not None

# 教师认证
def authenticate_teacher(username, password):
    """验证老师账号密码（硬编码验证）"""
    return username in TEACHER_CREDENTIALS and TEACHER_CREDENTIALS[username] == password

# 用户注册
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



# <!-- Session 管理 -->
# 生成唯一的 session ID
def generate_session_id():
    """生成唯一的 session ID"""
    return uuid.uuid4().hex

# 创建新的 session
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

# 根据 session_id 获取用户信息
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

# 清理过期的 sessions
def cleanup_expired_sessions():
    """清理过期的 sessions"""
    current_time = time.time()
    expired_sessions = [
        sid for sid, data in SESSIONS.items() 
        if current_time - data['created_time'] > SESSION_TIMEOUT
    ]
    for sid in expired_sessions:
        del SESSIONS[sid]



# <!-- 题目管理 -->
# 获取所有题目列表
def get_problems_list():
    """获取所有题目列表"""
    problems_dir = 'problems'
    problems = []
    
    if os.path.exists(problems_dir):
        for item in os.listdir(problems_dir):
            item_path = os.path.join(problems_dir, item)
            if os.path.isdir(item_path) and item.startswith('problem'):
                # 检查题目文件夹中是否有必要的文件
                description_file = os.path.join(item_path, 'description.txt')
                input_files = glob.glob(os.path.join(item_path, 'input*.txt'))
                output_files = glob.glob(os.path.join(item_path, 'output*.txt'))
                
                problems.append({
                    'name': item,
                    'path': item_path,
                    'has_description': os.path.exists(description_file),
                    'test_cases': min(len(input_files), len(output_files))
                })
    
    # 按題目編號排序
    problems.sort(key=lambda x: int(x['name'].replace('problem', '')) if x['name'].replace('problem', '').isdigit() else 0)
    return problems

# 保存上传的题目
def save_uploaded_problem(problem_id, description_file, test_files):
    """保存上传的题目文件"""
    problem_dir = f'problems/problem{problem_id}'
    
    # 检查题目是否已存在
    if os.path.exists(problem_dir):
        return False, f"題目 {problem_id} 已經存在！"
    
    try:
        # 创建题目文件夹
        os.makedirs(problem_dir, exist_ok=True)
        
        # 保存描述文件
        description_path = os.path.join(problem_dir, 'description.txt')
        with open(description_path, 'wb') as f:
            if hasattr(description_file, 'file'):
                f.write(description_file.file.read())
            else:
                f.write(description_file.value)
        
        # 整理测试文件
        input_files = []
        output_files = []
        
        for file_item in test_files:
            filename = file_item.filename.lower()
            if filename.startswith('input') and filename.endswith('.txt'):
                input_files.append(file_item)
            elif filename.startswith('output') and filename.endswith('.txt'):
                output_files.append(file_item)
        
        # 按数字排序
        input_files.sort(key=lambda x: int(''.join(filter(str.isdigit, x.filename))) or 0)
        output_files.sort(key=lambda x: int(''.join(filter(str.isdigit, x.filename))) or 0)
        
        # 检查输入和输出文件数量是否匹配
        if len(input_files) != len(output_files):
            # 清理已创建的文件夹
            import shutil
            shutil.rmtree(problem_dir)
            return False, f"輸入檔案數量 ({len(input_files)}) 與輸出檔案數量 ({len(output_files)}) 不匹配！"
        
        if len(input_files) == 0:
            import shutil
            shutil.rmtree(problem_dir)
            return False, "未找到有效的測試點檔案！"
        
        # 保存测试文件，重新命名为标准格式
        for i, (input_file, output_file) in enumerate(zip(input_files, output_files), 1):
            # 保存输入文件
            input_path = os.path.join(problem_dir, f'input{i}.txt')
            with open(input_path, 'wb') as f:
                if hasattr(input_file, 'file'):
                    f.write(input_file.file.read())
                else:
                    f.write(input_file.value)
            
            # 保存输出文件
            output_path = os.path.join(problem_dir, f'output{i}.txt')
            with open(output_path, 'wb') as f:
                if hasattr(output_file, 'file'):
                    f.write(output_file.file.read())
                else:
                    f.write(output_file.value)
        
        return True, f"題目 {problem_id} 上傳成功！包含 {len(input_files)} 個測試點。"
        
    except Exception as e:
        # 如果出错，清理已创建的文件夹
        if os.path.exists(problem_dir):
            import shutil
            shutil.rmtree(problem_dir)
        return False, f"上傳失敗：{str(e)}"

# 获取题目详细信息
def get_problem_details(problem_name):
    """获取题目详细信息"""
    problem_dir = f'problems/{problem_name}'
    
    if not os.path.exists(problem_dir):
        return None
    
    details = {
        'name': problem_name,
        'description': '',
        'test_cases': []
    }
    
    # 读取描述文件
    description_path = os.path.join(problem_dir, 'description.txt')
    if os.path.exists(description_path):
        try:
            with open(description_path, 'r', encoding='utf-8') as f:
                details['description'] = f.read()
        except UnicodeDecodeError:
            with open(description_path, 'r', encoding='gbk') as f:
                details['description'] = f.read()
    
    # 读取测试点
    input_files = sorted(glob.glob(os.path.join(problem_dir, 'input*.txt')))
    output_files = sorted(glob.glob(os.path.join(problem_dir, 'output*.txt')))
    
    for i, (input_file, output_file) in enumerate(zip(input_files, output_files), 1):
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                input_content = f.read()
        except UnicodeDecodeError:
            with open(input_file, 'r', encoding='gbk') as f:
                input_content = f.read()
        
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                output_content = f.read()
        except UnicodeDecodeError:
            with open(output_file, 'r', encoding='gbk') as f:
                output_content = f.read()
        
        details['test_cases'].append({
            'number': i,
            'input': input_content,
            'output': output_content
        })
    
    return details

# 删除题目
def delete_problem(problem_name):
    """删除题目"""
    problem_dir = f'problems/{problem_name}'
    
    if not os.path.exists(problem_dir):
        return False, f"題目 {problem_name} 不存在！"
    
    try:
        import shutil
        shutil.rmtree(problem_dir)
        return True, f"題目 {problem_name} 刪除成功！"
    except Exception as e:
        return False, f"刪除失敗：{str(e)}"

# 更新题目
def update_problem(problem_name, description, test_cases_data):
    """更新题目信息"""
    problem_dir = f'problems/{problem_name}'
    
    if not os.path.exists(problem_dir):
        return False, f"題目 {problem_name} 不存在！"
    
    try:
        # 更新描述文件
        description_path = os.path.join(problem_dir, 'description.txt')
        with open(description_path, 'w', encoding='utf-8') as f:
            f.write(description)
        
        # 删除现有的测试点文件
        for file in glob.glob(os.path.join(problem_dir, 'input*.txt')):
            os.remove(file)
        for file in glob.glob(os.path.join(problem_dir, 'output*.txt')):
            os.remove(file)
        
        # 写入新的测试点
        for i, test_case in enumerate(test_cases_data, 1):
            input_path = os.path.join(problem_dir, f'input{i}.txt')
            output_path = os.path.join(problem_dir, f'output{i}.txt')
            
            with open(input_path, 'w', encoding='utf-8') as f:
                f.write(test_case['input'])
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(test_case['output'])
        
        return True, f"題目 {problem_name} 更新成功！"
    except Exception as e:
        return False, f"更新失敗：{str(e)}"




# <!-- 学生管理 -->
# 获取所有学生
def get_all_students():
    """获取所有学生列表"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, grade, class_num, username, password FROM users ORDER BY grade, class_num, username")
    students = cursor.fetchall()
    conn.close()
    return students

# 根据ID获取学生信息
def get_student_by_id(student_id):
    """根据ID获取学生信息"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, grade, class_num, username, password FROM users WHERE id=?", (student_id,))
    student = cursor.fetchone()
    conn.close()
    return student

# 更新学生信息
def update_student(student_id, grade, class_num, username, password=None):
    """更新学生信息"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        if password:
            cursor.execute(
                "UPDATE users SET grade=?, class_num=?, username=?, password=? WHERE id=?",
                (grade, class_num, username, password, student_id)
            )
        else:
            cursor.execute(
                "UPDATE users SET grade=?, class_num=?, username=? WHERE id=?",
                (grade, class_num, username, student_id)
            )
        
        # 同时更新 scores 表中的相关信息
        cursor.execute(
            "UPDATE scores SET grade=?, class_num=?, username=? WHERE grade=(SELECT grade FROM users WHERE id=?) AND class_num=(SELECT class_num FROM users WHERE id=?) AND username=(SELECT username FROM users WHERE id=?)",
            (grade, class_num, username, student_id, student_id, student_id)
        )
        
        conn.commit()
        conn.close()
        return True, "学生信息更新成功！"
    except sqlite3.IntegrityError:
        conn.close()
        return False, f"该年级班级中已存在用户名 '{username}'，请选择其他用户名。"
    except Exception as e:
        conn.close()
        return False, f"更新失败：{str(e)}"

# 删除学生
def delete_student(student_id):
    """删除学生"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        # 先获取学生信息用于删除相关成绩记录
        cursor.execute("SELECT grade, class_num, username FROM users WHERE id=?", (student_id,))
        student_info = cursor.fetchone()
        
        if not student_info:
            conn.close()
            return False, "学生不存在！"
        
        grade, class_num, username = student_info
        
        # 删除相关成绩记录
        cursor.execute("DELETE FROM scores WHERE grade=? AND class_num=? AND username=?", 
                      (grade, class_num, username))
        
        # 删除学生记录
        cursor.execute("DELETE FROM users WHERE id=?", (student_id,))
        
        conn.commit()
        conn.close()
        return True, f"学生 {username} 删除成功！"
    except Exception as e:
        conn.close()
        return False, f"删除失败：{str(e)}"




# <!-- 解析 Cookie -->
def parse_cookies(cookie_header):
    """解析 Cookie 字符串，返回字典"""
    cookies = {}
    if cookie_header:
        for item in cookie_header.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
    return cookies


# <!-- 自动批改 -->
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



# <!-- 请求处理 -->
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
        elif urllib.parse.urlparse(self.path).path == '/admin/problems':
            # 题目管理页面
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'teacher':
                # 未登录或不是老师，重定向到老师登录页面
                self.send_response(302)
                self.send_header('Location', '/teacher')
                self.end_headers()
                return
            
            # 获取题目列表
            problems = get_problems_list()
            
            # 生成题目列表HTML
            if problems:
                problems_html = ""
                for problem in problems:
                    status_info = f"{problem['test_cases']} 個測試點" if problem['test_cases'] > 0 else "無測試點"
                    problems_html += render_template_component(
                        'problem_item',
                        PROBLEM_NAME=problem['name'],
                        PROBLEM_INFO=status_info
                    )
            else:
                problems_html = '<div class="no-problems">目前沒有任何題目</div>'
            
            # 读取题目管理模板并替换占位符
            try:
                with open('templates/problem_management.html', 'r', encoding='utf-8') as f:
                    template_content = f.read()
                
                # 替换占位符
                template_content = template_content.replace('{{PROBLEMS_LIST}}', problems_html)
                
                # 发送自定义的 HTML 响应
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(template_content.encode('utf-8'))
                return
            except FileNotFoundError:
                self.send_error(404, "Problem management template not found")
        elif urllib.parse.urlparse(self.path).path.startswith('/admin/view-problem/'):
            # 查看题目详情页面
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'teacher':
                # 未登录或不是老师，重定向到老师登录页面
                self.send_response(302)
                self.send_header('Location', '/teacher')
                self.end_headers()
                return
            
            # 提取题目名称
            parsed_path = urllib.parse.urlparse(self.path).path
            problem_name = parsed_path.split('/admin/view-problem/', 1)[1]
            if not problem_name:
                self.send_error(400, "Missing problem name")
                return
            
            # 获取题目详情
            problem_details = get_problem_details(problem_name)
            if not problem_details:
                self.send_error(404, "Problem not found")
                return
            
            # 读取题目详情模板
            try:
                # 构建测试案例HTML
                test_cases_html = ""
                for i, test_case in enumerate(problem_details['test_cases'], 1):
                    test_cases_html += render_template_component(
                        'test_case_item',
                        CASE_NUMBER=i,
                        TEST_INPUT=test_case['input'],
                        TEST_OUTPUT=test_case['output']
                    )
                
                if not test_cases_html:
                    test_cases_html = '<div class="no-test-cases">此題目尚無測試案例</div>'
                
                # 渲染模板
                template_content = render_main_template(
                    'templates/problem_detail.html',
                    PROBLEM_NAME=problem_details['name'],
                    PROBLEM_ID=problem_details['name'],
                    PROBLEM_DESCRIPTION=problem_details['description'],
                    TEST_CASES_HTML=test_cases_html,
                    TEST_CASES_COUNT=len(problem_details['test_cases'])
                )
                
                # 发送响应
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(template_content.encode('utf-8'))
                return
            except FileNotFoundError:
                self.send_error(404, "Problem detail template not found")
        elif urllib.parse.urlparse(self.path).path.startswith('/admin/edit-problem/'):
            # 编辑题目页面
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'teacher':
                # 未登录或不是老师，重定向到老师登录页面
                self.send_response(302)
                self.send_header('Location', '/teacher')
                self.end_headers()
                return
            
            # 提取题目名称
            parsed_path = urllib.parse.urlparse(self.path).path
            problem_name = parsed_path.split('/admin/edit-problem/', 1)[1]
            if not problem_name:
                self.send_error(400, "Missing problem name")
                return
            
            # 获取题目详情
            problem_details = get_problem_details(problem_name)
            if not problem_details:
                self.send_error(404, "Problem not found")
                return
            
            # 读取题目编辑模板
            try:
                # 构建测试案例输入框HTML
                test_cases_html = ""
                for i, test_case in enumerate(problem_details['test_cases']):
                    test_cases_html += render_template_component(
                        'test_case_edit',
                        CASE_NUMBER=i + 1,
                        CASE_INDEX=i,
                        TEST_INPUT=test_case['input'],
                        TEST_OUTPUT=test_case['output']
                    )
                
                # 渲染模板
                template_content = render_main_template(
                    'templates/problem_edit.html',
                    PROBLEM_NAME=problem_details['name'],
                    PROBLEM_ID=problem_details['name'],
                    PROBLEM_DESCRIPTION=problem_details['description'],
                    TEST_CASES_HTML=test_cases_html,
                    TEST_CASES_COUNT=len(problem_details['test_cases'])
                )
                
                # 发送响应
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(template_content.encode('utf-8'))
                return
            except FileNotFoundError:
                self.send_error(404, "Problem edit template not found")
        elif urllib.parse.urlparse(self.path).path == '/admin/students':
            # 学生管理页面
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'teacher':
                # 未登录或不是老师，重定向到老师登录页面
                self.send_response(302)
                self.send_header('Location', '/teacher')
                self.end_headers()
                return
            
            # 获取学生列表
            students = get_all_students()
            
            # 生成学生列表HTML
            if students:
                students_html = ""
                for student in students:
                    student_id, grade, class_num, username, password = student
                    students_html += f"""
                    <tr>
                        <td>{student_id}</td>
                        <td>{grade}</td>
                        <td>{class_num}</td>
                        <td>{username}</td>
                        <td>
                            <span class="password-cell" data-password="{password}">••••••</span>
                            <span class="password-toggle">显示</span>
                        </td>
                        <td>
                            <a href="/admin/edit-student/{student_id}" class="btn btn-edit">编辑</a>
                            <a href="/admin/delete-student/{student_id}" class="btn btn-delete" 
                               onclick="return confirm('确定要删除学生 {username} 吗？这将删除该学生的所有相关数据。')">删除</a>
                        </td>
                    </tr>
                    """
            else:
                students_html = '<tr><td colspan="6" class="no-students">目前没有任何学生</td></tr>'
            
            # 读取学生管理模板并替换占位符
            try:
                with open('templates/student_management.html', 'r', encoding='utf-8') as f:
                    template_content = f.read()
                
                # 替换占位符
                template_content = template_content.replace('{{STUDENTS_LIST}}', students_html)
                
                # 发送自定义的 HTML 响应
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(template_content.encode('utf-8'))
                return
            except FileNotFoundError:
                self.send_error(404, "Student management template not found")
        elif urllib.parse.urlparse(self.path).path.startswith('/admin/edit-student/'):
            # 编辑学生页面
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'teacher':
                # 未登录或不是老师，重定向到老师登录页面
                self.send_response(302)
                self.send_header('Location', '/teacher')
                self.end_headers()
                return
            
            # 提取学生ID
            parsed_path = urllib.parse.urlparse(self.path).path
            student_id = parsed_path.split('/admin/edit-student/', 1)[1]
            if not student_id or not student_id.isdigit():
                self.send_error(400, "Invalid student ID")
                return
            
            # 获取学生信息
            student = get_student_by_id(int(student_id))
            if not student:
                self.send_error(404, "Student not found")
                return
            
            student_id, grade, class_num, username, password = student
            
            # 读取学生编辑模板
            try:
                with open('templates/student_edit.html', 'r', encoding='utf-8') as f:
                    template_content = f.read()
                
                # 替换占位符
                template_content = template_content.replace('{{STUDENT_ID}}', str(student_id))
                template_content = template_content.replace('{{STUDENT_GRADE}}', grade)
                template_content = template_content.replace('{{STUDENT_CLASS}}', class_num)
                template_content = template_content.replace('{{STUDENT_USERNAME}}', username)
                
                # 发送响应
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(template_content.encode('utf-8'))
                return
            except FileNotFoundError:
                self.send_error(404, "Student edit template not found")
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
        
        # 檢查是否為題目上傳請求
        elif self.path == '/admin/upload-problem':
            # 验证老师身份
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'teacher':
                # 未登录或不是老师，重定向到老师登录页面
                self.send_response(302)
                self.send_header('Location', '/teacher')
                self.end_headers()
                return
            
            try:
                # 解析 multipart/form-data
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={'REQUEST_METHOD': 'POST',
                            'CONTENT_TYPE': self.headers['Content-Type']}
                )
                
                # 获取题目编号
                problem_id = form.getvalue('problem_id')
                if not problem_id or not problem_id.isdigit():
                    self.send_response(302)
                    self.send_header('Location', '/admin/problems?error=請輸入有效的題目編號')
                    self.end_headers()
                    return
                
                # 获取描述文件
                if 'description' not in form:
                    self.send_response(302)
                    self.send_header('Location', '/admin/problems?error=請上傳題目描述檔案')
                    self.end_headers()
                    return
                
                description_file = form['description']
                if not description_file.filename:
                    self.send_response(302)
                    self.send_header('Location', '/admin/problems?error=請選擇題目描述檔案')
                    self.end_headers()
                    return
                
                # 获取测试文件
                if 'test_files' not in form:
                    self.send_response(302)
                    self.send_header('Location', '/admin/problems?error=請上傳測試點檔案')
                    self.end_headers()
                    return
                
                test_files = form['test_files']
                if not isinstance(test_files, list):
                    test_files = [test_files]
                
                # 过滤空文件
                test_files = [f for f in test_files if f.filename]
                
                if not test_files:
                    self.send_response(302)
                    self.send_header('Location', '/admin/problems?error=請選擇測試點檔案')
                    self.end_headers()
                    return
                
                # 保存题目
                success, message = save_uploaded_problem(problem_id, description_file, test_files)
                
                if success:
                    self.send_response(302)
                    self.send_header('Location', '/admin/problems?success=1')
                    self.end_headers()
                else:
                    error_msg = urllib.parse.quote(message, safe='', encoding='utf-8')
                    self.send_response(302)
                    self.send_header('Location', f'/admin/problems?error={error_msg}')
                    self.end_headers()
                
            except Exception as e:
                error_msg = urllib.parse.quote(f"上傳失敗：{str(e)}", safe='', encoding='utf-8')
                self.send_response(302)
                self.send_header('Location', f'/admin/problems?error={error_msg}')
                self.end_headers()
        
        # 檢查是否為編輯題目請求
        elif urllib.parse.urlparse(self.path).path.startswith('/admin/edit-problem/'):
            # 验证老师身份
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'teacher':
                # 未登录或不是老师，重定向到老师登录页面
                self.send_response(302)
                self.send_header('Location', '/teacher')
                self.end_headers()
                return
            
            # 提取题目名称
            parsed_path = urllib.parse.urlparse(self.path).path
            problem_name = parsed_path.split('/admin/edit-problem/', 1)[1]
            if not problem_name:
                self.send_response(302)
                self.send_header('Location', '/admin/problems?error=無效的題目名稱')
                self.end_headers()
                return
            
            try:
                # 解析表单数据
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                post_data_str = post_data.decode('utf-8')
                parsed_data = urllib.parse.parse_qs(post_data_str)
                
                description = parsed_data.get('description', [''])[0]
                if not description:
                    self.send_response(302)
                    self.send_header('Location', f'/admin/edit-problem/{problem_name}?error=請填寫題目描述')
                    self.end_headers()
                    return
                
                # 收集测试案例
                test_cases = []
                i = 0
                while f'test_input_{i}' in parsed_data and f'test_output_{i}' in parsed_data:
                    test_input = parsed_data[f'test_input_{i}'][0].strip()
                    test_output = parsed_data[f'test_output_{i}'][0].strip()
                    if test_input and test_output:  # 只添加非空的测试案例
                        test_cases.append({
                            'input': test_input,
                            'output': test_output
                        })
                    i += 1
                
                # 更新题目
                success, message = update_problem(problem_name, description, test_cases)
                
                if success:
                    success_msg = urllib.parse.quote("題目更新成功", safe='', encoding='utf-8')
                    self.send_response(302)
                    self.send_header('Location', f'/admin/view-problem/{problem_name}?success={success_msg}')
                    self.end_headers()
                else:
                    error_msg = urllib.parse.quote(message, safe='', encoding='utf-8')
                    self.send_response(302)
                    self.send_header('Location', f'/admin/edit-problem/{problem_name}?error={error_msg}')
                    self.end_headers()
                
            except Exception as e:
                error_msg = urllib.parse.quote(f"更新失敗：{str(e)}", safe='', encoding='utf-8')
                self.send_response(302)
                self.send_header('Location', f'/admin/edit-problem/{problem_name}?error={error_msg}')
                self.end_headers()
        
        # 檢查是否為刪除題目請求
        elif urllib.parse.urlparse(self.path).path.startswith('/admin/delete-problem/'):
            # 验证老师身份
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'teacher':
                # 未登录或不是老师，重定向到老师登录页面
                self.send_response(302)
                self.send_header('Location', '/teacher')
                self.end_headers()
                return
            
            # 提取题目名称
            parsed_path = urllib.parse.urlparse(self.path).path
            problem_name = parsed_path.split('/admin/delete-problem/', 1)[1]
            if not problem_name:
                self.send_response(302)
                self.send_header('Location', '/admin/problems?error=無效的題目名稱')
                self.end_headers()
                return
            
            try:
                # 删除题目
                success, message = delete_problem(problem_name)
                
                if success:
                    success_msg = urllib.parse.quote("題目刪除成功", safe='', encoding='utf-8')
                    self.send_response(302)
                    self.send_header('Location', f'/admin/problems?success={success_msg}')
                    self.end_headers()
                else:
                    error_msg = urllib.parse.quote(message, safe='', encoding='utf-8')
                    self.send_response(302)
                    self.send_header('Location', f'/admin/problems?error={error_msg}')
                    self.end_headers()
                
            except Exception as e:
                error_msg = urllib.parse.quote(f"刪除失敗：{str(e)}", safe='', encoding='utf-8')
                self.send_response(302)
                self.send_header('Location', f'/admin/problems?error={error_msg}')
                self.end_headers()
        
        # 检查是否为编辑学生请求
        elif urllib.parse.urlparse(self.path).path.startswith('/admin/edit-student/'):
            # 验证老师身份
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'teacher':
                # 未登录或不是老师，重定向到老师登录页面
                self.send_response(302)
                self.send_header('Location', '/teacher')
                self.end_headers()
                return
            
            # 提取学生ID
            parsed_path = urllib.parse.urlparse(self.path).path
            student_id = parsed_path.split('/admin/edit-student/', 1)[1]
            if not student_id or not student_id.isdigit():
                self.send_response(302)
                self.send_header('Location', '/admin/students?error=無效的學生ID')
                self.end_headers()
                return
            
            try:
                # 解析表单数据
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                post_data_str = post_data.decode('utf-8')
                parsed_data = urllib.parse.parse_qs(post_data_str)
                
                grade = parsed_data.get('grade', [''])[0].strip()
                class_num = parsed_data.get('class_num', [''])[0].strip()
                username = parsed_data.get('username', [''])[0].strip()
                password = parsed_data.get('password', [''])[0].strip()
                
                if not grade or not class_num or not username:
                    self.send_response(302)
                    self.send_header('Location', f'/admin/edit-student/{student_id}?error=年級、班級和用戶名不能為空')
                    self.end_headers()
                    return
                
                # 更新学生信息
                success, message = update_student(int(student_id), grade, class_num, username, password if password else None)
                
                if success:
                    success_msg = urllib.parse.quote("學生信息更新成功", safe='', encoding='utf-8')
                    self.send_response(302)
                    self.send_header('Location', f'/admin/students?success={success_msg}')
                    self.end_headers()
                else:
                    error_msg = urllib.parse.quote(message, safe='', encoding='utf-8')
                    self.send_response(302)
                    self.send_header('Location', f'/admin/edit-student/{student_id}?error={error_msg}')
                    self.end_headers()
                
            except Exception as e:
                error_msg = urllib.parse.quote(f"更新失敗：{str(e)}", safe='', encoding='utf-8')
                self.send_response(302)
                self.send_header('Location', f'/admin/edit-student/{student_id}?error={error_msg}')
                self.end_headers()
        
        # 检查是否为删除学生请求
        elif urllib.parse.urlparse(self.path).path.startswith('/admin/delete-student/'):
            # 验证老师身份
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'teacher':
                # 未登录或不是老师，重定向到老师登录页面
                self.send_response(302)
                self.send_header('Location', '/teacher')
                self.end_headers()
                return
            
            # 提取学生ID
            parsed_path = urllib.parse.urlparse(self.path).path
            student_id = parsed_path.split('/admin/delete-student/', 1)[1]
            if not student_id or not student_id.isdigit():
                self.send_response(302)
                self.send_header('Location', '/admin/students?error=無效的學生ID')
                self.end_headers()
                return
            
            try:
                # 删除学生
                success, message = delete_student(int(student_id))
                
                if success:
                    success_msg = urllib.parse.quote(message, safe='', encoding='utf-8')
                    self.send_response(302)
                    self.send_header('Location', f'/admin/students?success={success_msg}')
                    self.end_headers()
                else:
                    error_msg = urllib.parse.quote(message, safe='', encoding='utf-8')
                    self.send_response(302)
                    self.send_header('Location', f'/admin/students?error={error_msg}')
                    self.end_headers()
                
            except Exception as e:
                error_msg = urllib.parse.quote(f"刪除失敗：{str(e)}", safe='', encoding='utf-8')
                self.send_response(302)
                self.send_header('Location', f'/admin/students?error={error_msg}')
                self.end_headers()
        
        else:
            self.send_error(404, "Not Found")

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

if __name__ == '__main__':
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