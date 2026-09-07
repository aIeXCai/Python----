import os
import glob
from dataclasses import dataclass, field
from django.db import models
from django.db import transaction
from django.conf import settings
from django.core.exceptions import ValidationError

from users.grade_levels import CANONICAL_GRADES, GRADE_CHOICES, normalize_grade, normalize_student_identifier


AUDIENCE_ALL_SCHOOL = 'all_school'
AUDIENCE_GRADE_ALL = 'grade_all'
AUDIENCE_CLASS = 'class'
AUDIENCE_SCOPE_CHOICES = (
    (AUDIENCE_ALL_SCHOOL, '全校'),
    (AUDIENCE_GRADE_ALL, '全年级'),
    (AUDIENCE_CLASS, '指定班级'),
)


@dataclass
class ProblemSyncResult:
    """Detailed sync result that remains compatible with legacy two-value unpacking."""

    created: list = field(default_factory=list)
    updated: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    failed: list = field(default_factory=list)

    def __iter__(self):
        yield self.created
        yield self.updated

    def as_dict(self):
        return {
            'created': self.created,
            'updated': self.updated,
            'skipped': self.skipped,
            'failed': self.failed,
        }


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
    grade_tag = models.CharField(
        '适用年级标签', max_length=10, choices=GRADE_CHOICES,
        blank=True, default='', db_index=True,
    )
    course = models.CharField('所属课程', max_length=10, choices=[('ai', '人工智能课'), ('info', '信息科技课')], default='ai')
    template_code = models.TextField('模板代码', blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_ai_problems',
        verbose_name='创建教师',
    )
    publishing_suspended = models.BooleanField('全局暂停发布', default=False)
    management_version = models.PositiveIntegerField('管理版本', default=1)
    archived_at = models.DateTimeField('归档时间', null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    def get_template_code(self):
        """优先使用数据库模板；兼容尚未同步入库的旧磁盘题目。"""
        if self.template_code:
            return self.template_code
        template_path = self.get_problem_dir() / 'template.py'
        if not template_path.exists():
            return ''
        try:
            return template_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            return template_path.read_text(encoding='gbk')

    def get_test_count(self):
        """返回测试点数量"""
        return len(self.get_test_cases())

    @classmethod
    def sync_from_disk(cls, actor=None):
        """
        从 problems/ai/ 和 problems/ 目录同步题目列表到数据库。
        problems/ai/  → course='ai'
        problems/根目录 → course='info'
        """
        problems_dir = settings.PROBLEMS_DIR
        result = ProblemSyncResult()

        if not os.path.exists(problems_dir):
            return result

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

                try:
                    def read_text(filename):
                        path = os.path.join(item_path, filename)
                        if not os.path.exists(path):
                            return ''
                        try:
                            with open(path, 'r', encoding='utf-8') as file:
                                return file.read()
                        except UnicodeDecodeError:
                            with open(path, 'r', encoding='gbk') as file:
                                return file.read()

                    description = read_text('description.txt')
                    template_code = read_text('template.py')
                    difficulty = ''
                    for line in read_text('metadata.txt').splitlines():
                        if line.startswith('difficulty:'):
                            difficulty = line.split(':', 1)[1].strip()
                            break

                    defaults = {
                        'title': item,
                        'description': description,
                        'course': course,
                        'difficulty': difficulty,
                        'template_code': template_code,
                    }
                    with transaction.atomic():
                        obj, created = cls.objects.get_or_create(
                            problem_id=item,
                            defaults={**defaults, 'created_by': actor},
                        )
                        if created:
                            result.created.append(item)
                            continue
                        if (
                            actor is not None
                            and not getattr(actor, 'is_superuser', False)
                            and obj.created_by_id != getattr(actor, 'pk', None)
                        ):
                            result.skipped.append({
                                'problem_id': item,
                                'reason': '题目属于其他教师或历史共享题，未覆盖内容',
                            })
                            continue
                        changed_fields = []
                        for model_field, value in defaults.items():
                            if getattr(obj, model_field) != value:
                                setattr(obj, model_field, value)
                                changed_fields.append(model_field)
                        if not changed_fields:
                            result.skipped.append({
                                'problem_id': item, 'reason': '内容无变化',
                            })
                            continue
                        obj.management_version += 1
                        obj.save(update_fields=[
                            *changed_fields, 'management_version', 'updated_at',
                        ])
                        result.updated.append(item)
                except Exception as exc:
                    result.failed.append({
                        'problem_id': item,
                        'reason': str(exc) or '读取或写入题目失败',
                    })

        return result


class ProblemAudience(models.Model):
    """A durable publication rule for one AI problem."""

    problem = models.ForeignKey(
        Problem,
        on_delete=models.CASCADE,
        related_name='audience_rules',
        verbose_name='题目',
    )
    scope_type = models.CharField('范围类型', max_length=16, choices=AUDIENCE_SCOPE_CHOICES)
    grade = models.CharField('年级', max_length=10, choices=GRADE_CHOICES, blank=True, default='')
    class_num = models.CharField('班级', max_length=20, blank=True, default='')
    is_active = models.BooleanField('是否生效', default=True)
    configured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='configured_ai_problem_audiences',
        verbose_name='最近配置人',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI题目发布范围'
        verbose_name_plural = 'AI题目发布范围'
        constraints = [
            models.UniqueConstraint(
                fields=['problem', 'scope_type', 'grade', 'class_num'],
                name='ai_problem_audience_unique_scope',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(scope_type=AUDIENCE_ALL_SCHOOL, grade='', class_num='')
                    | models.Q(scope_type=AUDIENCE_GRADE_ALL, grade__in=CANONICAL_GRADES, class_num='')
                    | (
                        models.Q(scope_type=AUDIENCE_CLASS, grade__in=CANONICAL_GRADES)
                        & ~models.Q(class_num='')
                    )
                ),
                name='ai_problem_audience_valid_shape',
            ),
        ]
        indexes = [
            models.Index(fields=['problem', 'is_active', 'scope_type'], name='ai_audience_problem_idx'),
            models.Index(fields=['grade', 'class_num', 'is_active'], name='ai_audience_identity_idx'),
        ]

    def clean(self):
        errors = {}
        if self.scope_type == AUDIENCE_ALL_SCHOOL:
            if self.grade or self.class_num:
                errors['scope_type'] = '全校规则不能指定年级或班级。'
        elif self.scope_type == AUDIENCE_GRADE_ALL:
            try:
                self.grade = normalize_grade(self.grade)
            except ValidationError as exc:
                errors['grade'] = exc.messages
            if self.class_num:
                errors['class_num'] = '全年级规则不能指定班级。'
        elif self.scope_type == AUDIENCE_CLASS:
            try:
                self.grade = normalize_grade(self.grade)
            except ValidationError as exc:
                errors['grade'] = exc.messages
            try:
                self.class_num = normalize_student_identifier(self.class_num, label='班级')
            except ValidationError as exc:
                errors['class_num'] = exc.messages
        else:
            errors['scope_type'] = '范围类型无效。'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        if self.scope_type == AUDIENCE_ALL_SCHOOL:
            label = '全校'
        elif self.scope_type == AUDIENCE_GRADE_ALL:
            label = f'{self.grade}全年级'
        else:
            label = f'{self.grade}{self.class_num}班'
        return f'{self.problem.problem_id} - {label}'


