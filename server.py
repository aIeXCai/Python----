import http.server, socketserver, urllib.parse, os
import sqlite3, subprocess, glob, datetime
import uuid, time

PORT = 8000
# 使用绝对路径确保数据库文件在正确位置
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.db')

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
    # 建立 users 表格，包含 role 字段以区分学生/老师
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            grade TEXT NOT NULL,
            class_num TEXT NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
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
            FOREIGN KEY (grade, class_num, username) REFERENCES users (grade, class_num, username)
        )
    ''')
    conn.commit()
    # 兼容旧数据库：尝试添加 student_number 字段并创建班级内学号唯一索引
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN student_number TEXT")
    except Exception:
        # 已存在或无法添加时忽略
        pass

    try:
        # 创建索引以保证 (grade, class_num, student_number) 唯一
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_grade_class_stuno ON users(grade, class_num, student_number)")
    except Exception:
        pass

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
def register_user(grade, class_num, username, password, student_number=None):
    """注册新用户，支持可选的 student_number"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        # 如果 users 表有 student_number 列则插入该字段
        cursor.execute("PRAGMA table_info(users)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'student_number' in cols:
            cursor.execute("INSERT INTO users (grade, class_num, student_number, username, password) VALUES (?, ?, ?, ?, ?)", 
                           (grade, class_num, student_number, username, password))
        else:
            cursor.execute("INSERT INTO users (grade, class_num, username, password) VALUES (?, ?, ?, ?)", 
                           (grade, class_num, username, password))

        conn.commit()
        conn.close()
        return True, "注册成功！"
    except sqlite3.IntegrityError as ie:
        conn.close()
        msg = str(ie)
        if 'idx_users_grade_class_stuno' in msg or 'student_number' in msg:
            return False, f"该班级中学号 '{student_number}' 已被使用，请选择其他学号。"
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
    # 使用绝对路径确保能找到problems目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    problems_dir = os.path.join(script_dir, 'problems')
    problems = []
    
    print(f"[DEBUG] 查找题目目录: {problems_dir}")
    print(f"[DEBUG] 目录是否存在: {os.path.exists(problems_dir)}")
    
    if os.path.exists(problems_dir):
        for item in os.listdir(problems_dir):
            item_path = os.path.join(problems_dir, item)
            if os.path.isdir(item_path) and item.startswith('problem'):
                # 检查题目文件夹中是否有必要的文件
                description_file = os.path.join(item_path, 'description.txt')
                
                # 首先检查tests子目录下的测试文件
                tests_dir = os.path.join(item_path, 'tests')
                if os.path.exists(tests_dir):
                    input_files = glob.glob(os.path.join(tests_dir, 'input*.txt'))
                    output_files = glob.glob(os.path.join(tests_dir, 'output*.txt'))
                else:
                    # 如果没有tests子目录，检查直接在问题目录下的文件
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
    # 使用绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    problem_dir = os.path.join(script_dir, 'problems', f'problem{problem_id}')
    
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
    # 使用绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    problem_dir = os.path.join(script_dir, 'problems', problem_name)
    
    print(f"[DEBUG] 查找题目详情: {problem_dir}")
    print(f"[DEBUG] 目录是否存在: {os.path.exists(problem_dir)}")
    
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
    
    # 读取测试点 - 优先从tests子目录读取
    tests_dir = os.path.join(problem_dir, 'tests')
    if os.path.exists(tests_dir):
        input_files = sorted(glob.glob(os.path.join(tests_dir, 'input*.txt')))
        output_files = sorted(glob.glob(os.path.join(tests_dir, 'output*.txt')))
    else:
        # 如果没有tests子目录，从问题根目录读取
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
    # 使用绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    problem_dir = os.path.join(script_dir, 'problems', problem_name)
    
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
    # 检查 users 表中是否存在 student_number 字段，兼容旧数据库
    cursor.execute("PRAGMA table_info(users)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'student_number' in cols:
        cursor.execute("SELECT id, grade, class_num, student_number, username, password FROM users ORDER BY grade, class_num, student_number, username")
        students = cursor.fetchall()
    else:
        cursor.execute("SELECT id, grade, class_num, username, password FROM users ORDER BY grade, class_num, username")
        rows = cursor.fetchall()
        # 在缺少 student_number 的旧表上使用占位符 '-'
        students = [(r[0], r[1], r[2], '-', r[3], r[4]) for r in rows]
    conn.close()
    return students

# 根据ID获取学生信息
def get_student_by_id(student_id):
    """根据ID获取学生信息"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 检查是否有 student_number 字段
    cursor.execute("PRAGMA table_info(users)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'student_number' in cols:
        cursor.execute("SELECT id, grade, class_num, student_number, username, password FROM users WHERE id=?", (student_id,))
        student = cursor.fetchone()
    else:
        cursor.execute("SELECT id, grade, class_num, username, password FROM users WHERE id=?", (student_id,))
        row = cursor.fetchone()
        student = (row[0], row[1], row[2], '-', row[3], row[4]) if row else None
    conn.close()
    return student

# 更新学生信息
def update_student(student_id, grade, class_num, username, password=None, student_number=None):
    """更新学生信息，支持更新 student_number"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        # 判断 users 表是否有 student_number 字段
        cursor.execute("PRAGMA table_info(users)")
        cols = [row[1] for row in cursor.fetchall()]

        if 'student_number' in cols:
            if password:
                cursor.execute(
                    "UPDATE users SET grade=?, class_num=?, student_number=?, username=?, password=? WHERE id=?",
                    (grade, class_num, student_number, username, password, student_id)
                )
            else:
                cursor.execute(
                    "UPDATE users SET grade=?, class_num=?, student_number=?, username=? WHERE id=?",
                    (grade, class_num, student_number, username, student_id)
                )
        else:
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

        # 同时更新 scores 表中的相关信息（如果学生信息变更）
        # 旧查询通过 users 表的旧值定位，直接使用 student_id 子查询来匹配并更新
        cursor.execute(
            "UPDATE scores SET grade=?, class_num=?, username=? WHERE grade=(SELECT grade FROM users WHERE id=?) AND class_num=(SELECT class_num FROM users WHERE id=?) AND username=(SELECT username FROM users WHERE id=?)",
            (grade, class_num, username, student_id, student_id, student_id)
        )

        conn.commit()
        conn.close()
        return True, "学生信息更新成功！"
    except sqlite3.IntegrityError as ie:
        conn.close()
        msg = str(ie)
        if 'idx_users_grade_class_stuno' in msg or 'student_number' in msg:
            return False, f"该班级中学号 '{student_number}' 已被使用，请选择其他学号。"
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
        print(f"[DEBUG] delete_student called with id={student_id}")
        print(f"[DEBUG] DB file: {DB_FILE}, exists: {os.path.exists(DB_FILE)}")
        # 先获取学生信息用于删除相关成绩记录
        cursor.execute("SELECT grade, class_num, username FROM users WHERE id=?", (student_id,))
        student_info = cursor.fetchone()
        print(f"[DEBUG] student_info fetched: {student_info}")
        
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
        print(f"[DEBUG] delete_student exception: {e}")
        conn.close()
        return False, f"删除失败：{str(e)}"


# <!-- 成绩管理相关函数 -->
def get_all_scores():
    """获取所有学生的最新成绩"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 获取每个学生每道题的最新成绩
    cursor.execute('''
        SELECT s.grade, s.class_num, s.username, s.problem_id, s.score, s.submission_time
        FROM scores s
        INNER JOIN (
            SELECT grade, class_num, username, problem_id, MAX(submission_time) as latest_time
            FROM scores
            GROUP BY grade, class_num, username, problem_id
        ) latest ON s.grade = latest.grade 
                AND s.class_num = latest.class_num 
                AND s.username = latest.username 
                AND s.problem_id = latest.problem_id 
                AND s.submission_time = latest.latest_time
        ORDER BY s.grade, s.class_num, s.username, s.problem_id
    ''')
    
    scores = cursor.fetchall()
    conn.close()
    return scores

def get_scores_by_filter(grade_filter=None, class_filter=None, problem_filter=None):
    """根据条件筛选成绩"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 构建查询条件
    where_conditions = []
    params = []
    
    if grade_filter:
        where_conditions.append("grade = ?")
        params.append(grade_filter)
    
    if class_filter:
        where_conditions.append("class_num = ?")
        params.append(class_filter)
    
    if problem_filter:
        where_conditions.append("problem_id = ?")
        # 尝试将传入的 problem_filter 转为整数，以匹配 scores.problem_id
        try:
            pf = int(problem_filter)
        except Exception:
            pf = problem_filter
        params.append(pf)
    
    where_clause = ""
    if where_conditions:
        where_clause = "WHERE " + " AND ".join(where_conditions)
    
    query = f'''
        SELECT s.grade, s.class_num, s.username, s.problem_id, s.score, s.submission_time
        FROM scores s
        INNER JOIN (
            SELECT grade, class_num, username, problem_id, MAX(submission_time) as latest_time
            FROM scores
            {where_clause}
            GROUP BY grade, class_num, username, problem_id
        ) latest ON s.grade = latest.grade 
                AND s.class_num = latest.class_num 
                AND s.username = latest.username 
                AND s.problem_id = latest.problem_id 
                AND s.submission_time = latest.latest_time
    '''
    
    if where_conditions:
        # 为主查询添加相同的WHERE条件
        main_where = " AND ".join([f"s.{cond}" for cond in where_conditions])
        query += f" WHERE {main_where}"
        params_final = params + params  # 子查询和主查询都需要参数
    else:
        params_final = []
    
    query += " ORDER BY s.grade, s.class_num, s.username, s.problem_id"
    
    cursor.execute(query, params_final)
    scores = cursor.fetchall()
    conn.close()
    return scores

def get_grade_class_options():
    """获取所有年级班级选项"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 获取所有年级
    cursor.execute("SELECT DISTINCT grade FROM users ORDER BY grade")
    grades = [row[0] for row in cursor.fetchall()]
    
    # 获取所有班级
    cursor.execute("SELECT DISTINCT class_num FROM users ORDER BY class_num")
    classes = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return grades, classes

def get_problem_options():
    """获取所有题目选项"""
    problems_data = get_problems_list()
    options = []
    for problem in problems_data:
        name = problem.get('name', '')
        # 从 'problemX' 中提取数字 X
        try:
            num = int(name.replace('problem', ''))
            options.append(num)
        except Exception:
            # 回退：保留原始名称
            options.append(name)
    return options




# <!-- 学生答题系统相关函数 -->
# 获取学生某道题目的完成状态
def get_student_problem_status(grade, class_num, username):
    """获取学生的题目完成状态"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 获取学生所有题目的最高分数
    cursor.execute('''
        SELECT problem_id, MAX(score) as best_score, COUNT(*) as attempts
        FROM scores 
        WHERE grade=? AND class_num=? AND username=?
        GROUP BY problem_id
    ''', (grade, class_num, username))
    
    student_scores = {}
    for row in cursor.fetchall():
        problem_id, best_score, attempts = row
        student_scores[problem_id] = {
            'best_score': best_score,
            'attempts': attempts,
            'status': 'status-completed' if best_score >= 80 else 'status-attempted'
        }
    
    conn.close()
    return student_scores

# 获取学生某题目的提交历史
def get_student_submissions(grade, class_num, username, problem_id):
    """获取学生某题目的提交历史"""
    print(f"[DEBUG] 查询提交记录: grade={grade}, class={class_num}, user={username}, problem={problem_id}")
    print(f"[DEBUG] 数据库文件: {DB_FILE}")
    print(f"[DEBUG] 数据库文件存在: {os.path.exists(DB_FILE)}")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT score, submission_time
        FROM scores 
        WHERE grade=? AND class_num=? AND username=? AND problem_id=?
        ORDER BY submission_time DESC
        LIMIT 10
    ''', (grade, class_num, username, problem_id))
    
    submissions = []
    for row in cursor.fetchall():
        score, submission_time = row
        submissions.append({
            'score': score,
            'submitTime': submission_time,
            'fileName': f'problem{problem_id}.py'  # 使用固定的文件名格式
        })
    
    conn.close()
    return submissions

