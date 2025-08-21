#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据管理工具
用于创建、管理和清理测试数据
"""

import sqlite3
import os
import sys

# 添加父目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server

def create_test_data():
    """创建测试数据"""
    print("🔧 创建测试数据...")
    
    conn = sqlite3.connect(server.DB_FILE)
    cursor = conn.cursor()
    
    # 测试学生数据
    test_students = [
        ('七年级', '1班', 'test_student_1', 'testpass1'),
        ('七年级', '2班', 'test_student_2', 'testpass2'),
        ('八年级', '1班', 'test_student_3', 'testpass3'),
        ('八年级', '2班', 'test_student_4', 'testpass4'),
        ('九年级', '1班', 'test_student_5', 'testpass5'),
    ]
    
    added_count = 0
    for grade, class_num, username, password in test_students:
        try:
            cursor.execute(
                "INSERT INTO users (grade, class_num, username, password, role) VALUES (?, ?, ?, ?, ?)",
                (grade, class_num, username, password, 'student')
            )
            added_count += 1
            print(f"   ✅ 添加学生: {username} ({grade} {class_num})")
        except sqlite3.IntegrityError:
            print(f"   ⚠️  学生已存在: {username}")
    
    conn.commit()
    conn.close()
    
    print(f"🎉 测试数据创建完成，共添加 {added_count} 个学生")

def list_test_data():
    """列出当前测试数据"""
    print("📋 当前测试数据:")
    
    conn = sqlite3.connect(server.DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE username LIKE 'test_%'")
    test_users = cursor.fetchall()
    
    if not test_users:
        print("   📭 没有找到测试数据")
    else:
        print(f"   📊 找到 {len(test_users)} 个测试用户:")
        for user in test_users:
            print(f"   - ID: {user[0]}, {user[1]} {user[2]}, 用户名: {user[3]}")
    
    conn.close()

def clean_test_data():
    """清理测试数据"""
    print("🧹 清理测试数据...")
    
    conn = sqlite3.connect(server.DB_FILE)
    cursor = conn.cursor()
    
    # 删除测试用户
    cursor.execute("DELETE FROM users WHERE username LIKE 'test_%'")
    deleted_users = cursor.rowcount
    
    # 删除可能的测试分数记录
    cursor.execute("DELETE FROM scores WHERE user_id NOT IN (SELECT id FROM users)")
    deleted_scores = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"✅ 清理完成:")
    print(f"   - 删除测试用户: {deleted_users} 个")
    print(f"   - 删除无效分数记录: {deleted_scores} 个")

def interactive_menu():
    """交互式菜单"""
    while True:
        print("\n" + "=" * 40)
        print("📦 测试数据管理工具")
        print("=" * 40)
        print("1. 创建测试数据")
        print("2. 查看测试数据")
        print("3. 清理测试数据")
        print("4. 退出")
        print("-" * 40)
        
        choice = input("请选择操作 (1-4): ").strip()
        
        if choice == '1':
            create_test_data()
        elif choice == '2':
            list_test_data()
        elif choice == '3':
            confirm = input("确认要清理所有测试数据吗？(y/N): ").strip().lower()
            if confirm in ['y', 'yes']:
                clean_test_data()
            else:
                print("❌ 已取消清理操作")
        elif choice == '4':
            print("👋 再见！")
            break
        else:
            print("❌ 无效选择，请重试")

if __name__ == '__main__':
    # 确保数据库存在
    if not os.path.exists(server.DB_FILE):
        print("⚠️  数据库文件不存在，正在创建...")
        server.setup_database()
    
    # 启动交互式菜单
    interactive_menu()
