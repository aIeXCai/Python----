#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成绩管理测试套件运行器
统一运行所有成绩管理相关的测试
"""

import os
import sys
import importlib

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.dirname(os.path.dirname(current_dir)))

def run_test_module(module_name, description):
    """运行指定的测试模块"""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print(f"{'='*60}")
    
    try:
        # 动态导入测试模块
        module = importlib.import_module(module_name)
        
        # 运行测试
        if hasattr(module, 'main'):
            module.main()
        else:
            print(f"❌ 模块 {module_name} 没有 main() 函数")
            return False
        
        print(f"✅ {description} 完成")
        return True
        
    except ImportError as e:
        print(f"❌ 无法导入模块 {module_name}: {e}")
        return False
    except Exception as e:
        print(f"❌ 运行 {description} 时出错: {e}")
        return False

def show_menu():
    """显示测试菜单"""
    print("🧪 成绩管理测试套件")
    print("="*40)
    print("1. 功能测试 - 测试基本功能正确性")
    print("2. 性能测试 - 测试大数据量下的性能")
    print("3. 运行所有测试")
    print("4. 退出")
    print("-"*40)

def run_functional_tests():
    """运行功能测试"""
    return run_test_module('test_score_management', '成绩管理功能测试')

def run_performance_tests():
    """运行性能测试"""
    return run_test_module('test_score_performance', '成绩管理性能测试')

def run_all_tests():
    """运行所有测试"""
    print("🚀 运行成绩管理完整测试套件")
    print("="*60)
    
    results = {
        '功能测试': run_functional_tests(),
        '性能测试': run_performance_tests()
    }
    
    # 生成总体报告
    print(f"\n{'='*60}")
    print("📋 测试套件总体报告")
    print(f"{'='*60}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    print(f"📊 测试模块总数: {total_tests}")
    print(f"✅ 通过模块: {passed_tests}")
    print(f"❌ 失败模块: {total_tests - passed_tests}")
    print(f"📈 通过率: {passed_tests/total_tests*100:.1f}%")
    
    print("\n📝 详细结果:")
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
    
    if all(results.values()):
        print("\n🎉 所有测试模块都通过了！")
    else:
        print("\n⚠️ 部分测试模块失败，请检查上面的详细输出。")
    
    print("="*60)

def check_dependencies():
    """检查测试依赖"""
    print("🔍 检查测试依赖...")
    
    # 检查服务器模块
    try:
        import server
        print("✅ server.py 模块可用")
    except ImportError:
        print("❌ 找不到 server.py 模块")
        return False
    
    # 检查数据库函数
    required_functions = [
        'get_all_scores',
        'get_scores_by_filter',
        'setup_database',
        'register_user'
    ]
    
    missing_functions = []
    for func_name in required_functions:
        if not hasattr(server, func_name):
            missing_functions.append(func_name)
    
    if missing_functions:
        print(f"❌ 缺少以下必需函数: {', '.join(missing_functions)}")
        return False
    
    print("✅ 所有必需的函数都可用")
    
    # 检查可选依赖
    optional_deps = {
        'psutil': '性能测试中的内存监控'
    }
    
    for dep, purpose in optional_deps.items():
        try:
            importlib.import_module(dep)
            print(f"✅ {dep} 可用 ({purpose})")
        except ImportError:
            print(f"⚠️ {dep} 不可用，将跳过 {purpose}")
    
    return True

def main():
    """主函数"""
    print("🧪 成绩管理测试套件启动器")
    print("="*60)
    
    # 检查依赖
    if not check_dependencies():
        print("❌ 依赖检查失败，无法运行测试")
        return
    
    while True:
        print()
        show_menu()
        
        try:
            choice = input("请选择操作 (1-4): ").strip()
            
            if choice == '1':
                run_functional_tests()
            elif choice == '2':
                run_performance_tests()
            elif choice == '3':
                run_all_tests()
            elif choice == '4':
                print("👋 退出测试套件")
                break
            else:
                print("❌ 无效选择，请输入 1-4")
                
        except KeyboardInterrupt:
            print("\n\n👋 用户中断，退出测试套件")
            break
        except Exception as e:
            print(f"❌ 操作失败: {e}")

if __name__ == '__main__':
    main()
