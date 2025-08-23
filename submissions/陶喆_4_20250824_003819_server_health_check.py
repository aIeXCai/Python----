#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
服务器健康检查和性能优化工具
"""

import sqlite3
import os
import time
import json
from datetime import datetime, timedelta

class ServerHealthChecker:
    def __init__(self, db_path="student_data.db"):
        self.db_path = db_path
        
    def check_database_health(self):
        """检查数据库健康状况"""
        print("=" * 50)
        print("数据库健康检查")
        print("=" * 50)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查表结构
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print(f"✓ 数据库连接正常，共有 {len(tables)} 个表")
            
            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"  - {table_name}: {count} 条记录")
            
            # 检查用户表
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            
            # 检查成绩表
            cursor.execute("SELECT COUNT(*) FROM scores")
            score_count = cursor.fetchone()[0]
            
            # 检查最近的提交
            cursor.execute("""
                SELECT COUNT(*) FROM scores 
                WHERE submission_time > datetime('now', '-1 day')
            """)
            recent_submissions = cursor.fetchone()[0]
            
            print(f"\n数据库统计:")
            print(f"  - 注册用户: {user_count}")
            print(f"  - 总提交数: {score_count}")
            print(f"  - 24小时内提交: {recent_submissions}")
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"✗ 数据库检查失败: {e}")
            return False
    
    def check_file_structure(self):
        """检查文件结构完整性"""
        print("\n" + "=" * 50)
        print("文件结构检查")
        print("=" * 50)
        
        required_files = [
            "server.py",
            "templates/index.html",
            "templates/dashboard.html",
            "templates/teacher_login.html",
            "templates/admin_dashboard.html",
            "student_data.db"
        ]
        
        required_dirs = [
            "templates",
            "problems",
            "submissions"
        ]
        
        all_good = True
        
        # 检查文件
        for file_path in required_files:
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                print(f"✓ {file_path} ({size} bytes)")
            else:
                print(f"✗ {file_path} (缺失)")
                all_good = False
        
        # 检查目录
        for dir_path in required_dirs:
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                files_count = len(os.listdir(dir_path))
                print(f"✓ {dir_path}/ ({files_count} 个文件)")
            else:
                print(f"✗ {dir_path}/ (缺失)")
                all_good = False
        
        return all_good
    
    def check_problems_directory(self):
        """检查题目目录"""
        print("\n" + "=" * 50)
        print("题目目录检查")
        print("=" * 50)
        
        problems_dir = "problems"
        if not os.path.exists(problems_dir):
            print("✗ problems目录不存在")
            return False
        
        problems = []
        for item in os.listdir(problems_dir):
            problem_path = os.path.join(problems_dir, item)
            if os.path.isdir(problem_path):
                problems.append(item)
                
                # 检查题目文件
                desc_file = os.path.join(problem_path, "description.txt")
                test_dir = os.path.join(problem_path, "tests")
                
                has_desc = os.path.exists(desc_file)
                has_tests = os.path.exists(test_dir) and os.path.isdir(test_dir)
                test_count = len(os.listdir(test_dir)) if has_tests else 0
                
                status = "✓" if has_desc and has_tests else "✗"
                print(f"{status} {item} - 描述: {'有' if has_desc else '无'}, 测试用例: {test_count}")
        
        print(f"\n总计: {len(problems)} 个题目")
        return len(problems) > 0
    
    def generate_performance_report(self):
        """生成性能报告"""
        print("\n" + "=" * 50)
        print("性能分析报告")
        print("=" * 50)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查询提交统计
            cursor.execute("""
                SELECT 
                    problem_id,
                    COUNT(*) as submission_count,
                    AVG(score) as avg_score,
                    MAX(score) as max_score,
                    MIN(score) as min_score
                FROM scores 
                GROUP BY problem_id 
                ORDER BY submission_count DESC
            """)
            
            problem_stats = cursor.fetchall()
            
            if problem_stats:
                print("题目提交统计:")
                print(f"{'题目ID':<10} {'提交数':<8} {'平均分':<8} {'最高分':<8} {'最低分':<8}")
                print("-" * 50)
                
                for stat in problem_stats:
                    problem_id, count, avg, max_score, min_score = stat
                    print(f"{problem_id:<10} {count:<8} {avg:<8.1f} {max_score:<8.1f} {min_score:<8.1f}")
            
            # 查询用户活跃度
            cursor.execute("""
                SELECT 
                    grade || '-' || class_num as class_info,
                    COUNT(DISTINCT username) as student_count,
                    COUNT(*) as total_submissions
                FROM scores 
                GROUP BY grade, class_num 
                ORDER BY total_submissions DESC
            """)
            
            class_stats = cursor.fetchall()
            
            if class_stats:
                print(f"\n班级活跃度:")
                print(f"{'班级':<15} {'学生数':<8} {'总提交数':<10}")
                print("-" * 35)
                
                for stat in class_stats:
                    class_info, student_count, submissions = stat
                    print(f"{class_info:<15} {student_count:<8} {submissions:<10}")
            
            conn.close()
            
        except Exception as e:
            print(f"✗ 性能报告生成失败: {e}")
    
    def optimize_database(self):
        """优化数据库性能"""
        print("\n" + "=" * 50)
        print("数据库优化")
        print("=" * 50)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建索引以提高查询性能
            indexes = [
                ("idx_scores_user", "CREATE INDEX IF NOT EXISTS idx_scores_user ON scores(grade, class_num, username)"),
                ("idx_scores_problem", "CREATE INDEX IF NOT EXISTS idx_scores_problem ON scores(problem_id)"),
                ("idx_scores_time", "CREATE INDEX IF NOT EXISTS idx_scores_time ON scores(submission_time)"),
                ("idx_users_auth", "CREATE INDEX IF NOT EXISTS idx_users_auth ON users(grade, class_num, username)")
            ]
            
            for idx_name, sql in indexes:
                cursor.execute(sql)
                print(f"✓ 创建索引: {idx_name}")
            
            # 运行VACUUM来优化数据库文件
            cursor.execute("VACUUM")
            print("✓ 数据库文件优化完成")
            
            # 更新统计信息
            cursor.execute("ANALYZE")
            print("✓ 统计信息更新完成")
            
            conn.commit()
            conn.close()
            
            print("数据库优化完成！")
            
        except Exception as e:
            print(f"✗ 数据库优化失败: {e}")
    
    def run_full_check(self):
        """运行完整的健康检查"""
        print("Python学习平台 - 服务器健康检查")
        print("检查时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        db_ok = self.check_database_health()
        files_ok = self.check_file_structure()
        problems_ok = self.check_problems_directory()
        
        self.generate_performance_report()
        
        if db_ok and files_ok and problems_ok:
            print("\n" + "=" * 50)
            print("🎉 所有检查通过！服务器状态良好")
            print("=" * 50)
            
            optimize = input("\n是否要运行数据库优化？(y/n): ").lower().strip()
            if optimize == 'y':
                self.optimize_database()
        else:
            print("\n" + "=" * 50)
            print("⚠️  发现问题，请检查上述错误")
            print("=" * 50)

if __name__ == "__main__":
    checker = ServerHealthChecker()
    checker.run_full_check()
