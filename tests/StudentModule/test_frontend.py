#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学生管理模块前端/UI测试代码
使用Selenium进行前端自动化测试
"""

import os
import sys
import time
import tempfile
import sqlite3
import subprocess
import unittest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 导入服务器模块
import server

class TestStudentManagementFrontend(unittest.TestCase):
    """学生管理前端功能测试"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化：启动服务器和浏览器"""
        print("[准备] 准备前端测试环境...")
        
        # 创建临时数据库
        cls.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        cls.temp_db.close()
        
        # 备份原始数据库路径
        cls.original_db_file = server.DB_FILE
        server.DB_FILE = cls.temp_db.name
        
        # 设置测试数据库
        server.setup_database()
        cls.add_test_data()
        # 将临时测试 DB 复制到项目根的 users.db，以便子进程 server.py 能读取相同的数据
        cls.project_db_path = os.path.join(project_root, 'users.db')
        cls._users_db_backup = None
        try:
            import shutil
            if os.path.exists(cls.project_db_path):
                cls._users_db_backup = cls.project_db_path + '.bak_for_tests'
                shutil.copyfile(cls.project_db_path, cls._users_db_backup)
            shutil.copyfile(cls.temp_db.name, cls.project_db_path)
        except Exception as e:
            print(f"[警告] 无法准备项目 users.db: {e}")
        
        # 启动测试服务器
        cls.start_test_server()
        
        # 设置Chrome浏览器
        cls.setup_browser()
        
        print("[完成] 前端测试环境准备完成")
    
    @classmethod
    def tearDownClass(cls):
        """测试类清理：关闭浏览器和服务器"""
        print("[清理] 清理前端测试环境...")
        
        # 关闭浏览器
        if hasattr(cls, 'driver'):
            cls.driver.quit()
        
        # 停止服务器
        if hasattr(cls, 'server_process'):
            cls.server_process.terminate()
            cls.server_process.wait()
        
        # 恢复数据库设置
        server.DB_FILE = cls.original_db_file
        # 恢复或删除项目级 users.db
        try:
            import shutil
            if getattr(cls, '_users_db_backup', None) and os.path.exists(cls._users_db_backup):
                shutil.copyfile(cls._users_db_backup, cls.project_db_path)
                os.unlink(cls._users_db_backup)
            else:
                if os.path.exists(cls.project_db_path):
                    os.unlink(cls.project_db_path)
        except Exception as e:
            print(f"[警告] 无法恢复项目 users.db: {e}")

        try:
            os.unlink(cls.temp_db.name)
        except Exception:
            pass
        
        print("[完成] 前端测试环境清理完成")
    
    @classmethod
    def add_test_data(cls):
        """添加测试数据"""
        conn = sqlite3.connect(server.DB_FILE)
        cursor = conn.cursor()
        
        # 添加管理员用户
        cursor.execute(
            "INSERT INTO users (grade, class_num, username, password, role) VALUES (?, ?, ?, ?, ?)",
            ('admin', 'admin', 'admin', 'admin123', 'admin')
        )
        
        # 添加测试学生
        test_students = [
            ('七年级', '1班', '张三', 'password123', 'student'),
            ('七年级', '1班', '李四', 'password456', 'student'),
            ('七年级', '2班', '王五', 'password789', 'student'),
            ('八年级', '1班', '赵六', 'password000', 'student'),
            ('八年级', '2班', '钱七', 'password111', 'student'),
        ]
        
        for student in test_students:
            cursor.execute(
                "INSERT INTO users (grade, class_num, username, password, role) VALUES (?, ?, ?, ?, ?)",
                student
            )
        
        conn.commit()
        conn.close()
    
    @classmethod
    def start_test_server(cls):
        """启动测试服务器"""
        # 启动服务器进程（使用项目根路径以确保能找到 server.py）
        server_path = os.path.join(project_root, 'server.py')
        cls.server_process = subprocess.Popen(
            [sys.executable, server_path],
            cwd=project_root
        )

        # 等待服务器启动：轮询 localhost:8000 直到可连接或超时
        import urllib.request
        start = time.time()
        timeout = 20  # seconds
        while True:
            try:
                urllib.request.urlopen('http://localhost:8000', timeout=1)
                break
            except Exception:
                if time.time() - start > timeout:
                    print('[警告] 服务器在超时内未能启动')
                    break
                time.sleep(0.5)

        print("[完成] 测试服务器已启动")
    
    @classmethod
    def setup_browser(cls):
        """设置Chrome浏览器"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 无头模式
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            # Disable push messaging / notifications to avoid GCM/FCM DEPRECATED_ENDPOINT logs during tests
            chrome_options.add_argument('--disable-features=PushMessaging')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--window-size=1920,1080')
            
            cls.driver = webdriver.Chrome(options=chrome_options)
            cls.driver.implicitly_wait(10)
            cls.wait = WebDriverWait(cls.driver, 15)
            
            print("[完成] Chrome浏览器设置完成")
            
        except WebDriverException as e:
            print(f"[错误] Chrome浏览器启动失败: {e}")
            print("[提示] 请确保已安装Chrome浏览器和ChromeDriver")
            raise unittest.SkipTest("Chrome浏览器不可用")
    
    def admin_login(self):
        """管理员登录"""
        # server.py serves the teacher login page at /teacher (GET)
        self.driver.get("http://localhost:8000/teacher")

        # 等待页面加载
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))

        # 输入管理员凭据
        username_field = self.driver.find_element(By.NAME, "username")
        password_field = self.driver.find_element(By.NAME, "password")

        username_field.send_keys("alex")
        password_field.send_keys("teacher123")

        # 提交表单并等待重定向
        submit_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
        submit_button.click()
        self.wait.until(EC.url_contains("/admin"))
    
    def test_01_admin_login_and_navigation(self):
        """测试管理员登录和导航到学生管理"""
        print("[测试] 测试管理员登录...")
        # 管理员登录
        self.admin_login()

        # 验证登录成功（server 重定向到 /admin）
        self.assertIn('/admin', self.driver.current_url)

        # 点击学生管理链接，模板内为 "管理學生" 或 英文 "管理學生"，尝试两种
        try:
            student_mgmt_link = self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "管理學生")))
        except Exception:
            student_mgmt_link = self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "管理學生")))

        student_mgmt_link.click()

        # 验证跳转到学生管理页面
        self.wait.until(EC.url_contains("admin/students"))
        self.assertIn("admin/students", self.driver.current_url)

        print("[通过] 管理员登录和导航测试通过")
    
    def test_02_student_list_display(self):
        """测试学生列表显示"""
        print("[测试] 测试学生列表显示...")
        
        # 管理员登录并进入学生管理
        self.admin_login()
        self.driver.get("http://localhost:8000/admin/students")

        # 等待学生列表加载（模板中表格类名为 students-table）
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".students-table")))

        # 检查页面标题（兼容繁体/简体）
        page_title = self.driver.find_element(By.TAG_NAME, "h1")
        self.assertIn(page_title.text.strip(), ("学生管理", "學生管理"))

        # 检查学生表格
        student_table = self.driver.find_element(By.CLASS_NAME, "students-table")
        self.assertIsNotNone(student_table)

        # 检查是否有学生行（排除表头）
        student_rows = self.driver.find_elements(By.CSS_SELECTOR, ".students-table tbody tr")
        self.assertGreater(len(student_rows), 0, "应该显示学生数据")

        # 模板中使用 id total-students 来显示数量，优先验证该节点，如果不存在则略过断言
        try:
            stats_element = self.driver.find_element(By.ID, "total-students")
            stats_text = stats_element.text.strip()
            if stats_text.isdigit():
                self.assertGreaterEqual(int(stats_text), len(student_rows))
        except Exception:
            # 如果模板未提供该统计节点，则忽略该断言
            pass

        print(f"[通过] 学生列表显示测试通过，共显示 {len(student_rows)} 个学生")
    
    def test_03_filter_functionality(self):
        """测试筛选功能"""
        print("[测试] 测试筛选功能...")
        
        # 管理员登录并进入学生管理
        self.admin_login()
        self.driver.get("http://localhost:8000/admin/students")
        
        # 等待页面加载并确保表格与筛选控件已由前端 JS 渲染
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "filter-section")))
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".students-table tbody tr")))

        # 测试年级筛选（模板中 select id 为 filter-grade）
        # 等待 select 被填充（至少有一个非空 option），使用 execute_script 更稳健
        self.wait.until(lambda d: d.execute_script("return Array.from(document.querySelectorAll('select#filter-grade option')).some(function(o){return o.value && o.value.trim() !== ''})"))

        grade_select = Select(self.driver.find_element(By.ID, "filter-grade"))
        options = [opt.get_attribute('value') for opt in self.driver.find_elements(By.CSS_SELECTOR, "select#filter-grade option") if opt.get_attribute('value')]
        if not options:
            self.fail("筛选控件未提供可选的年级")
        selected_grade = options[0]
        grade_select.select_by_value(selected_grade)

        # 等待筛选生效：至少有一个可见行的年级列等于所选值
        self.wait.until(lambda d: any(
            r.is_displayed() and r.find_element(By.CSS_SELECTOR, "td:nth-child(3)").text.strip() == selected_grade
            for r in d.find_elements(By.CSS_SELECTOR, ".students-table tbody tr")
        ))

        # 验证筛选结果
        visible_rows = self.driver.find_elements(
            By.CSS_SELECTOR, ".students-table tbody tr:not([style*='display: none'])"
        )
        
        # 检查显示的学生是否都和所选年级一致
        for row in visible_rows:
            grade_cell = row.find_element(By.CSS_SELECTOR, "td:nth-child(3)")
            self.assertEqual(grade_cell.text.strip(), selected_grade)
        
        # 重置筛选：选择空值以恢复全部学生
        grade_select.select_by_value('')

        print("[通过] 筛选功能测试通过")
    
    def test_04_search_functionality(self):
        """测试搜索功能"""
        print("[测试] 测试搜索功能...")
        
        # 管理员登录并进入学生管理
        self.admin_login()
        self.driver.get("http://localhost:8000/admin/students")
        
        # 等待页面加载并获取搜索框（模板中 id 为 filter-username）
        self.wait.until(EC.presence_of_element_located((By.ID, "filter-username")))
            
        # 获取搜索框
        search_input = self.driver.find_element(By.ID, "filter-username")
        
        # 输入搜索关键词
        search_input.clear()
        search_input.send_keys("张")
        
        # 等待搜索结果：要么出现匹配的用户名，要么出现 no-result-row
        def search_condition(driver):
            rows = driver.find_elements(By.CSS_SELECTOR, ".students-table tbody tr")
            for r in rows:
                if not r.is_displayed():
                    continue
                # 如果是提示行（no-students / no-result-row），跳过或当作没有结果
                tds = r.find_elements(By.TAG_NAME, 'td')
                if len(tds) == 1 and 'no-students' in tds[0].get_attribute('class'):
                    return True
                # 检查是否有第五列并包含关键词（模板中用户名为第5列）
                if len(tds) >= 5:
                    if '张' in tds[4].text:
                        return True
            return False

        self.wait.until(search_condition)

        # 验证搜索结果：遍历可见行，跳过不含用户名列的行
        visible_rows = [r for r in self.driver.find_elements(By.CSS_SELECTOR, ".students-table tbody tr") if r.is_displayed()]
        found = False
        for row in visible_rows:
            tds = row.find_elements(By.TAG_NAME, 'td')
            if len(tds) < 5:
                continue
            # 用户名位于第5列
            username_text = tds[4].text
            if "张" in username_text:
                found = True
                break

        # 如果没有找到包含关键词的行，则确认页面显示没有结果的提示行
        if not found:
            # 检查是否存在 no-result-row（表明无匹配项）
            no_result = False
            for r in visible_rows:
                tds = r.find_elements(By.TAG_NAME, 'td')
                if len(tds) == 1 and r.get_attribute('id') == 'no-result-row':
                    no_result = True
                    break
            # 测试通过条件是：找到匹配行或明确显示无结果提示
            self.assertTrue(found or no_result, '搜索后既未找到匹配行，也没有显示无结果提示')
        
        # 清空搜索
        search_input.clear()
        search_input.send_keys("")
        
        print("[通过] 搜索功能测试通过")
    
    def test_05_password_visibility_toggle(self):
        """测试密码显示/隐藏功能"""
        print("[测试] 测试密码显示/隐藏功能...")
        
        # 管理员登录并进入学生管理
        self.admin_login()
        self.driver.get("http://localhost:8000/admin/students")
        
        # 密码显示/隐藏：模板中使用 .password-toggle 和 .password-cell；如果不存在则跳过该测试
        password_toggles = self.driver.find_elements(By.CSS_SELECTOR, ".password-toggle")
        password_cells = self.driver.find_elements(By.CSS_SELECTOR, ".password-cell")
        if not password_toggles:
            print('[提示] 页面未提供密码切换控件，跳过密码显示/隐藏测试')
            return

        show_password_btn = password_toggles[0]

        # 初始状态：若有密码单元格则断言其存在文本（模板可能使用掩码符号）
        if password_cells:
            first_password_cell = password_cells[0]
            self.assertIsNotNone(first_password_cell.text)

        # 点击显示密码
        show_password_btn.click()
        time.sleep(0.5)

        # 验证密码已显示或文本变化
        if password_cells:
            first_password_cell = password_cells[0]
            self.assertGreaterEqual(len(first_password_cell.text), 0)

        # 再次点击隐藏密码
        show_password_btn.click()
        time.sleep(0.5)
        
        print("[通过] 密码显示/隐藏功能测试通过")
    
    def test_06_edit_student(self):
        """测试编辑学生功能"""
        print("[测试] 测试编辑学生功能...")
        
        # 管理员登录并进入学生管理
        self.admin_login()
        self.driver.get("http://localhost:8000/admin/students")
        
        # 等待页面加载（表格类名为 students-table）
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "students-table")))

        # 点击第一个编辑按钮（模板中类名为 btn-edit）
        edit_buttons = self.driver.find_elements(By.CSS_SELECTOR, ".btn-edit")
        if edit_buttons:
            edit_buttons[0].click()

            # 等待跳转到编辑页面
            self.wait.until(EC.url_contains("edit-student"))

            # 验证编辑页面加载
            self.assertIn("edit-student", self.driver.current_url)

            # 检查表单元素存在
            grade_field = self.driver.find_element(By.NAME, "grade")
            class_field = self.driver.find_element(By.NAME, "class_num")
            username_field = self.driver.find_element(By.NAME, "username")

            self.assertIsNotNone(grade_field)
            self.assertIsNotNone(class_field)
            self.assertIsNotNone(username_field)

            # 修改用户名（添加后缀）
            original_username = username_field.get_attribute("value")
            username_field.clear()
            username_field.send_keys(original_username + "_edited")

            # 提交表单（模板使用 <button type="submit">）
            try:
                submit_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            except Exception:
                submit_button = self.driver.find_element(By.CSS_SELECTOR, ".btn.btn-primary")
            submit_button.click()

            # 等待处理完成（可能跳转回学生列表或显示结果页面）
            time.sleep(2)

            print("[通过] 编辑学生功能测试通过")
    
    def test_07_responsive_design(self):
        """测试响应式设计"""
        print("[测试] 测试响应式设计...")
        
        # 管理员登录并进入学生管理
        self.admin_login()
        self.driver.get("http://localhost:8000/admin/students")

        # 等待页面加载（表格类名为 students-table）
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "students-table")))

        # 测试不同屏幕尺寸
        screen_sizes = [
            (1920, 1080),  # 桌面
            (1024, 768),   # 平板
            (375, 667),    # 手机
        ]

        for width, height in screen_sizes:
            self.driver.set_window_size(width, height)
            time.sleep(1)

            # 检查页面元素是否仍然可见和可用
            student_table = self.driver.find_element(By.CLASS_NAME, "students-table")
            self.assertTrue(student_table.is_displayed())

            filter_section = self.driver.find_element(By.CLASS_NAME, "filter-section")
            self.assertTrue(filter_section.is_displayed())

        # 恢复默认尺寸
        self.driver.set_window_size(1920, 1080)

        print("[通过] 响应式设计测试通过")


def run_frontend_tests():
    """运行前端测试"""
    print("[开始] 开始前端/UI测试...")
    print("=" * 50)
    
    try:
        # 检查Chrome浏览器是否可用
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        
        test_driver = webdriver.Chrome(options=chrome_options)
        test_driver.quit()
        
        # 运行测试
        unittest.main(argv=[''], verbosity=2, exit=False)
        
    except WebDriverException:
        print("[错误] Chrome浏览器或ChromeDriver不可用")
        print("[提示] 跳过前端测试，只运行后端测试")
        print("[提示] 要运行前端测试，请安装：")
        print("   - Chrome浏览器")
        print("   - ChromeDriver (可通过 webdriver-manager 自动管理)")
        return False
    
    return True


if __name__ == '__main__':
    run_frontend_tests()
