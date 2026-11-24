"""本地演示数据：40 个学生账号 + 积分流水 + 几场可作答的演示小测。

用途只有一个：本地验收积分系统（积分卡片、班级风云榜、教师端积分管理、海克斯刷新）。

所有数据都打了 `demo` 前缀 / `[演示]` 标题，方便一键清理：

    python manage.py seed_demo_points            # 创建（已存在则跳过）
    python manage.py seed_demo_points --reset     # 删掉旧演示数据后重建
    python manage.py seed_demo_points --cleanup   # 只删除
"""

import random

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from info_tech.models import QuizSession, Unit
from points.models import PointsReason
from points.services import award_points, quantize, typing_points_for
from users.models import CustomUser
from users.services import set_student_password

USERNAME_PREFIX = 'demo8'
PASSWORD = 'Points2026'
QUIZ_PREFIX = '[演示]'
NOTE_TYPING = '演示数据 · 打字练习'
NOTE_QUIZ = '演示数据 · 小测最高分'

GRADE = '八年级'
# (班级号, 学生姓名列表) —— 1 班、2 班各 20 人，正好 40 个账号
CLASSES = [
    ('1', [
        '陈嘉禾', '李思远', '王雨桐', '张子航', '刘欣怡',
        '黄俊杰', '吴梓涵', '周诗涵', '徐浩然', '孙佳宁',
        '马晨曦', '朱可欣', '胡博文', '郭子萱', '何明轩',
        '高梦琪', '林书瑶', '罗宇轩', '郑梓琳', '谢子昂',
    ]),
    ('2', [
        '苏念安', '唐嘉怡', '邓皓宇', '冯雨欣', '韩一诺',
        '曹思睿', '彭若曦', '董子墨', '袁梦洁', '蒋泽宇',
        '于欣妍', '潘思远', '蔡佳琪', '余天佑', '杜雨薇',
        '叶星辰', '程亦菲', '卢子谦', '沈嘉宁', '范可盈',
    ]),
]

# 三场演示小测：(标题前缀, 题量, 难度比例, 时间限制)
DEMO_QUIZZES = [
    ('互联网基础 · 10 题', 10, {'easy': 7, 'medium': 3}, 20),
    ('互联网应用 · 8 题', 8, {'easy': 5, 'medium': 3}, 15),
    ('快速自测 · 5 题', 5, {'easy': 4, 'medium': 1}, 8),
]


