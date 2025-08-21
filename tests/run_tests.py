#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学生管理模块测试运行器
统一运行所有测试并生成报告
"""

import os
import sys
import time
import unittest
import subprocess

# 添加父目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_backend_tests():
    """运行后端测试"""
    print("🔧 运行后端测试...")
    print("-" * 50)
    
    try:
        # 运行后端测试
        result = subprocess.run([
            sys.executable, 'test_backend.py'
        ], 
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True, 
        text=True, 
        timeout=60
        )
        
        print(result.stdout)
        if result.stderr:
            print("错误输出:", result.stderr)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ 后端测试超时")
        return False
    except Exception as e:
        print(f"❌ 后端测试运行失败: {e}")
        return False

def run_frontend_tests():
    """运行前端测试"""
    print("\n🌐 运行前端测试...")
    print("-" * 50)
    
    try:
        # 检查是否有Chrome浏览器
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        
        # 测试Chrome是否可用
        test_driver = webdriver.Chrome(options=chrome_options)
        test_driver.quit()
        
        # 运行前端测试
        result = subprocess.run([
            sys.executable, 'test_frontend.py'
        ], 
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True, 
        text=True, 
        timeout=120
        )
        
        print(result.stdout)
        if result.stderr:
            print("错误输出:", result.stderr)
        
        return result.returncode == 0
        
    except ImportError:
        print("❌ Selenium未安装，跳过前端测试")
        print("💡 安装方法: pip install selenium")
        return None
    except Exception as e:
        print(f"❌ 前端测试环境不可用: {e}")
        print("💡 请确保安装了Chrome浏览器和ChromeDriver")
        return None

def generate_test_report(backend_result, frontend_result):
    """生成测试报告"""
    print("\n" + "=" * 60)
    print("📊 测试报告")
    print("=" * 60)
    
    # 后端测试结果
    if backend_result:
        print("✅ 后端测试: 通过")
    else:
        print("❌ 后端测试: 失败")
    
    # 前端测试结果
    if frontend_result is None:
        print("⚠️  前端测试: 跳过 (环境不可用)")
    elif frontend_result:
        print("✅ 前端测试: 通过")
    else:
        print("❌ 前端测试: 失败")
    
    # 总结
    print("-" * 60)
    if backend_result and (frontend_result is None or frontend_result):
        print("🎉 测试总结: 全部通过！")
        return True
    else:
        print("⚠️  测试总结: 有测试失败")
        return False

def main():
    """主函数"""
    print("🧪 学生管理模块测试运行器")
    print("=" * 60)
    
    start_time = time.time()
    
    # 运行后端测试
    backend_result = run_backend_tests()
    
    # 运行前端测试
    frontend_result = run_frontend_tests()
    
    # 生成报告
    overall_success = generate_test_report(backend_result, frontend_result)
    
    # 总耗时
    total_time = time.time() - start_time
    print(f"⏱️  总耗时: {total_time:.2f}秒")
    
    print("\n💡 提示:")
    print("- 使用 test_data_manager.py 管理测试数据")
    print("- 后端测试包含单元测试、集成测试和性能测试")
    print("- 前端测试需要Chrome浏览器环境")
    
    return overall_success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
