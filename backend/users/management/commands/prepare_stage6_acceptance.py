import secrets
import string

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from info_tech.models import Question, QuizSession, Unit
from users.models import CustomUser
from users.services import set_student_password


PREFIX = 'stage6_accept_'
QUIZ_PREFIX = '[阶段6验收]'


def password():
    alphabet = string.ascii_letters + string.digits
    return 'S6!' + ''.join(secrets.choice(alphabet) for _ in range(13))


class Command(BaseCommand):
    help = '创建或清理阶段 6 本地手工验收数据。'

    def add_arguments(self, parser):
        parser.add_argument('--cleanup', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['cleanup']:
            QuizSession.objects.filter(title__startswith=QUIZ_PREFIX).delete()
            Unit.objects.filter(name__startswith=PREFIX).delete()
            CustomUser.objects.filter(username__startswith=PREFIX).delete()
            self.stdout.write(self.style.SUCCESS('阶段 6 验收数据已清理。'))
            return

        if CustomUser.objects.filter(username__startswith=PREFIX).exists():
            self.stdout.write(
                self.style.WARNING(
                    '验收账号已存在；如果忘记密码，请先使用 --cleanup 再重建。'
                )
            )
            return

        credentials = []
        teachers = {}
        for grade, suffix in (('七年级', 'teacher7'), ('八年级', 'teacher8')):
            value = password()
            user = CustomUser.objects.create_user(
                username=PREFIX + suffix, password=value, role='teacher',
                managed_grade=grade, display_name=f'{grade}验收教师',
            )
            teachers[grade] = user
            credentials.append((user.username, value, f'{grade}教师'))
        value = password()
        no_scope = CustomUser.objects.create_user(
            username=PREFIX + 'teacher_none', password=value, role='teacher',
            display_name='无范围验收教师',
        )
        credentials.append((no_scope.username, value, '无管理年级教师'))

        student_specs = (
            ('student7a', '七年级', '2', '01', '七年级验收生A'),
            ('student7b', '七年级', '3', '01', '七年级验收生B'),
            ('student8a', '八年级', '2', '01', '八年级验收生A'),
        )
        for suffix, grade, class_num, number, display_name in student_specs:
            value = password()
            user = CustomUser(
                username=PREFIX + suffix, role='student', grade=grade,
                class_num=class_num, student_number=number,
                display_name=display_name,
            )
            set_student_password(
                user, value, validate=False, invalidate_tokens=False,
            )
            credentials.append((f'{grade}/{class_num}班/{number}号', value, display_name))

        for grade, suffix in (('七年级', 'g7'), ('八年级', 'g8')):
            unit = Unit.objects.create(
                grade=grade, name=PREFIX + suffix,
                display_name=f'{QUIZ_PREFIX}{grade}单元',
            )
            Question.objects.create(
                unit=unit, difficulty='easy', text=f'{grade}的验收题：1+1=?',
                answer='B', explanation='1 加 1 等于 2。',
                option_a='1', option_b='2', option_c='3', option_d='4',
            )
            quiz = QuizSession.objects.create(
                title=f'{QUIZ_PREFIX}{grade}2班小测',
                created_by=teachers[grade], num_questions=1,
                difficulty_ratio={'easy': 1}, time_limit=10,
                status=QuizSession.STATUS_OPEN, opened_at=timezone.now(),
                visible_grades=[grade], visible_classes=['2'],
            )
            quiz.units.add(unit)

        self.stdout.write(self.style.SUCCESS('阶段 6 验收数据已创建。'))
        self.stdout.write('密码仅在本次输出，请临时记录：')
        for login, value, label in credentials:
            self.stdout.write(f'  {label} | {login} | {value}')
        self.stdout.write('验收后清理：python manage.py prepare_stage6_acceptance --cleanup')
