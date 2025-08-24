#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成绩管理性能测试模块
测试大量数据情况下的查询和筛选性能
"""

import sqlite3
import os
import sys
import random
import datetime
import time
from typing import List, Dict, Tuple

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
import server

class ScorePerformanceTester:
    """成绩管理性能测试类"""
    
    def __init__(self):
        self.test_db = "test_performance.db"
        self.original_db = server.DB_FILE
        
    def setup_large_dataset(self, num_students=1000, num_problems=50, submissions_per_student=100):
        """创建大型测试数据集"""
        print(f"🏗️ 创建大型测试数据集...")
        print(f"   学生数量: {num_students}")
        print(f"   题目数量: {num_problems}")
        print(f"   每学生提交次数: {submissions_per_student}")
        
        # 使用测试数据库
        server.DB_FILE = self.test_db
        
        # 删除已存在的测试数据库
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        
        # 初始化数据库
        server.setup_database()
        
        conn = sqlite3.connect(server.DB_FILE)
        cursor = conn.cursor()
        
        start_time = time.time()
        
        # 创建学生数据
        print("📝 创建学生数据...")
        grades = ["10", "11", "12"]
        classes = ["1", "2", "3", "4", "5"]
        
        students = []
        for i in range(num_students):
            grade = random.choice(grades)
            class_num = random.choice(classes)
            username = f"student_{i:04d}"
            password = "123456"
            
            # 注册学生
            server.register_user(grade, class_num, username, password)
            students.append((grade, class_num, username))
        
        print(f"✅ 创建了 {len(students)} 个学生账户")
        
        # 创建成绩数据
        print("📊 创建成绩数据...")
        
        # 批量插入成绩数据以提高性能
        score_data = []
        
        for grade, class_num, username in students:
            # 为每个学生随机选择一些题目提交
            selected_problems = random.sample(range(1, num_problems + 1), 
                                            min(submissions_per_student, num_problems))
            
            for problem_id in selected_problems:
                # 每个学生每个题目只记录一次最终成绩
                score = random.uniform(0, 100)
                submission_time = datetime.datetime.now() - datetime.timedelta(
                    days=random.randint(0, 90),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )
                
                score_data.append((
                    grade, class_num, username, problem_id, score,
                    submission_time.strftime('%Y-%m-%d %H:%M:%S')
                ))
        
        # 批量插入，使用 INSERT OR REPLACE 处理重复
        cursor.executemany('''
            INSERT OR REPLACE INTO scores (grade, class_num, username, problem_id, score, submission_time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', score_data)
        
        conn.commit()
        conn.close()
        
        creation_time = time.time() - start_time
        print(f"✅ 数据集创建完成！")
        print(f"   总成绩记录: {len(score_data):,}")
        print(f"   创建耗时: {creation_time:.2f} 秒")
        
        return len(students), len(score_data)
    
    def measure_query_performance(self, query_func, description, *args, **kwargs):
        """测量查询性能"""
        print(f"\n⏱️ 测试: {description}")
        
        # 预热查询
        query_func(*args, **kwargs)
        
        # 多次测试取平均值
        times = []
        for i in range(5):
            start_time = time.time()
            result = query_func(*args, **kwargs)
            end_time = time.time()
            times.append(end_time - start_time)
        
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        print(f"   结果数量: {len(result):,} 条")
        print(f"   平均耗时: {avg_time:.4f} 秒")
        print(f"   最快耗时: {min_time:.4f} 秒")
        print(f"   最慢耗时: {max_time:.4f} 秒")
        
        return {
            'result_count': len(result),
            'avg_time': avg_time,
            'min_time': min_time,
            'max_time': max_time
        }
    
    def test_basic_queries(self):
        """测试基本查询性能"""
        print("\n🧪 基本查询性能测试")
        print("-" * 40)
        
        results = {}
        
        # 测试获取所有成绩
        results['get_all_scores'] = self.measure_query_performance(
            server.get_all_scores, "获取所有成绩"
        )
        
        return results
    
    def test_filtered_queries(self):
        """测试筛选查询性能"""
        print("\n🧪 筛选查询性能测试")
        print("-" * 40)
        
        results = {}
        
        # 测试不同的筛选条件
        test_cases = [
            ("grade_filter", "按年级筛选", {"grade_filter": "10"}),
            ("class_filter", "按班级筛选", {"class_filter": "1"}),
            ("problem_filter", "按题目筛选", {"problem_filter": "1"}),
            ("grade_class_filter", "按年级+班级筛选", {"grade_filter": "10", "class_filter": "1"}),
            ("all_filters", "全部筛选条件", {"grade_filter": "10", "class_filter": "1", "problem_filter": "1"}),
        ]
        
        for key, description, kwargs in test_cases:
            results[key] = self.measure_query_performance(
                server.get_scores_by_filter, description, **kwargs
            )
        
        return results
    
    def test_concurrent_queries(self):
        """测试并发查询（模拟多用户访问）"""
        print("\n🧪 并发查询测试")
        print("-" * 40)
        
        import threading
        import queue
        
        def worker(query_queue, result_queue):
            """工作线程函数"""
            while True:
                try:
                    query_func, args, kwargs = query_queue.get(timeout=1)
                    start_time = time.time()
                    result = query_func(*args, **kwargs)
                    end_time = time.time()
                    result_queue.put({
                        'success': True,
                        'time': end_time - start_time,
                        'count': len(result)
                    })
                    query_queue.task_done()
                except queue.Empty:
                    break
                except Exception as e:
                    result_queue.put({
                        'success': False,
                        'error': str(e),
                        'time': 0,
                        'count': 0
                    })
                    query_queue.task_done()
        
        # 准备查询任务
        query_queue = queue.Queue()
        result_queue = queue.Queue()
        
        # 添加多种查询任务
        for _ in range(10):
            query_queue.put((server.get_all_scores, (), {}))
            query_queue.put((server.get_scores_by_filter, (), {"grade_filter": "10"}))
            query_queue.put((server.get_scores_by_filter, (), {"class_filter": "1"}))
        
        # 启动多个工作线程
        num_threads = 5
        threads = []
        
        start_time = time.time()
        
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(query_queue, result_queue))
            t.start()
            threads.append(t)
        
        # 等待所有任务完成
        query_queue.join()
        
        # 等待所有线程结束
        for t in threads:
            t.join()
        
        end_time = time.time()
        
        # 收集结果
        results = []
        while not result_queue.empty():
            results.append(result_queue.get())
        
        successful_queries = [r for r in results if r['success']]
        failed_queries = [r for r in results if not r['success']]
        
        print(f"   总查询数: {len(results)}")
        print(f"   成功查询: {len(successful_queries)}")
        print(f"   失败查询: {len(failed_queries)}")
        print(f"   总耗时: {end_time - start_time:.2f} 秒")
        
        if successful_queries:
            avg_query_time = sum(r['time'] for r in successful_queries) / len(successful_queries)
            print(f"   平均查询时间: {avg_query_time:.4f} 秒")
        
        return {
            'total_queries': len(results),
            'successful_queries': len(successful_queries),
            'failed_queries': len(failed_queries),
            'total_time': end_time - start_time,
            'avg_query_time': avg_query_time if successful_queries else 0
        }
    
    def test_memory_usage(self):
        """测试内存使用情况"""
        print("\n🧪 内存使用测试")
        print("-" * 40)
        
        try:
            import psutil
            import gc
            
            process = psutil.Process()
            
            # 垃圾回收
            gc.collect()
            
            # 测试前内存使用
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # 执行大查询
            start_time = time.time()
            all_scores = server.get_all_scores()
            query_time = time.time() - start_time
            
            # 测试后内存使用
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_used = memory_after - memory_before
            
            print(f"   查询前内存: {memory_before:.2f} MB")
            print(f"   查询后内存: {memory_after:.2f} MB")
            print(f"   内存增长: {memory_used:.2f} MB")
            print(f"   查询耗时: {query_time:.4f} 秒")
            print(f"   记录数量: {len(all_scores):,}")
            
            # 释放内存
            del all_scores
            gc.collect()
            
            return {
                'memory_before': memory_before,
                'memory_after': memory_after,
                'memory_used': memory_used,
                'query_time': query_time
            }
            
        except ImportError:
            print("   ⚠️ psutil 库未安装，跳过内存测试")
            return None
    
    def generate_performance_report(self, results):
        """生成性能测试报告"""
        print("\n" + "="*60)
        print("📊 成绩管理性能测试报告")
        print("="*60)
        
        # 基本查询性能
        if 'basic' in results:
            print("\n📈 基本查询性能:")
            basic = results['basic']['get_all_scores']
            print(f"   获取所有成绩: {basic['avg_time']:.4f}s (记录数: {basic['result_count']:,})")
        
        # 筛选查询性能
        if 'filtered' in results:
            print("\n🔍 筛选查询性能:")
            for key, data in results['filtered'].items():
                print(f"   {key}: {data['avg_time']:.4f}s (记录数: {data['result_count']:,})")
        
        # 并发查询性能
        if 'concurrent' in results:
            print("\n🚀 并发查询性能:")
            concurrent = results['concurrent']
            print(f"   总查询数: {concurrent['total_queries']}")
            print(f"   成功率: {concurrent['successful_queries']/concurrent['total_queries']*100:.1f}%")
            print(f"   平均查询时间: {concurrent['avg_query_time']:.4f}s")
        
        # 内存使用
        if 'memory' in results and results['memory']:
            print("\n💾 内存使用情况:")
            memory = results['memory']
            print(f"   查询内存增长: {memory['memory_used']:.2f} MB")
            print(f"   查询耗时: {memory['query_time']:.4f}s")
        
        # 性能建议
        print("\n💡 性能优化建议:")
        
        if 'basic' in results:
            basic_time = results['basic']['get_all_scores']['avg_time']
            if basic_time > 1.0:
                print("   ⚠️ 基本查询较慢，考虑添加数据库索引")
            else:
                print("   ✅ 基本查询性能良好")
        
        if 'concurrent' in results:
            success_rate = results['concurrent']['successful_queries'] / results['concurrent']['total_queries']
            if success_rate < 0.95:
                print("   ⚠️ 并发查询成功率较低，考虑优化数据库连接管理")
            else:
                print("   ✅ 并发查询处理良好")
        
        print("="*60)
    
    def run_performance_tests(self, scale='medium'):
        """运行性能测试"""
        print("🚀 开始成绩管理性能测试")
        print("="*60)
        
        # 根据规模设置参数
        scale_configs = {
            'small': {'students': 100, 'problems': 10, 'submissions': 20},
            'medium': {'students': 500, 'problems': 25, 'submissions': 50},
            'large': {'students': 1000, 'problems': 50, 'submissions': 100}
        }
        
        config = scale_configs.get(scale, scale_configs['medium'])
        
        results = {}
        
        try:
            # 设置大型数据集
            num_students, num_scores = self.setup_large_dataset(
                config['students'], config['problems'], config['submissions']
            )
            
            print(f"\n📊 数据集规模: {num_students} 学生, {num_scores:,} 成绩记录")
            
            # 运行各项性能测试
            results['basic'] = self.test_basic_queries()
            results['filtered'] = self.test_filtered_queries()
            results['concurrent'] = self.test_concurrent_queries()
            results['memory'] = self.test_memory_usage()
            
        except Exception as e:
            print(f"❌ 性能测试过程中出现错误: {e}")
        
        finally:
            # 清理测试环境
            server.DB_FILE = self.original_db
            if os.path.exists(self.test_db):
                os.remove(self.test_db)
        
        # 生成报告
        self.generate_performance_report(results)
        
        return results

def main():
    """主函数"""
    print("选择测试规模:")
    print("1. 小规模 (100学生, 10题目)")
    print("2. 中等规模 (500学生, 25题目)")
    print("3. 大规模 (1000学生, 50题目)")
    
    choice = input("请选择 (1-3, 默认2): ").strip()
    
    scale_map = {'1': 'small', '2': 'medium', '3': 'large'}
    scale = scale_map.get(choice, 'medium')
    
    tester = ScorePerformanceTester()
    tester.run_performance_tests(scale)

if __name__ == '__main__':
    main()
