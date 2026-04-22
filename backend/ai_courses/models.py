import os
import glob
import uuid
import datetime
import subprocess
from django.db import models
from django.conf import settings


class Problem(models.Model):
    """
    AI课题目模型。
    注意：测试点文件（input*.txt / output*.txt）仍然存储在文件系统，
    不在数据库中，以兼容现有的 problems/ 目录结构。
    """
    problem_id = models.CharField('题目ID', max_length=50, unique=True)  # 如 "problem1"
    title = models.CharField('标题', max_length=200, blank=True)
    description = models.TextField('题目描述', blank=True)
    difficulty = models.CharField('难度', max_length=20, blank=True)
    course = models.CharField('所属课程', max_length=10, choices=[('ai', '人工智能课'), ('info', '信息科技课')], default='ai')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'AI课题目'
        verbose_name_plural = 'AI课题目'
        ordering = ['problem_id']

    def __str__(self):
        return self.problem_id

    def get_problem_dir(self):
        """获取题目文件目录的绝对路径，ai课在problems/ai/下，信息课在problems/下"""
        if self.course == 'ai':
            return settings.PROBLEMS_DIR / 'ai' / self.problem_id
        return settings.PROBLEMS_DIR / self.problem_id

    def get_test_cases(self):
        """
        读取并返回所有测试点。
        支持两种文件命名约定：
          1. input1.txt / output1.txt（优先）
          2. 1.in / 1.out
        返回格式：[{'number': 1, 'input': '...', 'output': '...'}, ...]
        """
        problem_dir = self.get_problem_dir()
        if not os.path.exists(problem_dir):
            return []

        # 策略1：从 tests/ 子目录或根目录找 input*.txt / output*.txt
        tests_dir = os.path.join(problem_dir, 'tests')
        for search_dir in ([tests_dir] if os.path.exists(tests_dir) else [problem_dir]):
            input_files = sorted(glob.glob(os.path.join(search_dir, 'input*.txt')))
            if input_files:
                test_cases = []
                for i, input_file in enumerate(input_files, 1):
                    output_file = input_file.replace('input', 'output')
                    try:
                        with open(input_file, 'r', encoding='utf-8') as f:
                            input_content = f.read()
                    except UnicodeDecodeError:
                        with open(input_file, 'r', encoding='gbk') as f:
                            input_content = f.read()
                    try:
                        with open(output_file, 'r', encoding='utf-8') as f:
                            output_content = f.read().strip()
                    except UnicodeDecodeError:
                        with open(output_file, 'r', encoding='gbk') as f:
                            output_content = f.read().strip()
                    test_cases.append({
                        'number': i,
                        'input': input_content,
                        'output': output_content,
                    })
                return test_cases

        # 策略2：查找 1.in / 1.out 配对
        test_cases = []
        i = 1
        while True:
            input_file = os.path.join(problem_dir, f'{i}.in')
            output_file = os.path.join(problem_dir, f'{i}.out')
            if not (os.path.exists(input_file) and os.path.exists(output_file)):
                break
            try:
                with open(input_file, 'r', encoding='utf-8') as f:
                    input_content = f.read()
            except UnicodeDecodeError:
                with open(input_file, 'r', encoding='gbk') as f:
                    input_content = f.read()
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    output_content = f.read().strip()
            except UnicodeDecodeError:
                with open(output_file, 'r', encoding='gbk') as f:
                    output_content = f.read().strip()
            test_cases.append({'number': i, 'input': input_content, 'output': output_content})
            i += 1

        return test_cases

    def get_test_count(self):
        """返回测试点数量"""
        return len(self.get_test_cases())

    @classmethod
    def sync_from_disk(cls):
        """
        从 problems/ai/ 和 problems/ 目录同步题目列表到数据库。
        problems/ai/  → course='ai'
        problems/根目录 → course='info'
        """
        problems_dir = settings.PROBLEMS_DIR
        created_ids = []
        updated_ids = []

        if not os.path.exists(problems_dir):
            return created_ids, updated_ids

        # 定义扫描规则：(子目录名或None表示根目录, 课程名)
        scans = [
            ('ai', 'ai'),      # problems/ai/ → AI课
            (None, 'info'),    # problems/根目录 → 信息课
        ]

        for subdir, course in scans:
            scan_dir = os.path.join(problems_dir, subdir) if subdir else problems_dir
            if not os.path.exists(scan_dir):
                continue

            for item in os.listdir(scan_dir):
                item_path = os.path.join(scan_dir, item)
                if not os.path.isdir(item_path) or not item.startswith('problem'):
                    continue

                description_path = os.path.join(item_path, 'description.txt')
                description = ''
                if os.path.exists(description_path):
                    try:
                        with open(description_path, 'r', encoding='utf-8') as f:
                            description = f.read()
                    except UnicodeDecodeError:
                        try:
                            with open(description_path, 'r', encoding='gbk') as f:
                                description = f.read()
                        except Exception:
                            pass

                # 读取难度（可选，从单独的 metadata 文件或 description 第一行）
                difficulty = ''
                metadata_path = os.path.join(item_path, 'metadata.txt')
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                if line.startswith('difficulty:'):
                                    difficulty = line.split(':', 1)[1].strip()
                                    break
                    except Exception:
                        pass

                obj, created = cls.objects.update_or_create(
                    problem_id=item,
                    defaults={
                        'title': item,
                        'description': description,
                        'course': course,
                        'difficulty': difficulty,
                    }
                )
                if created:
                    created_ids.append(item)
                else:
                    updated_ids.append(item)

        return created_ids, updated_ids


