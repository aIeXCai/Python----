#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学生管理模块完整测试代码
测试内容包括：
1. 学生注册功能
2. 学生信息查询
3. 学生信息修改
4. 学生删除功能
5. 筛选功能模拟
6. Session管理
7. 性能测试
8. 集成测试
"""

import sqlite3
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import sys
import time

# 添加项目根目录到 Python 路径，确保能导入根目录下的模块（例如 server.py）
# test_backend.py 在 tests/StudentModule 下，向上三层到达项目根
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 导入服务器模块
import server

class TestStudentManagement(unittest.TestCase):
    
    def setUp(self):
        """测试前准备：创建临时数据库"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # 备份原始数据库文件路径
        self.original_db_file = server.DB_FILE
        server.DB_FILE = self.temp_db.name
        
        # 设置测试数据库
        server.setup_database()
        
        # 添加测试数据
        self.add_test_data()
    
    def tearDown(self):
        """测试后清理：删除临时数据库"""
        server.DB_FILE = self.original_db_file
        os.unlink(self.temp_db.name)
    
    def add_test_data(self):
        """添加测试数据"""
        conn = sqlite3.connect(server.DB_FILE)
        cursor = conn.cursor()
        
        # 添加测试学生
        test_students = [
            (1, '七年级', '1班', '张三', 'password123'),
            (2, '七年级', '1班', '李四', 'password456'),
            (3, '七年级', '2班', '王五', 'password789'),
            (4, '八年级', '1班', '赵六', 'password000'),
            (5, '八年级', '2班', '钱七', 'password111'),
        ]
        
        for student in test_students:
            cursor.execute(
                "INSERT INTO users (id, grade, class_num, username, password) VALUES (?, ?, ?, ?, ?)",
                student
            )
        
        conn.commit()
        conn.close()
    
    def test_get_all_students(self):
        """测试获取所有学生列表"""
        students = server.get_all_students()
        
        # 检查返回的学生数量
        self.assertEqual(len(students), 5)
        
        # 检查第一个学生的信息
        first_student = students[0]
        self.assertEqual(first_student[0], 1)  # ID
        self.assertEqual(first_student[1], '七年级')  # 年级
        self.assertEqual(first_student[2], '1班')  # 班级
        self.assertEqual(first_student[3], '张三')  # 用户名
        self.assertEqual(first_student[4], 'password123')  # 密码
        
        print("获取学生列表测试通过")
    
    def test_get_student_by_id(self):
        """测试根据ID获取学生信息"""
        # 测试存在的学生
        student = server.get_student_by_id(1)
        self.assertIsNotNone(student)
        self.assertEqual(student[3], '张三')  # 用户名
        
        # 测试不存在的学生
        student = server.get_student_by_id(999)
        self.assertIsNone(student)

        print("根据ID获取学生信息测试通过")

    def test_register_user(self):
        """测试用户注册功能"""
        # 测试正常注册
        success, message = server.register_user('九年级', '1班', '新学生', 'newpassword')
        self.assertTrue(success)
        self.assertEqual(message, "注册成功！")
        
        # 验证学生已添加到数据库
        students = server.get_all_students()
        self.assertEqual(len(students), 6)
        
        # 测试重复用户名注册
        success, message = server.register_user('九年级', '1班', '新学生', 'anotherpassword')
        self.assertFalse(success)
        self.assertIn("已存在用户名", message)
        
        print("用户注册功能测试通过")
    
    def test_update_student(self):
        """测试更新学生信息"""
        # 测试更新学生信息（不更改密码）
        success, message = server.update_student(1, '七年级', '3班', '张三改名')
        self.assertTrue(success)
        self.assertEqual(message, "学生信息更新成功！")
        
        # 验证更新结果
        student = server.get_student_by_id(1)
        self.assertEqual(student[2], '3班')  # 班级已更新
        self.assertEqual(student[3], '张三改名')  # 用户名已更新
        self.assertEqual(student[4], 'password123')  # 密码未更改
        
        # 测试更新学生信息（包含密码）
        success, message = server.update_student(1, '七年级', '3班', '张三改名', 'newpassword')
        self.assertTrue(success)
        
        # 验证密码已更新
        student = server.get_student_by_id(1)
        self.assertEqual(student[4], 'newpassword')
        
        # 测试更新为重复用户名
        success, message = server.update_student(1, '七年级', '1班', '李四')
        self.assertFalse(success)
        self.assertIn("已存在用户名", message)
        
        print("更新学生信息测试通过")
    
    def test_delete_student(self):
        """测试删除学生功能"""
        # 测试删除存在的学生
        success, message = server.delete_student(1)
        self.assertTrue(success)
        self.assertIn("删除成功", message)
        
        # 验证学生已删除
        student = server.get_student_by_id(1)
        self.assertIsNone(student)
        
        # 验证学生数量减少
        students = server.get_all_students()
        self.assertEqual(len(students), 4)
        
        # 测试删除不存在的学生
        success, message = server.delete_student(999)
        self.assertFalse(success)
        self.assertEqual(message, "学生不存在！")
        
        print("删除学生功能测试通过")
    
    def test_authenticate_user(self):
        """测试用户认证功能"""
        # 测试正确的认证信息
        is_authenticated = server.authenticate_user('七年级', '1班', '张三', 'password123')
        self.assertTrue(is_authenticated)
        
        # 测试错误的密码
        is_authenticated = server.authenticate_user('七年级', '1班', '张三', 'wrongpassword')
        self.assertFalse(is_authenticated)
        
        # 测试不存在的用户
        is_authenticated = server.authenticate_user('七年级', '1班', '不存在', 'password123')
        self.assertFalse(is_authenticated)
        
        print("用户认证功能测试通过")
    
    def test_filter_functionality_simulation(self):
        """模拟测试筛选功能（前端逻辑）"""
        students = server.get_all_students()
        
        # 模拟按年级筛选
        seven_grade_students = [s for s in students if s[1] == '七年级']
        self.assertEqual(len(seven_grade_students), 3)
        
        # 模拟按班级筛选
        class1_students = [s for s in students if s[2] == '1班']
        self.assertEqual(len(class1_students), 3)
        
        # 模拟按年级和班级组合筛选
        seven_class1_students = [s for s in students if s[1] == '七年级' and s[2] == '1班']
        self.assertEqual(len(seven_class1_students), 2)
        
        # 模拟按用户名搜索
        zhang_students = [s for s in students if '张' in s[3]]
        self.assertEqual(len(zhang_students), 1)
        
        print("筛选功能模拟测试通过")


