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
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException

# 添加父目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入服务器模块
import server

class TestStudentManagementFrontend(unittest.TestCase):
    """学生管理前端功能测试"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化：启动服务器和浏览器"""
        print("🚀 准备前端测试环境...")
        
        # 创建临时数据库
        cls.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        cls.temp_db.close()
        
        # 备份原始数据库路径
        cls.original_db_file = server.DB_FILE
        server.DB_FILE = cls.temp_db.name
        
        # 设置测试数据库
        server.setup_database()
        cls.add_test_data()
        
        # 启动测试服务器
        cls.start_test_server()
        
        # 设置Chrome浏览器
        cls.setup_browser()
        
        print("✅ 前端测试环境准备完成")
    
    @classmethod
    def tearDownClass(cls):
        """测试类清理：关闭浏览器和服务器"""
        print("🧹 清理前端测试环境...")
        
        # 关闭浏览器
        if hasattr(cls, 'driver'):
            cls.driver.quit()
        
        # 停止服务器
        if hasattr(cls, 'server_process'):
            cls.server_process.terminate()
            cls.server_process.wait()
        
        # 恢复数据库设置
        server.DB_FILE = cls.original_db_file
        os.unlink(cls.temp_db.name)
        
        print("✅ 前端测试环境清理完成")
    
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
        # 启动服务器进程
        cls.server_process = subprocess.Popen([
            sys.executable, 'server.py'
        ], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # 等待服务器启动
        time.sleep(3)
        print("✅ 测试服务器已启动")
    
    @classmethod
    def setup_browser(cls):
        """设置Chrome浏览器"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 无头模式
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            
            cls.driver = webdriver.Chrome(options=chrome_options)
            cls.driver.implicitly_wait(10)
            cls.wait = WebDriverWait(cls.driver, 15)
            
            print("✅ Chrome浏览器设置完成")
            
        except WebDriverException as e:
            print(f"❌ Chrome浏览器启动失败: {e}")
            print("💡 请确保已安装Chrome浏览器和ChromeDriver")
            raise unittest.SkipTest("Chrome浏览器不可用")
    
    def admin_login(self):
        """管理员登录"""
        self.driver.get("http://localhost:8000/teacher-login")
        
        # 等待页面加载
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
        
        # 输入管理员凭据
        username_field = self.driver.find_element(By.NAME, "username")
        password_field = self.driver.find_element(By.NAME, "password")
        
        username_field.send_keys("admin")
        password_field.send_keys("admin123")
        
        # 提交表单
        submit_button = self.driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
        submit_button.click()
        
        # 等待跳转到管理后台
        self.wait.until(EC.url_contains("admin-dashboard"))
    
    def test_01_admin_login_and_navigation(self):
        """测试管理员登录和导航到学生管理"""
        print("📝 测试管理员登录...")
        
        # 管理员登录
        self.admin_login()
        
        # 验证登录成功
        self.assertIn("admin-dashboard", self.driver.current_url)
        
        # 点击学生管理链接
        student_mgmt_link = self.wait.until(
            EC.element_to_be_clickable((By.LINK_TEXT, "学生管理"))
        )
        student_mgmt_link.click()
        
        # 验证跳转到学生管理页面
        self.wait.until(EC.url_contains("admin/students"))
        self.assertIn("admin/students", self.driver.current_url)
        
        print("✅ 管理员登录和导航测试通过")
    
    def test_02_student_list_display(self):
        """测试学生列表显示"""
        print("📝 测试学生列表显示...")
        
        # 管理员登录并进入学生管理
        self.admin_login()
        self.driver.get("http://localhost:8000/admin/students")
        
        # 等待学生列表加载
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "student-table")))
        
        # 检查页面标题
        page_title = self.driver.find_element(By.TAG_NAME, "h1")
        self.assertEqual(page_title.text, "学生管理")
        
        # 检查学生表格
        student_table = self.driver.find_element(By.CLASS_NAME, "student-table")
        self.assertIsNotNone(student_table)
        
        # 检查是否有学生行（排除表头）
        student_rows = self.driver.find_elements(By.CSS_SELECTOR, ".student-table tbody tr")
        self.assertGreater(len(student_rows), 0, "应该显示学生数据")
        
        # 检查统计信息
        stats_element = self.driver.find_element(By.CLASS_NAME, "student-stats")
        stats_text = stats_element.text
        self.assertIn("共", stats_text)
        self.assertIn("名学生", stats_text)
        
        print(f"✅ 学生列表显示测试通过，共显示 {len(student_rows)} 个学生")
    
    def test_03_filter_functionality(self):
        """测试筛选功能"""
        print("📝 测试筛选功能...")
        
        # 管理员登录并进入学生管理
        self.admin_login()
        self.driver.get("http://localhost:8000/admin/students")
        
        # 等待页面加载
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "filter-section")))
        
        # 测试年级筛选
        grade_filter = self.driver.find_element(By.ID, "gradeFilter")
        grade_filter.click()
        
        # 选择"七年级"
        seven_grade_option = self.driver.find_element(By.CSS_SELECTOR, "option[value='七年级']")
        seven_grade_option.click()
        
        # 等待筛选结果
        time.sleep(1)
        
        # 验证筛选结果
        visible_rows = self.driver.find_elements(
            By.CSS_SELECTOR, ".student-table tbody tr:not([style*='display: none'])"
        )
        
        # 检查显示的学生是否都是七年级
        for row in visible_rows:
            grade_cell = row.find_element(By.CSS_SELECTOR, "td:nth-child(2)")
            self.assertEqual(grade_cell.text, "七年级")
        
        # 重置筛选
        grade_filter.click()
        all_option = self.driver.find_element(By.CSS_SELECTOR, "option[value='']")
        all_option.click()
        
        print("✅ 筛选功能测试通过")
    
    def test_04_search_functionality(self):
        """测试搜索功能"""
        print("📝 测试搜索功能...")
        
        # 管理员登录并进入学生管理
        self.admin_login()
        self.driver.get("http://localhost:8000/admin/students")
        
        # 等待页面加载
        self.wait.until(EC.presence_of_element_located((By.ID, "searchInput")))
        
        # 获取搜索框
        search_input = self.driver.find_element(By.ID, "searchInput")
        
        # 输入搜索关键词
        search_input.clear()
        search_input.send_keys("张")
        
        # 等待搜索结果
        time.sleep(1)
        
        # 验证搜索结果
        visible_rows = self.driver.find_elements(
            By.CSS_SELECTOR, ".student-table tbody tr:not([style*='display: none'])"
        )
        
        # 检查搜索结果是否包含"张"
        for row in visible_rows:
            username_cell = row.find_element(By.CSS_SELECTOR, "td:nth-child(4)")
            self.assertIn("张", username_cell.text)
        
        # 清空搜索
        search_input.clear()
        search_input.send_keys("")
        
        print("✅ 搜索功能测试通过")
    
    def test_05_password_visibility_toggle(self):
        """测试密码显示/隐藏功能"""
        print("📝 测试密码显示/隐藏功能...")
        
        # 管理员登录并进入学生管理
        self.admin_login()
        self.driver.get("http://localhost:8000/admin/students")
        
        # 等待页面加载
        self.wait.until(EC.presence_of_element_located((By.ID, "showPasswordBtn")))
        
        # 获取密码显示按钮
        show_password_btn = self.driver.find_element(By.ID, "showPasswordBtn")
        
        # 初始状态：密码应该被隐藏
        password_cells = self.driver.find_elements(By.CSS_SELECTOR, ".password-cell")
        if password_cells:
            first_password_cell = password_cells[0]
            self.assertEqual(first_password_cell.text, "••••••••")
        
        # 点击显示密码
        show_password_btn.click()
        time.sleep(0.5)
        
        # 验证密码已显示
        if password_cells:
            first_password_cell = password_cells[0]
            self.assertNotEqual(first_password_cell.text, "••••••••")
            self.assertGreater(len(first_password_cell.text), 0)
        
        # 再次点击隐藏密码
        show_password_btn.click()
        time.sleep(0.5)
        
        # 验证密码已隐藏
        if password_cells:
            first_password_cell = password_cells[0]
            self.assertEqual(first_password_cell.text, "••••••••")
        
        print("✅ 密码显示/隐藏功能测试通过")
    
    def test_06_edit_student(self):
        """测试编辑学生功能"""
        print("📝 测试编辑学生功能...")
        
        # 管理员登录并进入学生管理
        self.admin_login()
        self.driver.get("http://localhost:8000/admin/students")
        
        # 等待页面加载
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "student-table")))
        
        # 点击第一个编辑按钮
        edit_buttons = self.driver.find_elements(By.CSS_SELECTOR, ".edit-btn")
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
            
            # 提交表单
            submit_button = self.driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
            submit_button.click()
            
            # 等待处理完成（可能跳转回学生列表或显示结果页面）
            time.sleep(2)
            
            print("✅ 编辑学生功能测试通过")
    
    def test_07_responsive_design(self):
        """测试响应式设计"""
        print("📝 测试响应式设计...")
        
        # 管理员登录并进入学生管理
        self.admin_login()
        self.driver.get("http://localhost:8000/admin/students")
        
        # 等待页面加载
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "student-table")))
        
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
            student_table = self.driver.find_element(By.CLASS_NAME, "student-table")
            self.assertTrue(student_table.is_displayed())
            
            filter_section = self.driver.find_element(By.CLASS_NAME, "filter-section")
            self.assertTrue(filter_section.is_displayed())
        
        # 恢复默认尺寸
        self.driver.set_window_size(1920, 1080)
        
        print("✅ 响应式设计测试通过")


def run_frontend_tests():
    """运行前端测试"""
    print("🌐 开始前端/UI测试...")
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
        print("❌ Chrome浏览器或ChromeDriver不可用")
        print("💡 跳过前端测试，只运行后端测试")
        print("💡 要运行前端测试，请安装：")
        print("   - Chrome浏览器")
        print("   - ChromeDriver (可通过 webdriver-manager 自动管理)")
        return False
    
    return True


if __name__ == '__main__':
    run_frontend_tests()