class Command(BaseCommand):
    help = '创建/清理本地积分系统演示数据（40 学生 + 积分 + 演示小测）。'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='删除旧演示数据后重建')
        parser.add_argument('--cleanup', action='store_true', help='只删除演示数据')

    def handle(self, *args, **options):
        if options['cleanup'] or options['reset']:
            self._cleanup()

        if options['cleanup']:
            return

        students = self._seed_students()
        created_points = self._seed_points(students)
        quizzes = self._seed_quizzes()

        self.stdout.write(self.style.SUCCESS(
            f'完成：学生 {len(students)} 个，积分流水 {created_points} 条，演示小测 {len(quizzes)} 场。'
        ))
        self.stdout.write(f'登录口令：{PASSWORD}（用户名形如 {USERNAME_PREFIX}101：班号 + 两位序号）')

    # ── 清理 ──────────────────────────────────────────────────────────────
    def _cleanup(self):
        from points.models import PointsLedger

        users = CustomUser.objects.filter(username__startswith=USERNAME_PREFIX)
        PointsLedger.objects.filter(user__in=users).delete()
        users.delete()
        QuizSession.objects.filter(title__startswith=QUIZ_PREFIX).delete()
        self.stdout.write(self.style.WARNING('旧演示数据已清理。'))

    # ── 学生 ──────────────────────────────────────────────────────────────
    def _seed_students(self):
        students = []
        for class_num, names in CLASSES:
            # 真实班级里可能已有学生（如 1 班已有学号 1），演示账号顺延占用空学号
            taken = set(
                CustomUser.objects
                .filter(grade=GRADE, class_num=class_num)
                .exclude(username__startswith=USERNAME_PREFIX)
                .values_list('student_number', flat=True)
            )
            next_number = 1
            for index, name in enumerate(names, start=1):
                username = f'{USERNAME_PREFIX}{class_num}{index:02d}'
                student = CustomUser.objects.filter(username=username).first()
                if student is None:
                    while str(next_number) in taken:
                        next_number += 1
                    number = str(next_number)
                    taken.add(number)
                    next_number += 1
                    student = CustomUser(
                        username=username,
                        role='student',
                        grade=GRADE,
                        class_num=class_num,
                        student_number=number,
                        display_name=name,
                        first_name=name,
                    )
                    student.save()
                    try:
                        set_student_password(student, PASSWORD, validate=False)
                    except Exception as exc:  # 密码服务异常也不该挡住演示数据
                        student.set_password(PASSWORD)
                        student.save(update_fields=['password'])
                        self.stderr.write(f'{username} 走标准设密流程失败：{exc}')
                students.append(student)
        return students

    # ── 积分 ──────────────────────────────────────────────────────────────
    def _seed_points(self, students):
        """按固定随机种子造积分，保证每次重建后榜单形态一致。

        打字金额走 `typing_points_for()`，与真实结算同一口径（含折算系数），
        否则演示榜单上的打字/小测结构会和线上规则对不上。
        """
        rng = random.Random(20261124)
        created = 0
        for student in students:
            level = rng.uniform(0.6, 0.97)  # 每个学生的"基础水平"
            typing_runs = rng.randint(2, 5)
            for i in range(1, typing_runs + 1):
                score = _clamp(level * 100 + rng.gauss(0, 6), 35, 100)
                ledger = award_points(
                    student, typing_points_for(score),
                    reason=PointsReason.TYPING,
                    source_type='demo_typing',
                    source_id=f'{student.username}:t{i}',
                    source_group=f'demo:typing:{i}',
                    note=NOTE_TYPING,
                )
                created += 1 if ledger else 0

            quiz_runs = rng.randint(1, 3)
            for i in range(1, quiz_runs + 1):
                score = _clamp(level * 100 + rng.gauss(-5, 9), 30, 100)
                ledger = award_points(
                    student, quantize(score),
                    reason=PointsReason.QUIZ_BEST,
                    source_type='demo_quiz',
                    source_id=f'{student.username}:q{i}',
                    source_group=f'demo:quiz:{i}',
                    note=NOTE_QUIZ,
                )
                created += 1 if ledger else 0
        return created

    # ── 演示小测 ──────────────────────────────────────────────────────────
    def _seed_quizzes(self):
        teacher = (
            CustomUser.objects.filter(is_superuser=True).order_by('id').first()
            or CustomUser.objects.filter(role='teacher').order_by('id').first()
        )
        if teacher is None:
            self.stderr.write('没有可用的教师账号，跳过演示小测。')
            return []

        unit = Unit.objects.filter(questions__isnull=False).first()
        if unit is None:
            self.stderr.write('题库为空，跳过演示小测。')
            return []

        now = timezone.now()
        quizzes = []
        for title, count, ratio, minutes in DEMO_QUIZZES:
            full_title = f'{QUIZ_PREFIX} {title}'
            session, _ = QuizSession.objects.update_or_create(
                title=full_title,
                defaults={
                    'created_by': teacher,
                    'num_questions': count,
                    'difficulty_ratio': ratio,
                    'time_limit': minutes,
                    'status': QuizSession.STATUS_OPEN,
                    'opened_at': now,
                    'visible_grades': [GRADE],
                    'visible_classes': [],
                    'archived_at': None,
                },
            )
            session.units.set([unit])
            quizzes.append(session)
        return quizzes


def _clamp(value, low, high):
    return max(low, min(high, value))
