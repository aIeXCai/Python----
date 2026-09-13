import os
import glob
from dataclasses import dataclass, field
from django.db import models
from django.db import transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

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


class AIUnit(models.Model):
    """Two-level curriculum catalog for AI choice and programming questions."""

    grade = models.CharField('年级', max_length=20, choices=GRADE_CHOICES, db_index=True)
    parent = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='sections', verbose_name='所属大单元',
    )
    name = models.CharField('单元名称', max_length=100)
    display_name = models.CharField('显示名称', max_length=200)
    order = models.IntegerField('排序', default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_ai_units', verbose_name='创建教师',
    )
    archived_at = models.DateTimeField('归档时间', null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI课程单元'
        verbose_name_plural = 'AI课程单元'
        ordering = ['grade', 'order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['grade', 'parent', 'name'],
                name='ai_unit_unique_sibling_name',
            ),
        ]
        indexes = [
            models.Index(fields=['grade', 'archived_at', 'order'], name='ai_unit_grade_active_idx'),
            models.Index(fields=['parent', 'archived_at', 'order'], name='ai_unit_parent_active_idx'),
        ]

    @property
    def is_section(self):
        return self.parent_id is not None

    @property
    def is_effectively_archived(self):
        return bool(self.archived_at or (self.parent_id and self.parent.archived_at))

    def clean(self):
        errors = {}
        try:
            self.grade = normalize_grade(self.grade)
        except ValidationError as exc:
            errors['grade'] = exc.messages
        self.name = (self.name or '').strip()
        self.display_name = (self.display_name or '').strip()
        if not self.name:
            errors['name'] = '单元名称不能为空。'
        if not self.display_name:
            errors['display_name'] = '显示名称不能为空。'
        if self.parent_id:
            if self.pk and self.parent_id == self.pk:
                errors['parent'] = '单元不能把自己设为父级。'
            elif self.parent.parent_id is not None:
                errors['parent'] = 'AI课程单元最多支持大单元和小节两级。'
            elif self.parent.grade != self.grade:
                errors['parent'] = '小节必须和所属大单元处于同一年级。'
        if errors:
            raise ValidationError(errors)

    def archive(self):
        if self.archived_at is None:
            self.archived_at = timezone.now()
            self.save(update_fields=['archived_at', 'updated_at'])

    def __str__(self):
        return f'{self.grade} · {self.display_name}'


class AIChoiceQuestion(models.Model):
    """Single-choice question in the AI course question bank."""

    DIFFICULTY_CHOICES = [
        ('easy', '容易'),
        ('medium', '中等'),
        ('hard', '困难'),
    ]
    ANSWER_CHOICES = [(letter, letter) for letter in ('A', 'B', 'C', 'D')]

    unit = models.ForeignKey(
        AIUnit, on_delete=models.PROTECT, related_name='choice_questions',
        verbose_name='所属小节',
    )
    difficulty = models.CharField(
        '难度', max_length=10, choices=DIFFICULTY_CHOICES, default='easy', db_index=True,
    )
    category = models.CharField('知识点分类', max_length=100, blank=True, default='')
    text = models.TextField('题目正文')
    option_a = models.CharField('选项A', max_length=500)
    option_b = models.CharField('选项B', max_length=500)
    option_c = models.CharField('选项C', max_length=500)
    option_d = models.CharField('选项D', max_length=500)
    answer = models.CharField('正确答案', max_length=1, choices=ANSWER_CHOICES)
    explanation = models.TextField('答案解析', blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_ai_choice_questions', verbose_name='创建教师',
    )
    management_version = models.PositiveIntegerField('管理版本', default=1)
    archived_at = models.DateTimeField('归档时间', null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI选择题'
        verbose_name_plural = 'AI选择题库'
        ordering = ['id']
        indexes = [
            models.Index(
                fields=['unit', 'difficulty', 'archived_at'],
                name='ai_choice_pool_idx',
            ),
        ]

    def clean(self):
        errors = {}
        if self.unit_id:
            if self.unit.parent_id is None:
                errors['unit'] = '选择题必须归入一个小节，不能直接归入大单元。'
            elif self.unit.is_effectively_archived:
                errors['unit'] = '不能把选择题归入已归档单元。'
        for field in ('text', 'option_a', 'option_b', 'option_c', 'option_d'):
            value = (getattr(self, field, '') or '').strip()
            setattr(self, field, value)
            if not value:
                errors[field] = '该字段不能为空。'
        self.category = (self.category or '').strip()
        self.explanation = (self.explanation or '').strip()
        self.answer = (self.answer or '').strip().upper()
        if self.answer not in dict(self.ANSWER_CHOICES):
            errors['answer'] = '正确答案必须为 A、B、C 或 D。'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.unit} - {self.text[:30]}'


