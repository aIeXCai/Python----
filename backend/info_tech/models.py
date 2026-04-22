from django.db import models
from users.models import CustomUser


class Unit(models.Model):
    """单元目录"""
    name         = models.CharField('单元名称', max_length=100, unique=True)   # 如 "第四单元"
    display_name = models.CharField('显示名称', max_length=200)                 # 如 "第四单元：搭建校园网络系统"
    order        = models.IntegerField('排序', default=0)

    class Meta:
        ordering = ['order']
        verbose_name = '单元'
        verbose_name_plural = '单元列表'

    def __str__(self):
        return self.display_name


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
    """老师发起的一场小测（配置型，每次学生进入时随机抽题）"""
    title           = models.CharField('小测标题', max_length=200)
    created_by      = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    units           = models.ManyToManyField(Unit, related_name='quiz_sessions')
    num_questions   = models.IntegerField('题目数量')
    difficulty_ratio = models.JSONField('难度比例', default=dict)   # {"easy":7,"medium":2,"hard":1}
    time_limit      = models.IntegerField('时间限制(分钟)', null=True, blank=True)
    is_visible      = models.BooleanField('对学生可见', default=False)
    visible_grades  = models.JSONField('可见年级', default=list)    # [] 表示全部年级可见
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '小测'
        verbose_name_plural = '小测管理'

    def __str__(self):
        return self.title


class QuizSubmission(models.Model):
    """学生提交记录（每次作答都存）"""
    user          = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    session       = models.ForeignKey(QuizSession, on_delete=models.CASCADE)
    score         = models.FloatField('得分')                        # 百分比，如 85.0
    correct_count = models.IntegerField('正确题数')
    total_count   = models.IntegerField('总题数')
    answers_json  = models.TextField('学生答案')
    submitted_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = '小测提交'
        verbose_name_plural = '小测提交记录'

    def __str__(self):
        return f"{self.user.display_name} - {self.session.title}: {self.score}分"