# 获取管理后台统计数据
def get_admin_statistics():
    """获取管理后台的统计数据"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 获取注册学生数（仅统计 role='student'）
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'student'")
    total_students = cursor.fetchone()[0]
    
    # 获取可用题目数
    problems = get_problems_list()
    total_problems = len(problems)
    
    # 获取今日提交数
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) FROM scores WHERE DATE(submission_time) = ?", (today,))
    today_submissions = cursor.fetchone()[0]
    
    # 获取平均成绩
    cursor.execute('''
        SELECT AVG(max_scores.best_score) as avg_score
        FROM (
            SELECT MAX(score) as best_score
            FROM scores 
            GROUP BY grade, class_num, username, problem_id
        ) as max_scores
    ''')
    
    avg_result = cursor.fetchone()[0]
    avg_score = round(avg_result, 1) if avg_result else 0
    
    conn.close()
    
    return {
        'total_students': total_students,
        'total_problems': total_problems,
        'today_submissions': today_submissions,
        'avg_score': avg_score
    }

# 获取学生的学习统计数据
def get_student_statistics(grade, class_num, username):
    """获取学生的学习统计数据"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 获取总题目数
    problems = get_problems_list()
    total_problems = len(problems)
    
    # 获取已完成题目数（得分>=80分）
    cursor.execute('''
        SELECT COUNT(DISTINCT problem_id) as completed
        FROM scores 
        WHERE grade=? AND class_num=? AND username=? AND score >= 80
    ''', (grade, class_num, username))
    completed_problems = cursor.fetchone()[0]
    
    # 获取平均分
    cursor.execute('''
        SELECT AVG(max_scores.best_score) as avg_score
        FROM (
            SELECT problem_id, MAX(score) as best_score
            FROM scores 
            WHERE grade=? AND class_num=? AND username=?
            GROUP BY problem_id
        ) max_scores
    ''', (grade, class_num, username))
    avg_result = cursor.fetchone()[0]
    average_score = round(avg_result, 1) if avg_result else 0
    
    # 获取班级排名（基于平均分）
    cursor.execute('''
        SELECT COUNT(*) + 1 as rank
        FROM (
            SELECT username, AVG(max_scores.best_score) as student_avg
            FROM (
                SELECT username, problem_id, MAX(score) as best_score
                FROM scores 
                WHERE grade=? AND class_num=? AND username != ?
                GROUP BY username, problem_id
            ) max_scores
            GROUP BY username
            HAVING student_avg > ?
        ) rankings
    ''', (grade, class_num, username, average_score))
    rank = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_problems': total_problems,
        'completed_problems': completed_problems,
        'average_score': average_score,
        'rank': rank
    }

