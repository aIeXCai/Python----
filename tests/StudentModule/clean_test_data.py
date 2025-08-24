#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速清理测试数据脚本
"""

import sqlite3
import os
import sys

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
import server

def clear_all_data():
    """清空所有测试数据"""
    try:
        conn = sqlite3.connect(server.DB_FILE)
        cursor = conn.cursor()
        
        # 删除所有成绩记录
        cursor.execute("DELETE FROM scores")
        deleted_scores = cursor.rowcount
        
        # 删除所有学生记录
        cursor.execute("DELETE FROM users")
        deleted_users = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"✅ 数据清理完成！")
        print(f"   删除了 {deleted_users} 个学生记录")
        print(f"   删除了 {deleted_scores} 个成绩记录")
        
        return True
    except Exception as e:
        print(f"❌ 清理数据时出错: {e}")
        return False

def show_current_data():
    """显示当前数据统计"""
    try:
        conn = sqlite3.connect(server.DB_FILE)
        cursor = conn.cursor()
        
        # 统计学生数量
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        # 统计成绩记录数量
        cursor.execute("SELECT COUNT(*) FROM scores")
        score_count = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"📊 当前数据统计:")
        print(f"   学生数量: {user_count}")
        print(f"   成绩记录: {score_count}")
        
        return user_count, score_count
    except Exception as e:
        print(f"❌ 查询数据时出错: {e}")
        return 0, 0

def main():
    """主函数"""
    print("🗑️ 测试数据清理工具")
    print("=" * 40)
    
    # 检查数据库是否存在
    if not os.path.exists(server.DB_FILE):
        print(f"⚠️ 数据库文件 {server.DB_FILE} 不存在")
        print("📝 没有需要清理的数据")
        return
    
    # 显示当前数据
    user_count, score_count = show_current_data()
    
    if user_count == 0 and score_count == 0:
        print("✨ 数据库已经是空的，无需清理")
        return
    
    print("\n" + "-" * 40)
    print("⚠️ 警告：此操作将删除所有学生和成绩数据！")
    print("📝 这包括:")
    print(f"   • {user_count} 个学生账户")
    print(f"   • {score_count} 个成绩记录")
    print("-" * 40)
    
    # 确认删除
    while True:
        confirm = input("\n确定要删除所有数据吗？(输入 'yes' 确认，'no' 取消): ").strip().lower()
        
        if confirm == 'yes':
            if clear_all_data():
                print("\n🎉 数据清理完成！数据库现在是空的。")
            break
        elif confirm == 'no':
            print("❌ 操作已取消")
            break
        else:
            print("❌ 请输入 'yes' 或 'no'")

if __name__ == '__main__':
    main()
