#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成绩管理模块测试数据清理工具
专门用于清理成绩相关的测试数据
"""

import sqlite3
import os
import sys

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import server

def clear_score_data():
    """清空成绩测试数据"""
    try:
        conn = sqlite3.connect(server.DB_FILE)
        cursor = conn.cursor()
        
        # 删除所有成绩记录
        cursor.execute("DELETE FROM scores")
        deleted_scores = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"✅ 成绩数据清理完成！")
        print(f"   删除了 {deleted_scores} 个成绩记录")
        
        return True
    except Exception as e:
        print(f"❌ 清理成绩数据时出错: {e}")
        return False

def clear_all_test_data():
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
        
        print(f"✅ 所有测试数据清理完成！")
        print(f"   删除了 {deleted_users} 个学生记录")
        print(f"   删除了 {deleted_scores} 个成绩记录")
        
        return True
    except Exception as e:
        print(f"❌ 清理测试数据时出错: {e}")
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
        
        # 统计成绩分布
        cursor.execute("""
            SELECT grade, COUNT(*) as count 
            FROM scores 
            GROUP BY grade 
            ORDER BY grade
        """)
        grade_distribution = cursor.fetchall()
        
        conn.close()
        
        print(f"📊 当前数据统计:")
        print(f"   学生数量: {user_count}")
        print(f"   成绩记录: {score_count}")
        
        if grade_distribution:
            print(f"   成绩分布:")
            for grade, count in grade_distribution:
                print(f"     {grade}年级: {count} 条记录")
        
        return user_count, score_count
    except Exception as e:
        print(f"❌ 查询数据时出错: {e}")
        return 0, 0

def show_menu():
    """显示清理菜单"""
    print("🗑️ 成绩管理测试数据清理工具")
    print("=" * 40)
    print("1. 只清理成绩数据")
    print("2. 清理所有测试数据 (学生+成绩)")
    print("3. 查看当前数据统计")
    print("4. 退出")
    print("-" * 40)

def main():
    """主函数"""
    print("🧹 成绩管理模块数据清理工具")
    print("=" * 50)
    
    # 检查数据库是否存在
    if not os.path.exists(server.DB_FILE):
        print(f"⚠️ 数据库文件 {server.DB_FILE} 不存在")
        print("📝 没有需要清理的数据")
        return
    
    while True:
        print()
        show_menu()
        
        try:
            choice = input("请选择操作 (1-4): ").strip()
            
            if choice == '1':
                # 显示当前数据
                user_count, score_count = show_current_data()
                
                if score_count == 0:
                    print("✨ 没有成绩数据需要清理")
                    continue
                
                print(f"\n⚠️ 警告：将删除 {score_count} 条成绩记录！")
                confirm = input("确定要删除所有成绩数据吗？(输入 'yes' 确认): ").strip().lower()
                
                if confirm == 'yes':
                    if clear_score_data():
                        print("🎉 成绩数据清理完成！")
                else:
                    print("❌ 操作已取消")
            
            elif choice == '2':
                # 显示当前数据
                user_count, score_count = show_current_data()
                
                if user_count == 0 and score_count == 0:
                    print("✨ 没有测试数据需要清理")
                    continue
                
                print(f"\n⚠️ 警告：将删除所有测试数据！")
                print(f"📝 这包括:")
                print(f"   • {user_count} 个学生账户")
                print(f"   • {score_count} 个成绩记录")
                confirm = input("确定要删除所有测试数据吗？(输入 'yes' 确认): ").strip().lower()
                
                if confirm == 'yes':
                    if clear_all_test_data():
                        print("🎉 所有测试数据清理完成！")
                else:
                    print("❌ 操作已取消")
            
            elif choice == '3':
                show_current_data()
            
            elif choice == '4':
                print("👋 退出清理工具")
                break
            
            else:
                print("❌ 无效选择，请输入 1-4")
                
        except KeyboardInterrupt:
            print("\n\n👋 用户中断，退出清理工具")
            break
        except Exception as e:
            print(f"❌ 操作失败: {e}")

if __name__ == '__main__':
    main()
