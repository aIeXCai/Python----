# 成绩管理测试快速参考

## 🚀 快速命令

```bash
# 切换到测试目录
cd tests/ScoreModule

# 运行所有测试
python run_score_tests.py

# 只运行功能测试
python test_score_management.py

# 只运行性能测试 (小规模)
echo 1 | python test_score_performance.py

# 清理测试数据
python clean_test_data.py
```

## 📊 测试结果速览

### 功能测试 ✅
- 获取所有成绩 ✅
- 成绩筛选功能 ✅  
- 成绩统计功能 ✅
- 成绩提交模拟 ✅
- 边界情况处理 ✅

### 性能测试 ✅
- 基础查询: < 0.01s
- 筛选查询: < 0.003s  
- 并发成功率: > 95%

## 🔧 常见修复

### 约束错误
```python
# 使用 INSERT OR REPLACE 替代 INSERT
cursor.execute('''
    INSERT OR REPLACE INTO scores (...)
    VALUES (?, ?, ?, ?, ?, ?)
''', data)
```

### 路径问题
```python
# 正确的路径设置
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
```

## 📈 测试规模

| 规模 | 学生数 | 题目数 | 记录数 |
|------|--------|--------|--------|
| 小   | 100    | 10     | ~1K    |
| 中   | 500    | 25     | ~12K   |  
| 大   | 1000   | 50     | ~50K   |

选择合适的规模进行测试，避免过度消耗资源。
