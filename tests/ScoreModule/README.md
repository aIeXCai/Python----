# 成绩管理模块测试攻略

## 📋 概览

本文档提供了Python学习网站成绩管理模块的完整测试攻略，包括功能测试、性能测试和使用指南。

## 📁 文件结构

```
tests/ScoreModule/
├── test_score_management.py     # 功能测试模块
├── test_score_performance.py    # 性能测试模块
├── run_score_tests.py          # 测试套件运行器
├── clean_test_data.py          # 测试数据清理工具
└── README.md                   # 本文档
```

## 🎯 测试目标

### 主要测试功能
- ✅ 成绩数据的增删改查 (CRUD)
- ✅ 多条件筛选和查询
- ✅ 成绩统计和分析
- ✅ 数据完整性验证
- ✅ 并发访问性能
- ✅ 边界情况处理

### 测试覆盖范围
- **数据库操作**: 测试所有成绩相关的数据库操作
- **查询性能**: 验证大数据量下的查询效率
- **数据一致性**: 确保数据约束和一致性规则
- **错误处理**: 测试异常情况的处理能力

## 🚀 快速开始

### 环境要求
- Python 3.6+
- SQLite3
- 可选: psutil (用于内存监控)

### 安装依赖
```bash
pip install psutil  # 可选，用于性能测试中的内存监控
```

### 运行测试

#### 1. 使用测试套件运行器 (推荐)
```bash
cd tests/ScoreModule
python run_score_tests.py
```

#### 2. 单独运行功能测试
```bash
cd tests/ScoreModule
python test_score_management.py
```

#### 3. 单独运行性能测试
```bash
cd tests/ScoreModule
python test_score_performance.py
```

## 📊 测试模块详解

### 1. 功能测试模块 (`test_score_management.py`)

#### 测试用例
| 测试项目 | 描述 | 验证要点 |
|---------|------|----------|
| `test_get_all_scores` | 获取所有成绩 | 数据完整性、结构正确性 |
| `test_filter_scores` | 成绩筛选功能 | 各种筛选条件的准确性 |
| `test_score_statistics` | 成绩统计功能 | 统计计算的正确性 |
| `test_score_submission_simulation` | 成绩提交模拟 | 数据更新机制 |
| `test_edge_cases` | 边界情况测试 | 异常处理能力 |

#### 测试数据
- **学生数量**: 6个测试学生
- **年级分布**: 10-12年级
- **班级分布**: 1-2班
- **题目数量**: 5道题目
- **成绩范围**: 60-100分

#### 运行示例
```bash
🚀 开始成绩管理功能测试
============================================================
🔧 设置测试环境...
✅ 测试数据库初始化完成
📊 创建测试成绩数据...
✅ 测试成绩数据创建完成

🧪 测试获取所有成绩功能...
✅ 成功获取 30 条成绩记录
✅ 成绩数据结构正确

🧪 测试成绩筛选功能...
✅ 按年级筛选: 获取到 15 条记录
✅ 按班级筛选: 获取到 20 条记录
...

📋 成绩管理功能测试报告
============================================================
📊 测试总数: 5
✅ 通过: 5 ❌ 失败: 0 📈 通过率: 100.0%
```

### 2. 性能测试模块 (`test_score_performance.py`)

#### 测试规模选择
| 规模 | 学生数 | 题目数 | 成绩记录数 | 适用场景 |
|------|--------|--------|------------|----------|
| 小规模 | 100 | 10 | ~1,000 | 开发测试 |
| 中等规模 | 500 | 25 | ~12,500 | 预生产测试 |
| 大规模 | 1,000 | 50 | ~50,000 | 压力测试 |

#### 性能指标
- **查询响应时间**: 各类查询的平均响应时间
- **并发处理能力**: 多线程访问的成功率
- **内存使用情况**: 大查询时的内存占用
- **数据创建速度**: 批量数据插入性能

#### 测试项目
1. **基础查询性能**
   - 获取所有成绩
   - 基础筛选查询

2. **高级筛选性能**
   - 单条件筛选
   - 多条件组合筛选
   - 复杂查询优化

3. **并发访问测试**
   - 多线程同时查询
   - 并发成功率统计
   - 平均响应时间

4. **内存使用测试**
   - 大查询内存占用
   - 内存释放情况

#### 性能基准
根据测试结果，以下是性能基准参考：

| 测试项目 | 小规模 (1K记录) | 中等规模 (12K记录) | 大规模 (50K记录) |
|----------|-----------------|-------------------|------------------|
| 获取所有成绩 | < 0.01s | < 0.05s | < 0.2s |
| 筛选查询 | < 0.003s | < 0.01s | < 0.05s |
| 并发成功率 | > 95% | > 90% | > 85% |

### 3. 测试套件运行器 (`run_score_tests.py`)

#### 功能特性
- **依赖检查**: 自动检查测试环境和依赖
- **交互式菜单**: 用户友好的操作界面
- **统一报告**: 汇总所有测试结果
- **错误处理**: 优雅处理测试异常

