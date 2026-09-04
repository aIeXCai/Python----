from django.db import models
from django.utils import timezone
from users.models import CustomUser
from users.grade_levels import GRADE_CHOICES


class Unit(models.Model):
    """单元目录 — Grade-Unit-Section 三级结构
    grade  = 年级（大单元和小节都必须属于某年级）
    parent = 所属大单元（小节用），大单元 parent=null
    """
    grade       = models.CharField('年级', max_length=20, choices=GRADE_CHOICES, default='七年级')
    parent      = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sections')
    name        = models.CharField('单元名称', max_length=100)               # 如 "1-1" 或 "unit_1_1"
    display_name = models.CharField('显示名称', max_length=200)               # 如 "1.1 变量的概念"
    order       = models.IntegerField('排序', default=0)

    class Meta:
        ordering = ['grade', 'order']
        verbose_name = '单元'
        verbose_name_plural = '单元列表'

    def __str__(self):
        return f"{self.grade} · {self.display_name}"


class Question(models.Model):
    """题库题目（单选）"""
    DIFFICULTY_CHOICES = [
        ('easy',   '容易'),
        ('medium', '中等'),
        ('hard',   '困难'),
    ]

    unit        = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='questions')
    difficulty  = models.CharField('难度', max_length=10, choices=DIFFICULTY_CHOICES, default='easy')
    category    = models.CharField('知识点分类', max_length=100, blank=True)   # 如 "网络层级结构"
    text        = models.TextField('题目正文')
    answer      = models.CharField('正确答案', max_length=1)                     # 'A'/'B'/'C'/'D'
    explanation = models.TextField('答案解析', blank=True)
    option_a    = models.CharField('选项A', max_length=500)
    option_b    = models.CharField('选项B', max_length=500)
    option_c    = models.CharField('选项C', max_length=500)
    option_d    = models.CharField('选项D', max_length=500)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '题目'
        verbose_name_plural = '题库'
        ordering = ['id']

    def __str__(self):
        return f"{self.unit.name} - {self.text[:30]}..."


class QuizSession(models.Model):
    """老师发起的一场小测。学生开始时固化独立试卷快照。"""
    STATUS_DRAFT = 'draft'
    STATUS_OPEN = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, '未发布'),
        (STATUS_OPEN, '进行中'),
        (STATUS_CLOSED, '已关闭'),
    ]

    title           = models.CharField('小测标题', max_length=200)
    created_by      = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    units           = models.ManyToManyField(Unit, related_name='quiz_sessions')
    num_questions   = models.IntegerField('题目数量')
    difficulty_ratio = models.JSONField('难度比例', default=dict)   # {"easy":7,"medium":2,"hard":1}
    time_limit      = models.IntegerField('时间限制(分钟)', null=True, blank=True)
    status           = models.CharField(
        '状态', max_length=10, choices=STATUS_CHOICES,
        default=STATUS_DRAFT, db_index=True,
    )
    opened_at        = models.DateTimeField('开放时间', null=True, blank=True)
    closed_at        = models.DateTimeField('关闭时间', null=True, blank=True)
    visible_grades  = models.JSONField('可见年级', default=list)    # [] 表示全部年级可见
    visible_classes = models.JSONField('可见班级', default=list)    # [] 表示所选年级全部班级可见
    archived_at     = models.DateTimeField('删除归档时间', null=True, blank=True, db_index=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '小测'
        verbose_name_plural = '小测管理'

    def __str__(self):
        return self.title

    @property
    def is_visible(self):
        """Temporary Python-level compatibility; status is the database source of truth."""
        return self.status == self.STATUS_OPEN

    @is_visible.setter
    def is_visible(self, value):
        self.status = self.STATUS_OPEN if value else self.STATUS_DRAFT


class QuizSubmission(models.Model):
    """学生小测作答。名称为兼容存量表，领域含义为 attempt。"""
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_SUBMITTED = 'submitted'
    STATUS_TIMED_OUT = 'timed_out'
    STATUS_RESET = 'reset'
    STATUS_SUPERSEDED = 'superseded'
    STATUS_CHOICES = [
        (STATUS_IN_PROGRESS, '作答中'),
        (STATUS_SUBMITTED, '已提交'),
        (STATUS_TIMED_OUT, '已超时'),
        (STATUS_RESET, '已重置'),
        (STATUS_SUPERSEDED, '历史记录'),
    ]

    user          = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    session       = models.ForeignKey(QuizSession, on_delete=models.CASCADE)
    grade         = models.CharField('学生年级', max_length=20, blank=True, default='')  # 提交时快照
    class_num_snapshot = models.CharField('班级快照', max_length=20, blank=True, default='')
    student_number_snapshot = models.CharField('学号快照', max_length=50, blank=True, default='')
    status        = models.CharField(
        '作答状态', max_length=20, choices=STATUS_CHOICES,
        default=STATUS_SUBMITTED, db_index=True,
    )
    attempt_no    = models.PositiveIntegerField('作答序号', default=1)
    current_marker = models.BooleanField('当前有效标记', null=True, blank=True, default=True)
    snapshot_version = models.PositiveSmallIntegerField('快照版本', default=0)
    snapshot_json = models.JSONField('试卷快照', null=True, blank=True)
    score         = models.FloatField('得分', null=True, blank=True)  # 百分比，如 85.0
    correct_count = models.IntegerField('正确题数', null=True, blank=True)
    total_count   = models.IntegerField('总题数', null=True, blank=True)
    answers_json  = models.TextField('学生答案')
    answer_revision = models.PositiveIntegerField('答案版本', default=0)
    started_at    = models.DateTimeField('开始时间', null=True, blank=True)
    deadline_at   = models.DateTimeField('截止时间', null=True, blank=True)
    submitted_at  = models.DateTimeField('提交时间', null=True, blank=True, default=timezone.now)
    updated_at    = models.DateTimeField('更新时间', auto_now=True)
    reset_at      = models.DateTimeField('重置时间', null=True, blank=True)
    reset_by      = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reset_quiz_attempts', verbose_name='重置教师',
    )
    reset_reason  = models.CharField('重置原因', max_length=300, blank=True, default='')

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = '小测提交'
        verbose_name_plural = '小测提交记录'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'session', 'attempt_no'],
                name='info_quiz_unique_attempt_no',
            ),
            models.UniqueConstraint(
                fields=['user', 'session', 'current_marker'],
                name='info_quiz_unique_current_attempt',
            ),
            models.CheckConstraint(
                condition=(models.Q(current_marker=True) | models.Q(current_marker__isnull=True)),
                name='info_quiz_current_true_or_null',
            ),
        ]
        indexes = [
            models.Index(fields=['session', 'status'], name='info_quiz_session_status'),
            models.Index(fields=['status', 'deadline_at'], name='info_quiz_status_deadline'),
            models.Index(fields=['grade', 'session'], name='info_quiz_grade_session'),
        ]

    def __str__(self):
        score = '-' if self.score is None else self.score
        return f"{self.user.display_name} - {self.session.title}: {score}分"

    @property
    def answers(self):
        import json
        try:
            value = json.loads(self.answers_json or '{}')
        except (TypeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}