class TestSessionManagement(unittest.TestCase):
    """测试Session管理功能"""
    
    def setUp(self):
        """清理现有sessions"""
        server.SESSIONS.clear()
    
    def test_create_session(self):
        """测试创建session"""
        session_id = server.create_session('testuser', 'student', '七年级', '1班')
        
        self.assertIsNotNone(session_id)
        self.assertIn(session_id, server.SESSIONS)
        
        session_data = server.SESSIONS[session_id]
        self.assertEqual(session_data['username'], 'testuser')
        self.assertEqual(session_data['role'], 'student')
        self.assertEqual(session_data['grade'], '七年级')
        self.assertEqual(session_data['class_num'], '1班')
        
        print("创建session测试通过")
    
    def test_get_user_from_session(self):
        """测试从session获取用户信息"""
        # 创建session
        session_id = server.create_session('testuser', 'student')
        
        # 获取用户信息
        user_data = server.get_user_from_session(session_id)
        self.assertIsNotNone(user_data)
        self.assertEqual(user_data['username'], 'testuser')
        
        # 测试无效session
        invalid_user_data = server.get_user_from_session('invalid_session_id')
        self.assertIsNone(invalid_user_data)
        
        print("从session获取用户信息测试通过")
    
    def test_session_timeout(self):
        """测试session超时"""
        # 创建session
        session_id = server.create_session('testuser', 'student')
        
        # 模拟超时：修改创建时间
        server.SESSIONS[session_id]['created_time'] = 0  # 设置为很久以前
        
        # 尝试获取用户信息（应该返回None，因为已超时）
        user_data = server.get_user_from_session(session_id)
        self.assertIsNone(user_data)
        
        # 验证过期session已被删除
        self.assertNotIn(session_id, server.SESSIONS)
        
        print("session超时测试通过")


