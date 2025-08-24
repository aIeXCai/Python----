#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成绩管理功能测试模块
测试包括：成绩录入、查询、筛选、统计等功能
"""

import sqlite3
import os
import sys
import random
import datetime
from typing import List, Dict, Tuple

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
import server

class ScoreManagementTester:
    """成绩管理测试类"""
    
    def __init__(self):
        self.test_db = "test_scores.db"
        self.original_db = server.DB_FILE
        
    def setup_test_environment(self):
        """设置测试环境"""
        print("🔧 设置测试环境...")
        
        # 使用测试数据库
        server.DB_FILE = self.test_db
        
        # 删除已存在的测试数据库
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        
        # 初始化测试数据库
        server.setup_database()
        print("✅ 测试数据库初始化完成")
        
    def cleanup_test_environment(self):
        """清理测试环境"""
        print("🧹 清理测试环境...")
        
        # 恢复原始数据库配置
        server.DB_FILE = self.original_db
        
        # 删除测试数据库
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        
        print("✅ 测试环境清理完成")
    
    def create_test_students(self) -> List[Tuple[str, str, str, str]]:
        """创建测试学生数据"""
        students = [
            ("10", "1", "张三", "123456"),
            ("10", "1", "李四", "123456"),
            ("10", "2", "王五", "123456"),
            ("11", "1", "赵六", "123456"),
            ("11", "2", "钱七", "123456"),
            ("12", "1", "孙八", "123456"),
        ]
        
        conn = sqlite3.connect(server.DB_FILE)
        cursor = conn.cursor()
        
        for grade, class_num, username, password in students:
            server.register_user(grade, class_num, username, password)
        
        conn.close()
        return students
    
    def create_test_scores(self, students: List[Tuple[str, str, str, str]]):
        """创建测试成绩数据"""
        print("📊 创建测试成绩数据...")
        
        conn = sqlite3.connect(server.DB_FILE)
        cursor = conn.cursor()
        
        # 为每个学生在多个题目上创建成绩
        problems = [1, 2, 3, 4, 5]
        
        for grade, class_num, username, _ in students:
            for problem_id in problems:
                # 为每个学生的每道题只创建一条最终成绩记录
                score = random.uniform(60, 100)  # 60-100分
                submission_time = datetime.datetime.now() - datetime.timedelta(
                    days=random.randint(0, 30),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )
                
                # 使用 INSERT OR REPLACE 来处理唯一约束
                cursor.execute('''
                    INSERT OR REPLACE INTO scores (grade, class_num, username, problem_id, score, submission_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (grade, class_num, username, problem_id, score, submission_time.strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.commit()
        conn.close()
        print("✅ 测试成绩数据创建完成")
    
    def test_get_all_scores(self):
        """测试获取所有成绩功能"""
        print("\n🧪 测试获取所有成绩功能...")
        
        try:
            scores = server.get_all_scores()
            print(f"✅ 成功获取 {len(scores)} 条成绩记录")
            
            # 验证数据结构
            if scores:
                sample = scores[0]
                expected_fields = 6  # grade, class_num, username, problem_id, score, submission_time
                if len(sample) == expected_fields:
                    print("✅ 成绩数据结构正确")
                else:
                    print(f"❌ 成绩数据结构错误，期望 {expected_fields} 个字段，实际 {len(sample)} 个")
            
            return True
        except Exception as e:
            print(f"❌ 获取所有成绩失败: {e}")
            return False
    
    def test_filter_scores(self):
        """测试成绩筛选功能"""
        print("\n🧪 测试成绩筛选功能...")
        
        test_cases = [
            {"grade": "10", "class": None, "problem": None, "desc": "按年级筛选"},
            {"grade": None, "class": "1", "problem": None, "desc": "按班级筛选"},
            {"grade": None, "class": None, "problem": "1", "desc": "按题目筛选"},
            {"grade": "10", "class": "1", "problem": None, "desc": "按年级和班级筛选"},
            {"grade": "10", "class": None, "problem": "1", "desc": "按年级和题目筛选"},
            {"grade": "10", "class": "1", "problem": "1", "desc": "按年级、班级和题目筛选"},
        ]
        
        all_passed = True
        
        for case in test_cases:
            try:
                scores = server.get_scores_by_filter(
                    grade_filter=case["grade"],
                    class_filter=case["class"],
                    problem_filter=case["problem"]
                )
                print(f"✅ {case['desc']}: 获取到 {len(scores)} 条记录")
                
                # 验证筛选结果的正确性
                for score in scores:
                    grade, class_num, username, problem_id, score_value, submission_time = score
                    
                    if case["grade"] and str(grade) != case["grade"]:
                        print(f"❌ 年级筛选错误: 期望 {case['grade']}, 实际 {grade}")
                        all_passed = False
                    
                    if case["class"] and str(class_num) != case["class"]:
                        print(f"❌ 班级筛选错误: 期望 {case['class']}, 实际 {class_num}")
                        all_passed = False
                    
                    if case["problem"] and str(problem_id) != case["problem"]:
                        print(f"❌ 题目筛选错误: 期望 {case['problem']}, 实际 {problem_id}")
                        all_passed = False
                
            except Exception as e:
                print(f"❌ {case['desc']} 失败: {e}")
                all_passed = False
        
        return all_passed
    
    def test_score_statistics(self):
        """测试成绩统计功能"""
        print("\n🧪 测试成绩统计功能...")
        
        try:
            # 获取所有成绩
            scores = server.get_all_scores()
            
            if not scores:
                print("❌ 没有成绩数据可用于统计")
                return False
            
            # 统计各种指标
            total_students = len(set((s[0], s[1], s[2]) for s in scores))  # 不重复的学生
            total_problems = len(set(s[3] for s in scores))  # 不重复的题目
            avg_score = sum(s[4] for s in scores) / len(scores)
            max_score = max(s[4] for s in scores)
            min_score = min(s[4] for s in scores)
            
            print(f"✅ 统计结果:")
            print(f"   📝 参与学生数: {total_students}")
            print(f"   📋 题目数量: {total_problems}")
            print(f"   📊 平均分: {avg_score:.2f}")
            print(f"   🏆 最高分: {max_score:.2f}")
            print(f"   📉 最低分: {min_score:.2f}")
            
            # 按年级统计
            grade_stats = {}
            for score in scores:
                grade = score[0]
                if grade not in grade_stats:
                    grade_stats[grade] = []
                grade_stats[grade].append(score[4])
            
            print(f"   🎓 各年级平均分:")
            for grade, scores_list in grade_stats.items():
                avg = sum(scores_list) / len(scores_list)
                print(f"      {grade}年级: {avg:.2f}")
            
            return True
        except Exception as e:
            print(f"❌ 成绩统计失败: {e}")
            return False
    
    def test_score_submission_simulation(self):
        """测试成绩提交模拟"""
        print("\n🧪 测试成绩提交模拟...")
        
        try:
            conn = sqlite3.connect(server.DB_FILE)
            cursor = conn.cursor()
            
            # 模拟新的成绩提交（更新现有记录）
            test_submissions = [
                ("10", "1", "张三", 1, 95.5),
                ("10", "1", "李四", 1, 88.0),
                ("11", "2", "钱七", 2, 92.3),
            ]
            
            for grade, class_num, username, problem_id, score in test_submissions:
                submission_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 使用 INSERT OR REPLACE 来更新成绩
                cursor.execute('''
                    INSERT OR REPLACE INTO scores (grade, class_num, username, problem_id, score, submission_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (grade, class_num, username, problem_id, score, submission_time))
            
            conn.commit()
            conn.close()
            
            print(f"✅ 成功模拟提交 {len(test_submissions)} 条新成绩")
            
            # 验证最新成绩查询
            latest_scores = server.get_all_scores()
            print(f"✅ 最新成绩查询返回 {len(latest_scores)} 条记录")
            
            return True
        except Exception as e:
            print(f"❌ 成绩提交模拟失败: {e}")
            return False
    
    def test_edge_cases(self):
        """测试边界情况"""
        print("\n🧪 测试边界情况...")
        
        test_cases = [
            {
                "name": "空筛选条件",
                "func": lambda: server.get_scores_by_filter(None, None, None),
                "should_succeed": True
            },
            {
                "name": "不存在的年级",
                "func": lambda: server.get_scores_by_filter("99", None, None),
                "should_succeed": True  # 应该返回空列表
            },
            {
                "name": "不存在的班级",
                "func": lambda: server.get_scores_by_filter(None, "99", None),
                "should_succeed": True
            },
            {
                "name": "不存在的题目",
                "func": lambda: server.get_scores_by_filter(None, None, "99"),
                "should_succeed": True
            },
        ]
        
        all_passed = True
        
        for case in test_cases:
            try:
                result = case["func"]()
                if case["should_succeed"]:
                    print(f"✅ {case['name']}: 成功处理，返回 {len(result) if result else 0} 条记录")
                else:
                    print(f"❌ {case['name']}: 应该失败但成功了")
                    all_passed = False
            except Exception as e:
                if case["should_succeed"]:
                    print(f"❌ {case['name']}: 意外失败 - {e}")
                    all_passed = False
                else:
                    print(f"✅ {case['name']}: 按预期失败 - {e}")
        
        return all_passed
    
    def generate_test_report(self, test_results: Dict[str, bool]):
        """生成测试报告"""
        print("\n" + "="*60)
        print("📋 成绩管理功能测试报告")
        print("="*60)
        
        total_tests = len(test_results)
        passed_tests = sum(test_results.values())
        failed_tests = total_tests - passed_tests
        
        print(f"📊 测试总数: {total_tests}")
        print(f"✅ 通过: {passed_tests}")
        print(f"❌ 失败: {failed_tests}")
        print(f"📈 通过率: {passed_tests/total_tests*100:.1f}%")
        
        print("\n📝 详细结果:")
        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {status} {test_name}")
        
        if failed_tests == 0:
            print("\n🎉 所有测试通过！成绩管理功能运行正常。")
        else:
            print(f"\n⚠️ 有 {failed_tests} 个测试失败，请检查相关功能。")
        
        print("="*60)
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始成绩管理功能测试")
        print("="*60)
        
        test_results = {}
        
        try:
            # 设置测试环境
            self.setup_test_environment()
            
            # 创建测试数据
            students = self.create_test_students()
            self.create_test_scores(students)
            
            # 运行各项测试
            test_results["获取所有成绩"] = self.test_get_all_scores()
            test_results["成绩筛选功能"] = self.test_filter_scores()
            test_results["成绩统计功能"] = self.test_score_statistics()
            test_results["成绩提交模拟"] = self.test_score_submission_simulation()
            test_results["边界情况处理"] = self.test_edge_cases()
            
        except Exception as e:
            print(f"❌ 测试执行过程中出现严重错误: {e}")
            test_results["测试执行"] = False
        
        finally:
            # 清理测试环境
            self.cleanup_test_environment()
        
        # 生成测试报告
        self.generate_test_report(test_results)
        
        return test_results

def main():
    """主函数"""
    tester = ScoreManagementTester()
    tester.run_all_tests()

if __name__ == '__main__':
    main()
