from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """扩展 Django 默认 User 模型"""

    ROLE_CHOICES = [
        ('student', '学生'),
        ('teacher', '老师'),
    ]

    GRADE_CHOICES = [
        ('初一', '初一'),
        ('初二', '初二'),
        ('初三', '初三'),
        ('高一', '高一'),
        ('高二', '高二'),
        ('高三', '高三'),
    ]

    role = models.CharField(
        '角色', max_length=20, choices=ROLE_CHOICES, default='student'
    )
    grade = models.CharField(
        '年级', max_length=10, choices=GRADE_CHOICES, blank=True, null=True
    )
    class_num = models.CharField(
        '班级', max_length=20, blank=True, null=True
    )
    student_number = models.CharField(
        '班级内学号', max_length=20, blank=True, null=True
    )
    # 学生真实姓名（登录时不验证，仅用于显示）
    display_name = models.CharField('显示姓名', max_length=100, blank=True, null=True)
    # 明文密码（供老师查看）
    plain_password = models.CharField('明文密码', max_length=128, blank=True, null=True)
    # 老师的管理范围（信息科技课用）
    managed_grade = models.CharField(
        '管理年级', max_length=10, choices=GRADE_CHOICES, blank=True, null=True
    )

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'

    def __str__(self):
        if self.grade and self.class_num:
            return f"{self.username} ({self.grade}{self.class_num})"
        return self.username