class Submission(models.Model):
    """学生提交记录"""
    STATUS_CHOICES = [
        ('pending', '待批改'),
        ('running', '批改中'),
        ('accepted', '通过'),
        ('wrong_answer', '答案错误'),
        ('runtime_error', '运行时错误'),
        ('timeout', '超时'),
        ('error', '系统错误'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_submissions'
    )
    problem = models.ForeignKey(
        Problem,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    code = models.TextField('提交代码')
    score = models.FloatField('得分', default=0)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField('错误信息', blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'AI课提交记录'
        verbose_name_plural = 'AI课提交记录'
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.user.username} - {self.problem.problem_id} ({self.score}分)"


def grade_submission(submission_path, problem):
    """
    自动批改学生提交的代码。

    参数:
        submission_path: 学生代码文件的绝对路径
        problem: Problem 实例

    返回:
        (success: bool, result: str, score: float)
    """
    problem_dir = problem.get_problem_dir()
    if not os.path.exists(problem_dir):
        return False, "找不到指定的题目文件夹。", 0

    test_cases = problem.get_test_cases()
    total_tests = len(test_cases)
    passed_tests = 0
    test_results = []

    for i, test_case in enumerate(test_cases, 1):
        test_input = test_case['input']
        correct_output = test_case['output']

        try:
            result = subprocess.run(
                ['python', submission_path],
                input=test_input,
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            student_output = result.stdout.strip()

            if student_output == correct_output:
                test_results.append(f"测试点 {i}: 通过")
                passed_tests += 1
            else:
                test_results.append(
                    f"测试点 {i}: 失败\n"
                    f"你的输出：'{student_output}'\n"
                    f"正确输出：'{correct_output}'"
                )
        except subprocess.CalledProcessError as e:
            test_results.append(f"测试点 {i}: 代码执行错误：\n{e.stderr}")
        except subprocess.TimeoutExpired:
            test_results.append(f"测试点 {i}: 代码执行超时（5秒）！")
        except Exception as e:
            test_results.append(f"测试点 {i}: 意外错误：{e}")

    score = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    summary = f"总分: {passed_tests}/{total_tests} (得分率: {score:.2f}%)"
    full_report = '\n'.join(test_results)

    return True, f"{summary}\n\n详细报告：\n{full_report}", score