def run_performance_test():
    """性能测试：测试大量学生数据的处理"""
    print("\n开始性能测试...")
    
    # 创建临时数据库
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    original_db_file = server.DB_FILE
    server.DB_FILE = temp_db.name
    
    try:
        server.setup_database()
        
        # 添加大量测试数据
        conn = sqlite3.connect(server.DB_FILE)
        cursor = conn.cursor()
        
        print("添加1000个测试学生...")
        start_time = time.time()
        
        for i in range(1000):
            grade = f"{(i % 3) + 7}年级"  # 7、8、9年级
            class_num = f"{(i % 5) + 1}班"  # 1-5班
            username = f"student_{i:04d}"
            password = f"password_{i:04d}"
            
            cursor.execute(
                "INSERT INTO users (grade, class_num, username, password) VALUES (?, ?, ?, ?)",
                (grade, class_num, username, password)
            )
        
        conn.commit()
        insert_time = time.time() - start_time
        print(f"插入1000个学生耗时: {insert_time:.4f}秒")
        
        conn.close()
        
        # 测试查询性能
        start_time = time.time()
        students = server.get_all_students()
        query_time = time.time() - start_time
        
        print(f"查询1000个学生耗时: {query_time:.4f}秒")
        print(f"查询到 {len(students)} 个学生")
        
        # 测试筛选性能（模拟前端操作）
        start_time = time.time()
        filtered_students = [s for s in students if s[1] == '7年级' and s[2] == '1班']
        filter_time = time.time() - start_time
        
        print(f"筛选耗时: {filter_time:.4f}秒")
        print(f"筛选结果: {len(filtered_students)} 个学生")
        
    finally:
        server.DB_FILE = original_db_file
        os.unlink(temp_db.name)


def run_integration_test():
    """集成测试：测试完整的学生管理流程"""
    print("\n开始集成测试...")
    
    # 创建临时数据库
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    original_db_file = server.DB_FILE
    server.DB_FILE = temp_db.name
    
    try:
        server.setup_database()
        
        # 1. 注册新学生
        print("1. 测试注册新学生...")
        success, message = server.register_user('七年级', '1班', '测试学生', 'testpass123')
        assert success, f"注册失败: {message}"
        print("学生注册成功")
        
        # 2. 验证学生可以登录
        print("2. 测试学生登录...")
        is_authenticated = server.authenticate_user('七年级', '1班', '测试学生', 'testpass123')
        assert is_authenticated, "学生登录失败"
        print("学生登录成功")
        
        # 3. 获取学生信息
        print("3. 测试获取学生信息...")
        students = server.get_all_students()
        assert len(students) == 1, "学生数量不正确"
        student = students[0]
        assert student[3] == '测试学生', "学生用户名不正确"
        print("学生信息获取成功")
        
        # 4. 更新学生信息
        print("4. 测试更新学生信息...")
        student_id = student[0]
        success, message = server.update_student(student_id, '八年级', '2班', '更新学生', 'newpass456')
        assert success, f"更新失败: {message}"
        
        # 验证更新结果
        updated_student = server.get_student_by_id(student_id)
        assert updated_student[1] == '八年级', "年级更新失败"
        assert updated_student[2] == '2班', "班级更新失败"
        assert updated_student[3] == '更新学生', "用户名更新失败"
        print("学生信息更新成功")
        
        # 5. 验证新密码有效
        print("5. 测试新密码登录...")
        is_authenticated = server.authenticate_user('八年级', '2班', '更新学生', 'newpass456')
        assert is_authenticated, "新密码登录失败"
        print("新密码登录成功")
        
        # 6. 删除学生
        print("6. 测试删除学生...")
        success, message = server.delete_student(student_id)
        assert success, f"删除失败: {message}"
        
        # 验证删除结果
        deleted_student = server.get_student_by_id(student_id)
        assert deleted_student is None, "学生删除失败"
        
        students = server.get_all_students()
        assert len(students) == 0, "学生数量应为0"
        print("学生删除成功")
        
        print("集成测试全部通过！")
        
    finally:
        server.DB_FILE = original_db_file
        os.unlink(temp_db.name)


if __name__ == '__main__':
    print("开始学生管理模块完整测试")
    print("=" * 50)
    
    # 运行单元测试
    print("\n单元测试:")
    unittest.main(argv=[''], verbosity=2, exit=False)
    
    # 运行性能测试
    run_performance_test()
    
    # 运行集成测试
    run_integration_test()
    
    print("\n" + "=" * 50)
    print("所有测试完成！")