class AIQuizSession(models.Model):
    """Teacher-managed quiz configuration and immutable first-publish blueprint."""

    STATUS_DRAFT = 'draft'
    STATUS_OPEN = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = (
        (STATUS_DRAFT, '草稿'),
        (STATUS_OPEN, '进行中'),
        (STATUS_CLOSED, '已关闭'),
    )

    title = models.CharField('小测名称', max_length=200)
    content_grade = models.CharField('内容年级', max_length=20, choices=GRADE_CHOICES, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='created_ai_quizzes', verbose_name='创建教师',
    )
    choice_units = models.ManyToManyField(
        AIUnit, related_name='quiz_sessions', blank=True, verbose_name='选择题小节',
    )
    choice_question_count = models.PositiveSmallIntegerField('选择题抽题数', default=0)
    choice_difficulty_ratio = models.JSONField('选择题难度题数', default=dict, blank=True)
    choice_points = models.DecimalField(
        '选择题分值', max_digits=5, decimal_places=1, default=0,
    )
    time_limit = models.PositiveSmallIntegerField('限时（分钟）', null=True, blank=True)
    status = models.CharField(
        '状态', max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True,
    )
    management_version = models.PositiveIntegerField('管理版本', default=1)
    blueprint_version = models.PositiveSmallIntegerField('蓝图版本', default=0)
    blueprint_json = models.JSONField('发布蓝图', null=True, blank=True)
    blueprint_hash = models.CharField('蓝图哈希', max_length=64, blank=True, default='')
    opened_at = models.DateTimeField('开放时间', null=True, blank=True)
    closed_at = models.DateTimeField('关闭时间', null=True, blank=True)
    archived_at = models.DateTimeField('归档时间', null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI小测'
        verbose_name_plural = 'AI小测'
        ordering = ['-created_at', '-id']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(choice_points__gte=0) & models.Q(choice_points__lte=100),
                name='ai_quiz_choice_points_range',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status='draft')
                    | (
                        models.Q(blueprint_version__gt=0)
                        & models.Q(blueprint_json__isnull=False)
                        & ~models.Q(blueprint_hash='')
                    )
                ),
                name='ai_quiz_published_has_blueprint',
            ),
        ]
        indexes = [
            models.Index(
                fields=['content_grade', 'status', 'archived_at'],
                name='ai_quiz_grade_status_idx',
            ),
            models.Index(
                fields=['created_by', 'archived_at', 'updated_at'],
                name='ai_quiz_creator_idx',
            ),
        ]

    def clean(self):
        errors = {}
        try:
            self.content_grade = normalize_grade(self.content_grade)
        except ValidationError as exc:
            errors['content_grade'] = exc.messages
        self.title = (self.title or '').strip()
        if not self.title:
            errors['title'] = '小测名称不能为空。'
        if self.time_limit is not None and not 1 <= self.time_limit <= 600:
            errors['time_limit'] = '限时必须在 1–600 分钟之间。'
        if self.status != self.STATUS_DRAFT:
            if not self.blueprint_version or not self.blueprint_json or not self.blueprint_hash:
                errors['blueprint_json'] = '已发布小测必须具有完整蓝图。'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


class AIQuizProgrammingItem(models.Model):
    session = models.ForeignKey(
        AIQuizSession, on_delete=models.CASCADE,
        related_name='programming_items', verbose_name='所属小测',
    )
    problem = models.ForeignKey(
        'Problem', on_delete=models.PROTECT,
        related_name='quiz_programming_items', verbose_name='编程题',
    )
    position = models.PositiveSmallIntegerField('顺序')
    points = models.DecimalField('分值', max_digits=5, decimal_places=1)

    class Meta:
        verbose_name = 'AI小测编程题项'
        verbose_name_plural = 'AI小测编程题项'
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'problem'], name='ai_quiz_unique_programming_problem',
            ),
            models.UniqueConstraint(
                fields=['session', 'position'], name='ai_quiz_unique_programming_position',
            ),
            models.CheckConstraint(
                condition=models.Q(points__gt=0) & models.Q(points__lte=100),
                name='ai_quiz_programming_points_range',
            ),
        ]

    def __str__(self):
        return f'{self.session_id}:{self.position} - {self.problem_id}'