#### 使用方法
```bash
python run_score_tests.py

🧪 成绩管理测试套件
========================================
1. 功能测试 - 测试基本功能正确性
2. 性能测试 - 测试大数据量下的性能
3. 运行所有测试
4. 退出
----------------------------------------
请选择操作 (1-4):
```

## 🔧 自定义测试

### 修改测试数据
在 `test_score_management.py` 中修改 `create_test_students()` 方法：

```python
def create_test_students(self) -> List[Tuple[str, str, str, str]]:
    students = [
        # 添加更多测试学生
        ("10", "1", "自定义学生", "123456"),
        # ...
    ]
    return students
```

### 调整性能测试规模
在 `test_score_performance.py` 中修改规模配置：

```python
scale_configs = {
    'custom': {'students': 200, 'problems': 15, 'submissions': 30},
    # ...
}
```

### 添加新的测试用例
在测试类中添加新方法：

```python
def test_custom_functionality(self):
    """自定义测试用例"""
    # 测试逻辑
    pass
```

## 📈 测试报告解读

### 功能测试报告
```
📋 成绩管理功能测试报告
============================================================
📊 测试总数: 5
✅ 通过: 5
❌ 失败: 0
📈 通过率: 100.0%

📝 详细结果:
   ✅ PASS 获取所有成绩
   ✅ PASS 成绩筛选功能
   ✅ PASS 成绩统计功能
   ✅ PASS 成绩提交模拟
   ✅ PASS 边界情况处理
```

### 性能测试报告
```
📊 成绩管理性能测试报告
============================================================

📈 基本查询性能:
   获取所有成绩: 0.0058s (记录数: 1,000)

🔍 筛选查询性能:
   grade_filter: 0.0000s (记录数: 320)
   class_filter: 0.0010s (记录数: 190)
   problem_filter: 0.0026s (记录数: 100)

🚀 并发查询性能:
   总查询数: 30
   成功率: 100.0%
   平均查询时间: 0.0012s

💾 内存使用情况:
   查询内存增长: 1.2 MB
   查询耗时: 0.0058s
```

## 🚨 常见问题和解决方案

### 1. 数据库约束错误
**问题**: `UNIQUE constraint failed: scores.grade, scores.class_num, scores.username, scores.problem_id`

**原因**: 成绩表有唯一约束，每个学生每道题只能有一条记录。

**解决方案**: 使用 `INSERT OR REPLACE` 替代 `INSERT`：
```python
cursor.execute('''
    INSERT OR REPLACE INTO scores (grade, class_num, username, problem_id, score, submission_time)
    VALUES (?, ?, ?, ?, ?, ?)
''', data)
```

### 2. 模块导入错误
**问题**: `ModuleNotFoundError: No module named 'server'`

**解决方案**: 检查路径设置，确保正确添加到 Python 路径：
```python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
```

### 3. 性能测试过慢
**问题**: 大规模测试耗时过长

**解决方案**: 
- 使用小规模测试进行开发
- 使用批量插入 `executemany()`
- 考虑添加数据库索引

### 4. 并发测试失败
**问题**: 并发访问时出现数据库锁定

**解决方案**:
- 减少并发线程数量
- 增加超时时间
- 使用连接池

## 🔄 持续集成

### 自动化测试脚本
创建 `ci_test.bat` (Windows) 或 `ci_test.sh` (Linux/Mac)：

```bash
#!/bin/bash
echo "运行成绩管理模块测试..."
cd tests/ScoreModule
python test_score_management.py
if [ $? -eq 0 ]; then
    echo "✅ 功能测试通过"
    echo "1" | python test_score_performance.py
    if [ $? -eq 0 ]; then
        echo "✅ 性能测试通过"
        echo "🎉 所有测试完成"
    else
        echo "❌ 性能测试失败"
        exit 1
    fi
else
    echo "❌ 功能测试失败"
    exit 1
fi
```

### GitHub Actions 配置
```yaml
name: Score Module Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.8
    - name: Install dependencies
      run: pip install psutil
    - name: Run tests
      run: |
        cd tests/ScoreModule
        python test_score_management.py
```

## 📚 扩展阅读

### 相关文档
- [Python学习网站架构文档](../../docs/architecture.md)
- [数据库设计说明](../../docs/database.md)
- [API接口文档](../../docs/api.md)

### 最佳实践
1. **测试隔离**: 每个测试使用独立的测试数据库
2. **数据清理**: 测试完成后及时清理测试数据
3. **版本控制**: 不要提交测试数据库文件
4. **文档更新**: 测试用例变更时同步更新文档

### 性能优化建议
1. **数据库索引**: 为常用查询字段添加索引
2. **查询优化**: 避免 N+1 查询问题
3. **缓存机制**: 对频繁查询的数据使用缓存
4. **分页处理**: 大数据量查询使用分页

## 📞 支持和反馈

如果在使用测试模块时遇到问题，请：

1. 检查本文档的常见问题部分
2. 查看测试日志和错误信息
3. 确保测试环境配置正确
4. 联系开发团队获取技术支持

---

**最后更新**: 2025年8月23日  
**版本**: 1.0.0  
**维护者**: Python学习网站开发团队
