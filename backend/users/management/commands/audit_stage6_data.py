from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from info_tech.models import QuizSession, QuizSubmission, Unit
from users.grade_levels import normalize_grade, normalize_student_identifier


class Command(BaseCommand):
    help = '只读审计阶段 6 年级、学生身份和教师管理范围数据。'

    def add_arguments(self, parser):
        parser.add_argument(
            '--strict', action='store_true',
            help='发现会阻止迁移的数据时以非零状态退出。',
        )

    def handle(self, *args, **options):
        User = get_user_model()
        blockers = []
        missing_scope = []
        identities = []

        for user in User.objects.all().iterator():
            if user.role == 'student':
                try:
                    identity = (
                        normalize_grade(user.grade),
                        normalize_student_identifier(user.class_num, label='班级'),
                        normalize_student_identifier(user.student_number, label='班内学号'),
                    )
                    identities.append(identity)
                except Exception:
                    blockers.append(f'user:{user.pk}:invalid_student_identity')
            elif user.role == 'teacher' and not user.is_superuser:
                try:
                    normalize_grade(user.managed_grade)
                except Exception:
                    missing_scope.append(user.pk)

        duplicates = [key for key, count in Counter(identities).items() if count > 1]
        blockers.extend('duplicate:' + '/'.join(key) for key in duplicates)

        for unit in Unit.objects.all().iterator():
            try:
                normalize_grade(unit.grade)
            except Exception:
                blockers.append(f'unit:{unit.pk}:invalid_grade')
        for session in QuizSession.objects.all().iterator():
            try:
                for grade in session.visible_grades or []:
                    normalize_grade(grade)
            except Exception:
                blockers.append(f'quiz_session:{session.pk}:invalid_visible_grade')
        for submission in QuizSubmission.objects.exclude(grade='').iterator():
            try:
                normalize_grade(submission.grade)
            except Exception:
                blockers.append(f'quiz_submission:{submission.pk}:invalid_grade')

        self.stdout.write(f'迁移阻断项: {len(blockers)}')
        self.stdout.write(f'未配置管理年级的普通教师: {len(missing_scope)}')
        if blockers:
            self.stdout.write('\n'.join(blockers))
        if missing_scope:
            self.stdout.write('教师 ID: ' + ', '.join(map(str, missing_scope)))
        if options['strict'] and blockers:
            raise CommandError('阶段 6 数据审计未通过。')
        self.stdout.write(self.style.SUCCESS('阶段 6 数据审计完成（未修改数据）。'))