# 保存学生提交记录
def save_student_submission(grade, class_num, username, problem_id, score, submission_time):
    """保存学生提交记录到数据库"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO scores (grade, class_num, username, problem_id, score, submission_time)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (grade, class_num, username, problem_id, score, submission_time))
    
    conn.commit()
    conn.close()


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
    def generate_filter_options(self, options, selected_value, default_text, is_problem=False):
        """生成筛选下拉的 HTML 片段

        参数:
          options: 可迭代的选项（数字或字符串）
          selected_value: 当前选中值
          default_text: 默认选项文本
          is_problem: 如果为 True，数字选项会显示为 '题目X'
        """
        html = f'<option value="">{default_text}</option>'
        for opt in options:
            val = opt
            try:
                is_int = isinstance(opt, int) or (isinstance(opt, str) and str(opt).isdigit())
            except Exception:
                is_int = False

            if is_problem and is_int:
                try:
                    label = f'题目{int(opt)}'
                except Exception:
                    label = str(opt)
            else:
                label = str(opt)

            selected = ' selected' if str(opt) == str(selected_value) else ''
            html += f'<option value="{val}"{selected}>{label}</option>'
        return html
    
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
                # 获取统计数据
                stats = get_admin_statistics()
                print(f"[DEBUG] 获取到的统计数据: {stats}")
                
                with open('templates/admin_dashboard.html', 'r', encoding='utf-8') as f:
                    admin_content = f.read()
                
                # 替换占位符
                admin_content = admin_content.replace('{{USERNAME}}', user_data['username'])
                
                # 替换统计数据占位符
                admin_content = admin_content.replace('{{TOTAL_STUDENTS}}', str(stats['total_students']))
                admin_content = admin_content.replace('{{TOTAL_PROBLEMS}}', str(stats['total_problems']))
                admin_content = admin_content.replace('{{TODAY_SUBMISSIONS}}', str(stats['today_submissions']))
                admin_content = admin_content.replace('{{AVG_SCORE}}', f"{stats['avg_score']}%")
                print(f"[DEBUG] 模板替换完成")
                
                # 发送自定义的 HTML 响应
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(admin_content.encode('utf-8'))
                return
            except FileNotFoundError:
                print("[DEBUG] 模板文件未找到")
                self.send_error(404, "Admin dashboard template not found")
            except Exception as e:
                print(f"[DEBUG] 处理管理后台时出错: {e}")
                self.send_error(500, f"Error processing admin dashboard: {e}")
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
        elif urllib.parse.urlparse(self.path).path.startswith('/admin/delete-student/'):
            # 处理通过 GET 点击删除学生的请求（链接使用 GET）
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)

            if not user_data or user_data.get('role') != 'teacher':
                # 未登录或不是老师，重定向到老师登录页面
                self.send_response(302)
                self.send_header('Location', '/teacher')
                self.end_headers()
                return

            # 提取学生ID并校验
            parsed_path = urllib.parse.urlparse(self.path).path
            student_id = parsed_path.split('/admin/delete-student/', 1)[1]
            if not student_id or not student_id.isdigit():
                self.send_response(302)
                self.send_header('Location', '/admin/students?error=无效的学生ID')
                self.end_headers()
                return

            try:
                success, message = delete_student(int(student_id))
                if success:
                    # 删除成功：把后端返回的消息 URL 编码放到 success 参数，前端会显示该消息
                    success_msg = urllib.parse.quote(message, safe='', encoding='utf-8')
                    self.send_response(302)
                    self.send_header('Location', f'/admin/students?success={success_msg}')
                    self.end_headers()
                    return
                else:
                    error_msg = urllib.parse.quote(message, safe='', encoding='utf-8')
                    self.send_response(302)
                    self.send_header('Location', f'/admin/students?error={error_msg}')
                    self.end_headers()
                    return
            except Exception as e:
                error_msg = urllib.parse.quote(str(e), safe='', encoding='utf-8')
                self.send_response(302)
                self.send_header('Location', f'/admin/students?error={error_msg}')
                self.end_headers()
                return
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
                    # student tuple: (id, grade, class_num, student_number, username, password)
                    student_id, grade, class_num, student_number, username, password = student
                    students_html += f"""
                    <tr>
                        <td>{student_id}</td>
                        <td>{student_number}</td>
                        <td>{grade}</td>
                        <td>{class_num}</td>
                        <td>{username}</td>
                        <td>
                            <span class=\"password-cell\" data-password=\"{password}\">••••••</span>
                            <span class=\"password-toggle\">显示</span>
                        </td>
                        <td>
                            <a href=\"/admin/edit-student/{student_id}\" class=\"btn btn-edit\">编辑</a>
                            <a href=\"/admin/delete-student/{student_id}\" class=\"btn btn-delete\" 
                               onclick=\"return confirm('确定要删除学生 {username} 吗？这将删除该学生的所有相关数据。')\">删除</a>
                        </td>
                    </tr>
                    """
            else:
                students_html = '<tr><td colspan="7" class="no-students">目前没有任何学生</td></tr>'
            
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
        elif urllib.parse.urlparse(self.path).path == '/admin/scores':
            # 成绩管理页面
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'teacher':
                # 未登录或不是老师，重定向到老师登录页面
                self.send_response(302)
                self.send_header('Location', '/teacher')
                self.end_headers()
                return
            
            # 解析查询参数
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            print(f"[DEBUG] /admin/scores query string: {parsed_url.query}")
            print(f"[DEBUG] /admin/scores parsed query params: {query_params}")
            
            grade_filter = query_params.get('grade', [None])[0]
            class_filter = query_params.get('class', [None])[0]
            problem_filter = query_params.get('problem', [None])[0]
            print(f"[DEBUG] /admin/scores filters -> grade: {grade_filter}, class: {class_filter}, problem: {problem_filter}")
            
            # 获取筛选选项
            grades, classes = get_grade_class_options()
            problems = get_problem_options()
            
            # 获取成绩数据
            if grade_filter or class_filter or problem_filter:
                scores = get_scores_by_filter(grade_filter, class_filter, problem_filter)
            else:
                scores = get_all_scores()
            
            # 构建成绩表格数据
            # 先组织数据结构：{学生: {题目: 分数}}
            score_matrix = {}
            all_problems = set()
            all_students = set()
            
            for score in scores:
                grade, class_num, username, problem_id, score_value, submission_time = score
                student_key = f"{grade}-{class_num}-{username}"
                all_students.add(student_key)
                all_problems.add(problem_id)
                
                if student_key not in score_matrix:
                    score_matrix[student_key] = {}
                score_matrix[student_key][problem_id] = {
                    'score': score_value,
                    'time': submission_time
                }
            
            # 生成表格HTML
            scores_html = self.generate_scores_table(score_matrix, sorted(all_students), sorted(all_problems))
            
            # 生成筛选选项HTML
            grade_options = self.generate_filter_options(grades, grade_filter, "全部年级")
            class_options = self.generate_filter_options(classes, class_filter, "全部班级")
            # 对题目选项单独传入 is_problem=True，以便显示为 "题目X"
            problem_options = self.generate_filter_options(problems, problem_filter, "全部题目", is_problem=True)
            
            # 读取成绩管理模板
            try:
                with open('templates/score_management.html', 'r', encoding='utf-8') as f:
                    template_content = f.read()
                
                # 替换占位符
                template_content = template_content.replace('{{SCORES_TABLE}}', scores_html)
                template_content = template_content.replace('{{GRADE_OPTIONS}}', grade_options)
                template_content = template_content.replace('{{CLASS_OPTIONS}}', class_options)
                template_content = template_content.replace('{{PROBLEM_OPTIONS}}', problem_options)
                # 注入总学生数（仅统计 role='student'）
                try:
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'student'")
                    total_students = cursor.fetchone()[0]
                    conn.close()
                except Exception:
                    total_students = 0
                template_content = template_content.replace('{{TOTAL_STUDENTS}}', str(total_students))
                
                # 发送响应
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(template_content.encode('utf-8'))
                return
            except FileNotFoundError:
                self.send_error(404, "Score management template not found")
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
            
            # student tuple: (id, grade, class_num, student_number, username, password)
            student_id, grade, class_num, student_number, username, password = student
            
            # 读取学生编辑模板
            try:
                with open('templates/student_edit.html', 'r', encoding='utf-8') as f:
                    template_content = f.read()
                
                # 替换占位符
                template_content = template_content.replace('{{STUDENT_ID}}', str(student_id))
                template_content = template_content.replace('{{STUDENT_GRADE}}', grade)
                template_content = template_content.replace('{{STUDENT_CLASS}}', class_num)
                template_content = template_content.replace('{{STUDENT_USERNAME}}', username)
                template_content = template_content.replace('{{STUDENT_NUMBER}}', str(student_number) if student_number is not None else '')
                
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
            
            print(f"[DEBUG] Dashboard request - session_id: {session_id}")
            print(f"[DEBUG] Dashboard request - user_data: {user_data}")
            
            if not user_data or user_data.get('role') != 'student':
                # 未登录或不是学生，重定向到登录页面
                print(f"[DEBUG] Dashboard - redirecting to login")
                self.send_response(302)
                self.send_header('Location', '/')
                self.end_headers()
                return
            
            # 获取题目列表和学生状态
            problems = get_problems_list()
            print(f"[DEBUG] Dashboard - found {len(problems)} problems")
            
            student_status = get_student_problem_status(
                user_data['grade'], user_data['class_num'], user_data['username']
            )
            
            # 生成题目列表HTML
            problems_html = ""
            if problems:
                for problem in problems:
                    problem_id = problem['name'].replace('problem', '')
                    status_info = student_status.get(int(problem_id), {})
                    status_class = status_info.get('status', 'status-new')
                    
                    problems_html += f'''
                    <div class="problem-item {status_class}" onclick="selectProblem('{problem_id}')">
                        <div class="problem-info">
                            <h4>題目 {problem_id}</h4>
                            <p>{problem['test_cases']} 個測試點</p>
                        </div>
                        <div class="problem-status {status_class}">
                            {'已完成' if status_class == 'status-completed' else '已嘗試' if status_class == 'status-attempted' else '未開始'}
                        </div>
                    </div>
                    '''
            else:
                problems_html = '<p style="text-align: center; color: #666; padding: 20px;">暫無題目</p>'
            
            # 读取 dashboard 模板并替换用户信息
            try:
                print(f"[DEBUG] Dashboard - reading template file")
                with open('templates/dashboard.html', 'r', encoding='utf-8') as f:
                    dashboard_content = f.read()
                
                print(f"[DEBUG] Dashboard - template file size: {len(dashboard_content)} characters")
                
                # 替换占位符
                dashboard_content = dashboard_content.replace('{{USERNAME}}', user_data['username'])
                dashboard_content = dashboard_content.replace('{{GRADE}}', user_data['grade'])
                dashboard_content = dashboard_content.replace('{{CLASS}}', user_data['class_num'])
                dashboard_content = dashboard_content.replace('{{PROBLEMS_LIST}}', problems_html)
                
                print(f"[DEBUG] Dashboard - after replacement: {len(dashboard_content)} characters")
                print(f"[DEBUG] Dashboard - problems_html length: {len(problems_html)} characters")
                
                # 发送自定义的 HTML 响应
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(dashboard_content.encode('utf-8'))
                print(f"[DEBUG] Dashboard - response sent successfully")
                return
            except FileNotFoundError:
                print(f"[ERROR] Dashboard template not found")
                self.send_error(404, "Dashboard template not found")
            except Exception as e:
                print(f"[ERROR] Dashboard template processing error: {e}")
                self.send_error(500, "Dashboard template processing error")
        elif self.path == '/api/problems':
            # API: 获取题目列表
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'student':
                self.send_response(401)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(b'{"error": "Unauthorized"}')
                return
            
            # 获取题目列表和学生状态
            problems = get_problems_list()
            student_status = get_student_problem_status(
                user_data['grade'], user_data['class_num'], user_data['username']
            )
            
            problems_data = []
            for problem in problems:
                problem_id = problem['name'].replace('problem', '')
                status_info = student_status.get(int(problem_id), {})
                
                problems_data.append({
                    'id': problem_id,
                    'title': f'題目 {problem_id}',
                    'difficulty': '中等',
                    'status': status_info.get('status', 'status-new'),
                    'testCases': problem['test_cases']
                })
            
            import json
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(problems_data, ensure_ascii=False).encode('utf-8'))
            return
        elif urllib.parse.urlparse(self.path).path.startswith('/api/problem/'):
            # API: 获取题目详情
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'student':
                self.send_response(401)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(b'{"error": "Unauthorized"}')
                return
            
            # 提取题目ID
            parsed_path = urllib.parse.urlparse(self.path).path
            problem_id = parsed_path.split('/api/problem/', 1)[1]
            
            problem_name = f'problem{problem_id}'
            problem_details = get_problem_details(problem_name)
            
            if not problem_details:
                self.send_response(404)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(b'{"error": "Problem not found"}')
                return
            
            # 构建测试案例数据
            test_cases = []
            for test_case in problem_details['test_cases']:
                test_cases.append({
                    'input': test_case['input'],
                    'output': test_case['output']
                })
            
            problem_data = {
                'id': problem_id,
                'title': f'題目 {problem_id}',
                'description': problem_details['description'],
                'testCases': test_cases
            }
            
            import json
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(problem_data, ensure_ascii=False).encode('utf-8'))
            return
        elif urllib.parse.urlparse(self.path).path.startswith('/api/submissions/'):
            # API: 获取学生提交历史
            cookies = parse_cookies(self.headers.get('Cookie', ''))
            session_id = cookies.get('session_id')
            user_data = get_user_from_session(session_id)
            
            if not user_data or user_data.get('role') != 'student':
                self.send_response(401)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(b'{"error": "Unauthorized"}')
                return
            
            # 提取题目ID
            parsed_path = urllib.parse.urlparse(self.path).path
            problem_id = parsed_path.split('/api/submissions/', 1)[1]
            
            submissions = get_student_submissions(
                user_data['grade'], user_data['class_num'], user_data['username'], int(problem_id)
            )
            
            import json
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(submissions, ensure_ascii=False).encode('utf-8'))
            return
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
        except FileNotFoundError as e:
            print(f"[404 ERROR] File not found for path: {self.path}")
            print(f"[404 ERROR] Working directory: {os.getcwd()}")
            print(f"[404 ERROR] Exception: {e}")
            self.send_error(404, "File Not Found")
        except ConnectionAbortedError:
            # 连接被客户端中断，静默处理
            print(f"[INFO] Connection aborted by client for path: {self.path}")
            pass
        except BrokenPipeError:
            # 管道断开错误，静默处理
            print(f"[INFO] Broken pipe for path: {self.path}")
            pass
        except Exception as e:
            # 其他异常，记录并发送500错误
            print(f"[ERROR] Unexpected error in do_GET for path {self.path}: {e}")
            try:
                self.send_error(500, "Internal Server Error")
            except:
                # 如果连发送错误响应都失败，就静默处理
                pass
            
    def do_POST(self):
        try:
            self._handle_post_request()
        except ConnectionAbortedError:
            # 连接被客户端中断，静默处理
            print(f"[INFO] Connection aborted by client for POST path: {self.path}")
            pass
        except BrokenPipeError:
            # 管道断开错误，静默处理
            print(f"[INFO] Broken pipe for POST path: {self.path}")
            pass
        except Exception as e:
            # 其他异常，记录并发送500错误
            print(f"[ERROR] Unexpected error in do_POST for path {self.path}: {e}")
            try:
                self.send_error(500, "Internal Server Error")
            except:
                # 如果连发送错误响应都失败，就静默处理
                pass
    
    def _handle_post_request(self):
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
                
                print(f"[INFO] 用户登录成功: {grade}-{class_num}-{username}, session: {session_id}")
                
                # 发送重定向响应，并设置 Cookie
                self.send_response(302)
                self.send_header('Location', '/dashboard.html')
                self.send_header('Set-Cookie', f'session_id={session_id}; Path=/; HttpOnly; Max-Age=7200')  # 2小时
                self.end_headers()
                return
            else:
                print(f"[INFO] 用户登录失败: {grade}-{class_num}-{username}")
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                error_message = f"年級、班級、帳號或密碼錯誤！請返回<a href='/'>登入頁面</a>重試。"
                self.wfile.write(error_message.encode('utf-8'))
                return
        
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
            student_number = parsed_data.get('student_number', [''])[0]
            if not grade or not class_num or not username or not password or not student_number:
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
            success, message = register_user(grade, class_num, username, password, student_number)
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
                # 返回JSON错误响应
                import json
                self.send_response(401)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "請先登入"}, ensure_ascii=False).encode('utf-8'))
                return
            
            # 注意：這裡不能先讀取 rfile，cgi.FieldStorage 需要直接從 rfile 解析 multipart/form-data
            try:
                import cgi
            except Exception:
                # 在 Python 3.13+ 中 cgi 模組被移除，给出友好提示
                import json
                self.send_response(500)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "message": "服务器当前 Python 环境不支持 multipart/form-data 解析 (缺少 cgi 模块)。请使用 Python 3.11/3.12 或在服务器端安装兼容解析库。"
                }, ensure_ascii=False).encode('utf-8'))
                return

            form = cgi.FieldStorage(
                fp=self.rfile, 
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST',
                        'CONTENT_TYPE': self.headers['Content-Type'],
                        })
            
            import json
            
            if 'codeFile' in form and 'problem_id' in form:
                file_item = form['codeFile']
                problem_id = form.getvalue('problem_id')
                
                if file_item.filename and problem_id:
                    try:
                        # 使用从 session 中获取的真实用户名和信息
                        username = user_data['username']
                        grade = user_data['grade']
                        class_num = user_data['class_num']
                        
                        # 生成唯一的文件名
                        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                        safe_filename = f"{username}_{problem_id}_{timestamp}_{file_item.filename}"
                        submission_path = os.path.join('submissions', safe_filename)
                        
                        # 保存文件
                        with open(submission_path, 'wb') as f:
                            f.write(file_item.file.read())
                        
                        # 批改代码
                        is_ok, grade_result = grade_submission(submission_path, int(problem_id))
                        
                        # 從回傳結果中提取分數
                        score_percentage = 0
                        if "得分率:" in grade_result:
                            try:
                                score_percentage = float(grade_result.split("得分率:")[1].split("%")[0].strip())
                            except (ValueError, IndexError):
                                pass
                        
                        # 將成績存入資料庫（允许多次提交）
                        save_student_submission(
                            grade, class_num, username, int(problem_id), 
                            score_percentage, 
                            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        )
                        
                        # 返回JSON成功响应
                        response_data = {
                            "success": True,
                            "message": "程式碼提交成功！",
                            "score": score_percentage,
                            "details": grade_result
                        }
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))
                        
                    except Exception as e:
                        # 返回JSON错误响应
                        response_data = {
                            "success": False,
                            "message": f"處理失敗：{str(e)}"
                        }
                        
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))
                else:
                    # 返回JSON错误响应
                    response_data = {
                        "success": False,
                        "message": "請選擇檔案並指定題目"
                    }
                    
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))
            else:
                # 返回JSON错误响应
                response_data = {
                    "success": False,
                    "message": "缺少必要的提交資料"
                }
                
                self.send_response(400)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))
        
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
                # 解析 multipart/form-data，延迟导入 cgi 并在缺失时返回友好错误
                try:
                    import cgi
                except Exception:
                    error_msg = urllib.parse.quote('服务器当前 Python 环境不支持 multipart/form-data 解析 (缺少 cgi 模块)', safe='', encoding='utf-8')
                    self.send_response(302)
                    self.send_header('Location', f'/admin/problems?error={error_msg}')
                    self.end_headers()
                    return

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
                student_number = parsed_data.get('student_number', [''])[0].strip()
                
                if not grade or not class_num or not username:
                    self.send_response(302)
                    self.send_header('Location', f'/admin/edit-student/{student_id}?error=年級、班級和用戶名不能為空')
                    self.end_headers()
                    return
                
                # 更新学生信息
                success, message = update_student(int(student_id), grade, class_num, username, password if password else None, student_number if student_number else None)
                
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
                    return
                else:
                    error_msg = urllib.parse.quote(message, safe='', encoding='utf-8')
                    self.send_response(302)
                    self.send_header('Location', f'/admin/students?error={error_msg}')
                    self.end_headers()
                    return
                
            except Exception as e:
                error_msg = urllib.parse.quote(f"刪除失敗：{str(e)}", safe='', encoding='utf-8')
                self.send_response(302)
                self.send_header('Location', f'/admin/students?error={error_msg}')
                self.end_headers()
                return
        
        else:
            self.send_error(404, "Not Found")

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()
    
    def log_message(self, format, *args):
        """重写日志方法，过滤连接错误消息"""
        message = format % args
        # 过滤掉常见的客户端断开连接错误
        if not any(error in message for error in ['ConnectionAbortedError', 'WinError 10053', 'BrokenPipeError']):
            super().log_message(format, *args)
    
    def safe_write(self, data):
        """安全地写入响应数据，处理连接断开错误"""
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            self.wfile.write(data)
            return True
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
            print(f"[INFO] Client disconnected during write for path: {self.path}")
            return False
        except Exception as e:
            print(f"[ERROR] Unexpected error during write for path {self.path}: {e}")
            return False
    
    def safe_send_response(self, code, message=None):
        """安全地发送HTTP响应，处理连接断开错误"""
        try:
            self.send_response(code, message)
            return True
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
            print(f"[INFO] Client disconnected during response for path: {self.path}")
            return False
        except Exception as e:
            print(f"[ERROR] Unexpected error during response for path {self.path}: {e}")
            return False

    def generate_scores_table(self, score_matrix, students, problems):
        """生成成绩表格HTML"""
        if not students or not problems:
            return '<tr><td colspan="100%" class="no-data">暂无成绩数据</td></tr>'

        # 表头（拆分学生信息为 年级 / 班级 / 学号 / 姓名）
        header_html = '<tr><th>年级</th><th>班级</th><th>学号</th><th>姓名</th>'
        for problem in problems:
            header_html += f'<th>{problem}</th>'
        header_html += '</tr>'

        # 表格内容
        rows_html = ''
        # 为了显示学号，从 users 表查询 student_number（兼容旧库若无此字段则显示 '-'）
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        for student in students:
            # student 格式通常为 'grade-class-username'
            try:
                grade, class_num, username = student.split('-')
            except Exception:
                # 容错：如果格式不符，直接显示原始字符串
                grade = class_num = ''
                username = student

            # 查询学号（可能不存在该列）
            try:
                cursor.execute("SELECT student_number FROM users WHERE grade=? AND class_num=? AND username=?", (grade, class_num, username))
                sn_row = cursor.fetchone()
                student_number = sn_row[0] if sn_row and sn_row[0] is not None else '-'
            except Exception:
                student_number = '-'

            # 列顺序：年级 / 班级 / 学号 / 姓名
            rows_html += f'<tr><td>{grade}</td>'
            rows_html += f'<td>{class_num}</td>'
            rows_html += f'<td>{student_number}</td>'
            rows_html += f'<td class="student-info">{username}</td>'

            for problem in problems:
                if student in score_matrix and problem in score_matrix[student]:
                    score_info = score_matrix[student][problem]
                    score = score_info['score']
                    time = score_info['time']

                    # 根据分数添加样式类
                    if score >= 90:
                        score_class = 'score-excellent'
                    elif score >= 80:
                        score_class = 'score-good'
                    elif score >= 60:
                        score_class = 'score-pass'
                    else:
                        score_class = 'score-fail'

                    rows_html += f'<td class="score-cell {score_class}" title="提交时间: {time}">{score:.1f}</td>'
                else:
                    rows_html += '<td class="score-cell score-empty">-</td>'

            rows_html += '</tr>'
        conn.close()

        return header_html + rows_html

    def generate_filter_options(self, options, selected_value, default_text, is_problem=False):
        """生成筛选下拉的 HTML 片段

        参数:
          options: 可迭代的选项（数字或字符串）
          selected_value: 当前选中值
          default_text: 默认选项文本
          is_problem: 如果为 True，数字选项会显示为 '题目X'
        """
        html = f'<option value="">{default_text}</option>'
        for opt in options:
            val = opt
            try:
                is_int = isinstance(opt, int) or (isinstance(opt, str) and str(opt).isdigit())
            except Exception:
                is_int = False

            if is_problem and is_int:
                try:
                    label = f'题目{int(opt)}'
                except Exception:
                    label = str(opt)
            else:
                label = str(opt)

            selected = ' selected' if str(opt) == str(selected_value) else ''
            html += f'<option value="{val}"{selected}>{label}</option>'
        return html

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.exists('submissions'):
        os.makedirs('submissions')
    if not os.path.exists('problems'):
        os.makedirs('problems')
    setup_database()
    cleanup_expired_sessions()  # 服务器启动时清理过期 sessions
    Handler = MyHandler

    # 使用多线程服务器以支持并发请求
    try:
        class ThreadingHTTPServer(socketserver.ThreadingTCPServer):
            allow_reuse_address = True

        httpd = ThreadingHTTPServer(("", PORT), Handler)
        # 增加请求队列大小以减少短时期连接被拒绝的概率
        try:
            httpd.request_queue_size = 128
        except Exception:
            pass
        # 使工作线程为守护线程，便于进程退出
        httpd.daemon_threads = True

        print(f"伺服器已啟動，請在瀏覽器中輸入 http://localhost:{PORT}")
        print("按下 Ctrl + C 即可停止伺服器")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass

        httpd.server_close()
        print("伺服器已關閉")
    except Exception as e:
        print(f"啟動伺服器時發生錯誤: {e}")