class AIQuizAudience(models.Model):
    session = models.ForeignKey(
        AIQuizSession, on_delete=models.CASCADE,
        related_name='audience_rules', verbose_name='所属小测',
    )
    scope_type = models.CharField('范围类型', max_length=16, choices=AUDIENCE_SCOPE_CHOICES)
    grade = models.CharField('年级', max_length=10, choices=GRADE_CHOICES, blank=True, default='')
    class_num = models.CharField('班级', max_length=20, blank=True, default='')
    is_active = models.BooleanField('是否生效', default=True)
    configured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='configured_ai_quiz_audiences', verbose_name='最近配置人',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI小测发布范围'
        verbose_name_plural = 'AI小测发布范围'
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'scope_type', 'grade', 'class_num'],
                name='ai_quiz_audience_unique_scope',
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
                name='ai_quiz_audience_valid_shape',
            ),
        ]
        indexes = [
            models.Index(
                fields=['session', 'is_active', 'scope_type'],
                name='ai_quiz_audience_session_idx',
            ),
            models.Index(
                fields=['grade', 'class_num', 'is_active'],
                name='ai_quiz_audience_identity_idx',
            ),
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


class AIQuizAttempt(models.Model):
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_SETTLING = 'settling'
    STATUS_SUBMITTED = 'submitted'
    STATUS_TIMED_OUT = 'timed_out'
    STATUS_CLOSED = 'closed'
    STATUS_RESET = 'reset'
    STATUS_SUPERSEDED = 'superseded'
    STATUS_CHOICES = (
        (STATUS_IN_PROGRESS, '作答中'),
        (STATUS_SETTLING, '结算中'),
        (STATUS_SUBMITTED, '已提交'),
        (STATUS_TIMED_OUT, '已超时'),
        (STATUS_CLOSED, '关闭结算'),
        (STATUS_RESET, '已重置'),
        (STATUS_SUPERSEDED, '历史作答'),
    )
    FINAL_REASON_CHOICES = (
        ('', '未结算'),
        ('submitted', '主动交卷'),
        ('timed_out', '超时'),
        ('closed', '教师关闭'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='ai_quiz_attempts', verbose_name='学生',
    )
    session = models.ForeignKey(
        AIQuizSession, on_delete=models.PROTECT,
        related_name='attempts', verbose_name='所属小测',
    )
    status = models.CharField(
        '作答状态', max_length=20, choices=STATUS_CHOICES,
        default=STATUS_IN_PROGRESS, db_index=True,
    )
    final_reason = models.CharField(
        '结算原因', max_length=16, choices=FINAL_REASON_CHOICES, blank=True, default='',
    )
    attempt_no = models.PositiveIntegerField('作答序号', default=1)
    current_marker = models.BooleanField(
        '当前有效标记', null=True, blank=True, default=True,
    )
    snapshot_version = models.PositiveSmallIntegerField('快照版本', default=1)
    snapshot_json = models.JSONField('个人试卷快照')
    answers_json = models.JSONField('选择题答案', default=dict, blank=True)
    answer_revision = models.PositiveIntegerField('答案版本', default=0)
    choice_score = models.DecimalField(
        '选择题得分', max_digits=5, decimal_places=1, null=True, blank=True,
    )
    programming_score = models.DecimalField(
        '编程题得分', max_digits=5, decimal_places=1, null=True, blank=True,
    )
    total_score = models.DecimalField(
        '总分', max_digits=5, decimal_places=1, null=True, blank=True,
    )
    correct_count = models.PositiveSmallIntegerField('选择题答对数', null=True, blank=True)
    choice_count = models.PositiveSmallIntegerField('选择题总数', null=True, blank=True)
    grade = models.CharField('年级快照', max_length=20, blank=True, default='')
    class_num = models.CharField('班级快照', max_length=20, blank=True, default='')
    student_number = models.CharField('学号快照', max_length=50, blank=True, default='')
    started_at = models.DateTimeField('开始时间', default=timezone.now)
    deadline_at = models.DateTimeField('截止时间', null=True, blank=True)
    settlement_requested_at = models.DateTimeField('请求结算时间', null=True, blank=True)
    settled_at = models.DateTimeField('结算完成时间', null=True, blank=True)
    grading_issue_count = models.PositiveSmallIntegerField('评测异常题数', default=0)
    result_revision = models.PositiveIntegerField('结果版本', default=0)
    reset_at = models.DateTimeField('重置时间', null=True, blank=True)
    reset_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reset_ai_quiz_attempts', verbose_name='重置教师',
    )
    reset_reason = models.CharField('重置原因', max_length=300, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI小测作答'
        verbose_name_plural = 'AI小测作答'
        ordering = ['-started_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'session', 'attempt_no'],
                name='ai_quiz_unique_attempt_no',
            ),
            models.UniqueConstraint(
                fields=['user', 'session', 'current_marker'],
                name='ai_quiz_unique_current_attempt',
            ),
            models.CheckConstraint(
                condition=models.Q(current_marker=True) | models.Q(current_marker__isnull=True),
                name='ai_quiz_current_true_or_null',
            ),
            models.CheckConstraint(
                condition=models.Q(choice_score__isnull=True)
                | (models.Q(choice_score__gte=0) & models.Q(choice_score__lte=100)),
                name='ai_quiz_choice_score_range',
            ),
            models.CheckConstraint(
                condition=models.Q(programming_score__isnull=True)
                | (models.Q(programming_score__gte=0) & models.Q(programming_score__lte=100)),
                name='ai_quiz_programming_score_range',
            ),
            models.CheckConstraint(
                condition=models.Q(total_score__isnull=True)
                | (models.Q(total_score__gte=0) & models.Q(total_score__lte=100)),
                name='ai_quiz_total_score_range',
            ),
        ]
        indexes = [
            models.Index(fields=['session', 'status'], name='ai_attempt_session_status_idx'),
            models.Index(fields=['status', 'deadline_at'], name='ai_attempt_status_deadline_idx'),
            models.Index(
                fields=['user', 'session', 'current_marker'],
                name='ai_attempt_user_current_idx',
            ),
            models.Index(fields=['grade', 'session'], name='ai_attempt_grade_session_idx'),
        ]

    def __str__(self):
        return f'{self.user_id}/{self.session_id} #{self.attempt_no}'


class AIQuizManagementAudit(models.Model):
    OUTCOME_CHOICES = (
        ('success', '成功'), ('denied', '拒绝'),
        ('conflict', '冲突'), ('failed', '失败'),
    )

    event_type = models.CharField(max_length=32)
    outcome = models.CharField(max_length=16, choices=OUTCOME_CHOICES)
    actor_user_id = models.BigIntegerField(null=True, blank=True)
    object_type = models.CharField(max_length=32)
    object_id = models.CharField(max_length=64, blank=True)
    reason_code = models.CharField(max_length=80, blank=True)
    before_summary = models.JSONField(default=dict, blank=True)
    after_summary = models.JSONField(default=dict, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'AI小测管理审计'
        verbose_name_plural = 'AI小测管理审计'
        ordering = ['-created_at']


class Problem(models.Model):
    """
    AI课题目模型。
    注意：测试点文件（input*.txt / output*.txt）仍然存储在文件系统，
    不在数据库中，以兼容现有的 problems/ 目录结构。
    """
    problem_id = models.CharField('题目ID', max_length=50, unique=True)  # 如 "problem1"
    unit = models.ForeignKey(
        AIUnit, on_delete=models.PROTECT, null=True, blank=True,
        related_name='programming_problems', verbose_name='所属小节',
    )
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

    def clean(self):
        super().clean()
        if not self.unit_id:
            return
        errors = {}
        if self.course != 'ai':
            errors['unit'] = '只有 AI 课程编程题可以关联 AI 单元。'
        elif self.unit.parent_id is None:
            errors['unit'] = '编程题必须归入一个小节，不能直接归入大单元。'
        elif self.unit.is_effectively_archived:
            errors['unit'] = '不能把编程题归入已归档单元。'
        if self.grade_tag and self.grade_tag != self.unit.grade:
            errors['grade_tag'] = '适用年级必须与所属小节年级一致。'
        if errors:
            raise ValidationError(errors)

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
    quiz_attempt = models.ForeignKey(
        AIQuizAttempt,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='code_submissions',
        verbose_name='所属小测作答',
    )
    quiz_item_id = models.CharField('小测题目标识', max_length=36, blank=True, db_index=True)
    regrade_of = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='regrades',
        verbose_name='重评来源',
    )
    counts_for_quiz = models.BooleanField('计入小测成绩', default=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField('错误信息', blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'AI课提交记录'
        verbose_name_plural = 'AI课提交记录'
        ordering = ['-submitted_at']
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(quiz_attempt__isnull=True, quiz_item_id='')
                    | (models.Q(quiz_attempt__isnull=False) & ~models.Q(quiz_item_id=''))
                ),
                name='ai_submission_quiz_context_pair',
            ),
        ]
        indexes = [
            models.Index(
                fields=['quiz_attempt', 'quiz_item_id'],
                name='ai_submission_quiz_item_idx',
            ),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.problem.problem_id} ({self.score}分)"