class ProblemManagementAudit(models.Model):
    EVENT_CHOICES = (
        ('content_edit', '编辑内容'),
        ('scope_update', '修改范围'),
        ('global_suspend', '全局暂停'),
        ('global_resume', '全局恢复'),
        ('archive', '归档'),
        ('restore', '恢复'),
        ('disk_sync', '磁盘同步'),
    )
    OUTCOME_CHOICES = (
        ('success', '成功'),
        ('denied', '拒绝'),
        ('conflict', '冲突'),
        ('failed', '失败'),
    )

    event_type = models.CharField(max_length=24, choices=EVENT_CHOICES)
    outcome = models.CharField(max_length=16, choices=OUTCOME_CHOICES)
    actor_user_id = models.BigIntegerField(null=True, blank=True)
    problem_id = models.CharField(max_length=50, blank=True)
    reason_code = models.CharField(max_length=80, blank=True)
    before_summary = models.JSONField(default=dict, blank=True)
    after_summary = models.JSONField(default=dict, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'AI题目管理审计'
        verbose_name_plural = 'AI题目管理审计'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.event_type}/{self.outcome} - {self.problem_id}'


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
        on_delete=models.PROTECT,
        related_name='submissions'
    )
    code = models.TextField('提交代码')
    score = models.FloatField('得分', default=0, null=True, blank=True)
    execution_task = models.OneToOneField(
        'execution.ExecutionTask',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submission',
    )
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField('错误信息', blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'AI课提交记录'
        verbose_name_plural = 'AI课提交记录'
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.user.username} - {self.problem.problem_id} ({self.score}分)"
