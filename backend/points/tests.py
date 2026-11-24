"""积分系统行为锁定测试。

口径（2026-11-24 定稿）：
- 打字：打多少次发多少次，不封顶。
- 小测：同场只认最高分，破纪录才补差，重复提交不重复发放。
"""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from ai_courses.models import AIQuizAttempt, AIQuizSession
from info_tech.models import QuizSession, QuizSubmission
from users.models import CustomUser

from .models import PointsAccount, PointsLedger, PointsReason
from .services import (
    PointsError,
    award_points,
    balance_for,
    class_rank,
    reset_points,
    settle_ai_quiz,
    settle_info_quiz,
    settle_typing,
    spend_points,
    teacher_adjust,
)


def make_teacher(grade='七年级', username='points_teacher', is_superuser=False):
    return CustomUser.objects.create_user(
        username=username, password='test123', role='teacher',
        display_name='老师', managed_grade=grade, is_superuser=is_superuser,
    )


def make_student(grade='七年级', class_num='1', number='01', username=None, name='学生'):
    username = username or f'student_{grade}_{class_num}_{number}'
    return CustomUser.objects.create_user(
        username=username, password='test123', role='student',
        grade=grade, class_num=class_num, student_number=number, display_name=name,
    )


def auth(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


def typing_attempt(student, activity_id=1, pk=1):
    """settle_typing 只读这几个字段，用轻量对象避免造整条题库。"""
    return SimpleNamespace(student_id=student.pk, pk=pk, activity_id=activity_id, language='zh')


class TypingPointsTests(APITestCase):
    def setUp(self):
        self.student = make_student()

    def test_every_attempt_awards_weighted_score(self):
        """每次打字都发，不封顶；单价按 0.6 折算（90→54，100→60，45.5→27.3）。"""
        for index, score in enumerate(['90.0', '100.0', '45.5'], start=1):
            settle_typing(typing_attempt(self.student, pk=index), Decimal(score))
        self.assertEqual(balance_for(self.student), Decimal('141.3'))

    def test_same_attempt_twice_awards_once(self):
        first = settle_typing(typing_attempt(self.student, pk=7), Decimal('88.0'))
        second = settle_typing(typing_attempt(self.student, pk=7), Decimal('88.0'))
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(balance_for(self.student), Decimal('52.8'))

    def test_zero_score_awards_nothing(self):
        settle_typing(typing_attempt(self.student), Decimal('0.0'))
        self.assertEqual(
            PointsLedger.objects.filter(user=self.student).count(), 0,
        )

    @override_settings(POINTS_START_AT='2999-01-01')
    def test_settled_before_start_at_is_ignored(self):
        settle_typing(typing_attempt(self.student), Decimal('99.0'))
        self.assertEqual(balance_for(self.student), Decimal('0.0'))


class TypingWeightTests(APITestCase):
    """打字单价折算：打字可无限重复，不能按原分和小测 1:1 计价。"""

    def setUp(self):
        self.student = make_student()

    def test_default_weight_is_point_six(self):
        from .services import typing_points_for

        self.assertEqual(typing_points_for(Decimal('100')), Decimal('60.0'))
        self.assertEqual(typing_points_for(Decimal('90')), Decimal('54.0'))

    @override_settings(POINTS_TYPING_WEIGHT='1')
    def test_weight_can_be_turned_off(self):
        from .services import typing_points_for

        self.assertEqual(typing_points_for(Decimal('100')), Decimal('100.0'))
        settle_typing(typing_attempt(self.student), Decimal('100'))
        self.assertEqual(balance_for(self.student), Decimal('100.0'))

    @override_settings(POINTS_TYPING_WEIGHT='abc')
    def test_invalid_weight_falls_back(self):
        from .services import typing_points_for

        self.assertEqual(typing_points_for(Decimal('100')), Decimal('60.0'))

    @override_settings(POINTS_TYPING_WEIGHT='1.5')
    def test_weight_out_of_range_falls_back(self):
        from .services import typing_points_for

        self.assertEqual(typing_points_for(Decimal('100')), Decimal('60.0'))

    def test_standard_rhythm_reaches_dual_path(self):
        """每节课 2 次打字 + 1 次小测的标准节奏，应当自然落在「双修」。"""
        from .services import typing_points_for
        from .titles import path_payload

        for typing_score, quiz_score in (('100', '100'), ('90', '90'), ('80', '75')):
            typing_total = typing_points_for(Decimal(typing_score)) * 2
            payload = path_payload(typing_total, Decimal(quiz_score))
            self.assertEqual(
                payload['label'], '双修', f'标准节奏 {typing_score} 打字 + {quiz_score} 小测',
            )

        # 少打一次：小测更强，判为智识；多刷打字：判为疾风。两条路都摸得到。
        one_typing = typing_points_for(Decimal('100'))
        self.assertEqual(path_payload(one_typing, Decimal('100'))['label'], '智识')
        self.assertEqual(path_payload(one_typing * 4, Decimal('100'))['label'], '疾风')


class QuizBestPointsTests(APITestCase):
    def setUp(self):
        self.teacher = make_teacher()
        self.student = make_student()
        self.session = QuizSession.objects.create(
            title='信息小测', created_by=self.teacher, num_questions=5,
        )

    def submission(self, score, attempt_no=1):
        return QuizSubmission.objects.create(
            user=self.student, session=self.session, attempt_no=attempt_no,
            status=QuizSubmission.STATUS_SUBMITTED, score=float(score),
            answers_json='{}', current_marker=None,
            submitted_at=timezone.now(),
        )

    def test_only_best_score_counts(self):
        settle_info_quiz(self.submission('80.0', 1))
        self.assertEqual(balance_for(self.student), Decimal('80.0'))

        settle_info_quiz(self.submission('90.0', 2))
        self.assertEqual(balance_for(self.student), Decimal('90.0'))

        settle_info_quiz(self.submission('85.0', 3))
        self.assertEqual(balance_for(self.student), Decimal('90.0'))

    def test_repeated_settle_is_idempotent(self):
        attempt = self.submission('76.0', 1)
        settle_info_quiz(attempt)
        settle_info_quiz(attempt)
        self.assertEqual(balance_for(self.student), Decimal('76.0'))
        self.assertEqual(
            PointsLedger.objects.filter(reason=PointsReason.QUIZ_BEST).count(), 1,
        )

    def test_lower_first_score_keeps_record(self):
        settle_info_quiz(self.submission('60.0', 1))
        settle_info_quiz(self.submission('99.5', 2))
        settle_info_quiz(self.submission('70.0', 3))
        self.assertEqual(balance_for(self.student), Decimal('99.5'))

    def test_ai_quiz_uses_same_best_rule(self):
        ai_session = AIQuizSession.objects.create(
            title='AI 小测', content_grade='七年级', created_by=self.teacher,
        )
        first = AIQuizAttempt.objects.create(
            user=self.student, session=ai_session, snapshot_json={},
            status=AIQuizAttempt.STATUS_SUBMITTED, attempt_no=1, current_marker=None,
            total_score=Decimal('64.0'), settled_at=timezone.now(),
        )
        settle_ai_quiz(first)
        self.assertEqual(balance_for(self.student), Decimal('64.0'))

        second = AIQuizAttempt.objects.create(
            user=self.student, session=ai_session, snapshot_json={},
            status=AIQuizAttempt.STATUS_SUBMITTED, attempt_no=2, current_marker=None,
            total_score=Decimal('92.0'), settled_at=timezone.now(),
        )
        settle_ai_quiz(second)
        self.assertEqual(balance_for(self.student), Decimal('92.0'))

    def test_info_and_ai_quiz_are_separate_pools(self):
        settle_info_quiz(self.submission('50.0', 1))
        ai_session = AIQuizSession.objects.create(
            title='AI 小测', content_grade='七年级', created_by=self.teacher,
        )
        ai_attempt = AIQuizAttempt.objects.create(
            user=self.student, session=ai_session, snapshot_json={},
            status=AIQuizAttempt.STATUS_SUBMITTED, attempt_no=1, current_marker=None,
            total_score=Decimal('50.0'), settled_at=timezone.now(),
        )
        settle_ai_quiz(ai_attempt)
        self.assertEqual(balance_for(self.student), Decimal('100.0'))


class SpendTests(APITestCase):
    def setUp(self):
        self.student = make_student()
        award_points(self.student, Decimal('150.0'), reason=PointsReason.TYPING,
                     source_type='typing_attempt', source_id='1')

    def test_spend_reduces_balance(self):
        spend_points(self.student, Decimal('100'),
                     source_type='hex_redraw', source_id='attempt:1:1')
        self.assertEqual(balance_for(self.student), Decimal('50.0'))

    def test_spend_rejects_when_insufficient(self):
        with self.assertRaises(PointsError) as ctx:
            spend_points(self.student, Decimal('200'))
        self.assertEqual(ctx.exception.code, 'insufficient_points')
        self.assertEqual(balance_for(self.student), Decimal('150.0'))

    def test_spend_is_idempotent_by_source(self):
        for _ in range(3):
            spend_points(self.student, Decimal('100'),
                         source_type='hex_redraw', source_id='attempt:1:1')
        self.assertEqual(balance_for(self.student), Decimal('50.0'))

    def test_teacher_adjust_cannot_go_negative(self):
        teacher = make_teacher()
        with self.assertRaises(PointsError):
            teacher_adjust(teacher, self.student, Decimal('-500'))
        self.assertEqual(balance_for(self.student), Decimal('150.0'))

    def test_teacher_reset_writes_reverse_ledger(self):
        teacher = make_teacher()
        count, total = reset_points(teacher, grade='七年级', class_num='1')
        self.assertEqual(count, 1)
        self.assertEqual(total, Decimal('150.0'))
        self.assertEqual(balance_for(self.student), Decimal('0.0'))
        reset_row = PointsLedger.objects.get(reason=PointsReason.TEACHER_RESET)
        self.assertEqual(reset_row.delta, Decimal('-150.0'))
        self.assertEqual(reset_row.created_by_id, teacher.pk)
        # 历史不被删除，仍可追溯
        self.assertEqual(PointsLedger.objects.filter(user=self.student).count(), 2)


class PointsApiTests(APITestCase):
    def setUp(self):
        self.teacher = make_teacher()
        self.a = make_student(number='01', username='a01', name='张三')
        self.b = make_student(number='02', username='a02', name='李四')
        self.other_grade = make_student(grade='八年级', username='b01', name='王五')
        award_points(self.a, Decimal('120.0'), reason=PointsReason.TYPING,
                     source_type='typing_attempt', source_id='1')
        award_points(self.b, Decimal('80.0'), reason=PointsReason.QUIZ_BEST,
                     source_type='info_quiz_attempt', source_id='1',
                     source_group='info_session:1')

    def test_me_returns_balance_and_rank(self):
        response = self.client.get('/api/points/me/', **auth(self.a))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['balance'], '120.0')
        self.assertEqual(body['rank'], 1)
        self.assertEqual(body['class_size'], 2)

    def test_leaderboard_orders_by_points_with_breakdown(self):
        response = self.client.get('/api/points/leaderboard/', **auth(self.b))
        entries = response.json()['entries']
        self.assertEqual([e['label'] for e in entries], ['张三', '李四'])
        self.assertEqual(entries[0]['typing_points'], '120.0')
        self.assertEqual(entries[1]['quiz_points'], '80.0')
        self.assertTrue(entries[1]['self'])

    def test_leaderboard_includes_zero_point_classmates(self):
        make_student(number='03', username='a03', name='赵六')
        response = self.client.get('/api/points/leaderboard/', **auth(self.a))
        labels = [e['label'] for e in response.json()['entries']]
        self.assertIn('赵六', labels)
        self.assertEqual(len(labels), 3)

    def test_teacher_sees_only_managed_grade(self):
        response = self.client.get('/api/points/admin/students/', **auth(self.teacher))
        self.assertEqual(response.status_code, 200)
        names = {row['name'] for row in response.json()['students']}
        self.assertEqual(names, {'张三', '李四'})

    def test_teacher_adjusts_single_student(self):
        response = self.client.post(
            f'/api/points/admin/students/{self.b.pk}/adjust/',
            {'delta': '20', 'note': '课堂表现'}, format='json', **auth(self.teacher),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['balance'], '100.0')
        self.assertEqual(balance_for(self.b), Decimal('100.0'))

    def test_teacher_cannot_touch_other_grade(self):
        response = self.client.post(
            f'/api/points/admin/students/{self.other_grade.pk}/adjust/',
            {'delta': '10'}, format='json', **auth(self.teacher),
        )
        self.assertEqual(response.status_code, 404)

    def test_reset_requires_grade(self):
        response = self.client.post(
            '/api/points/admin/reset/', {}, format='json', **auth(self.teacher),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'grade_required')

    def test_reset_by_class(self):
        response = self.client.post(
            '/api/points/admin/reset/',
            {'grade': '七年级', 'class_num': '1', 'note': '新学期重置'},
            format='json', **auth(self.teacher),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['cleared_count'], 2)
        self.assertEqual(body['cleared_total'], '200.0')
        self.assertEqual(balance_for(self.a), Decimal('0.0'))
        self.assertEqual(balance_for(self.b), Decimal('0.0'))

    def test_student_cannot_use_teacher_endpoints(self):
        response = self.client.get('/api/points/admin/students/', **auth(self.a))
        self.assertEqual(response.status_code, 403)


class InfoQuizHookTests(APITestCase):
    """端到端验证：走真实交卷接口，积分钩子必须自动记账。"""

    def setUp(self):
        from info_tech.models import Question, Unit

        self.teacher = make_teacher()
        self.student = make_student()
        unit = Unit.objects.create(
            grade='七年级', name='points_unit', display_name='积分单元', order=1,
        )
        for index in range(6):
            Question.objects.create(
                unit=unit, difficulty='easy', category='基础',
                text=f'题目{index}', answer='A', explanation='解析',
                option_a=f'正确{index}', option_b='错B', option_c='错C', option_d='错D',
            )
        self.session = QuizSession.objects.create(
            title='积分验证小测', created_by=self.teacher, num_questions=4,
            difficulty_ratio={'easy': 4}, time_limit=20,
            status=QuizSession.STATUS_OPEN, opened_at=timezone.now(),
            visible_grades=['七年级'],
        )
        self.session.units.add(unit)

    def test_submitting_quiz_awards_points_automatically(self):
        started = self.client.post(
            f'/api/info/quizzes/{self.session.pk}/attempt/', {}, format='json',
            **auth(self.student),
        )
        attempt = QuizSubmission.objects.get(pk=started.json()['attempt_id'])
        items = attempt.snapshot_json['questions']
        answers = {item['item_id']: item['correct_option'] for item in items}

        submitted = self.client.post(
            f'/api/info/quizzes/{self.session.pk}/attempt/submit/',
            {'attempt_id': attempt.pk, 'revision': attempt.answer_revision,
             'answers': answers},
            format='json', **auth(self.student),
        )
        self.assertEqual(submitted.status_code, 200, submitted.data)

        attempt.refresh_from_db()
        self.assertEqual(balance_for(self.student), Decimal(str(attempt.score)))
        self.assertTrue(
            PointsLedger.objects.filter(
                user=self.student, reason=PointsReason.QUIZ_BEST,
            ).exists()
        )


class RankTests(APITestCase):
    def test_ties_share_rank(self):
        first = make_student(number='01', username='r01', name='甲')
        second = make_student(number='02', username='r02', name='乙')
        award_points(first, Decimal('50.0'), reason=PointsReason.TYPING,
                     source_type='typing_attempt', source_id='1')
        award_points(second, Decimal('50.0'), reason=PointsReason.TYPING,
                     source_type='typing_attempt', source_id='1')
        self.assertEqual(class_rank(first)[0], 1)
        self.assertEqual(class_rank(second)[0], 1)
        self.assertFalse(PointsAccount.objects.filter(balance__lt=0).exists())


class TitleTests(APITestCase):
    """称号（白省天骄十阶）：阈值、晋升、掉级留荣誉。"""

    def setUp(self):
        self.student = make_student()

    def test_thresholds_are_inclusive(self):
        from .titles import tier_for
        cases = {
            '0': '蒙学童生', '49.9': '蒙学童生', '50': '格物学徒',
            '149.9': '格物学徒', '150': '格物修士', '300': '南山行者',
            '500': '南山执剑', '800': '创新术士', '1800': '白省天骄',
            '3500': '校史留名',
        }
        for value, name in cases.items():
            self.assertEqual(tier_for(value)['name'], name, value)

    def test_promote_then_demote_keeps_honor(self):
        award_points(
            self.student, Decimal('500'), reason=PointsReason.TYPING,
            source_type='typing_attempt', source_id='1',
        )
        payload = self.client.get('/api/points/me/', **auth(self.student)).json()
        self.assertEqual(payload['title']['name'], '南山执剑')
        self.assertEqual(payload['title']['next']['name'], '创新术士')
        self.assertEqual(payload['title']['next']['remaining'], '300.0')
        self.assertIsNone(payload['title']['honor'])

        spend_points(self.student, Decimal('400'), source_type='hex', source_id='1')
        payload = self.client.get('/api/points/me/', **auth(self.student)).json()
        self.assertEqual(payload['title']['name'], '格物学徒')
        self.assertEqual(payload['title']['honor']['name'], '南山执剑')

    def test_teacher_reset_keeps_peak_honor(self):
        award_points(
            self.student, Decimal('1000'), reason=PointsReason.TYPING,
            source_type='typing_attempt', source_id='1',
        )
        teacher = make_teacher(grade='七年级')
        reset_points(teacher, grade='七年级')
        self.assertEqual(balance_for(self.student), Decimal('0.0'))

        payload = self.client.get('/api/points/me/', **auth(self.student)).json()
        self.assertEqual(payload['title']['name'], '蒙学童生')
        self.assertEqual(payload['title']['honor']['name'], '创新术士')

    def test_leaderboard_rows_carry_title(self):
        award_points(
            self.student, Decimal('500'), reason=PointsReason.TYPING,
            source_type='typing_attempt', source_id='1',
        )
        entries = self.client.get(
            '/api/points/leaderboard/', **auth(self.student),
        ).json()['entries']
        self.assertEqual(entries[0]['title']['name'], '南山执剑')
        self.assertEqual(entries[0]['title']['level'], 5)
        self.assertEqual(entries[0]['title']['icon'], 'sword')

    def test_me_returns_full_ladder(self):
        award_points(
            self.student, Decimal('150'), reason=PointsReason.TYPING,
            source_type='typing_attempt', source_id='1',
        )
        payload = self.client.get('/api/points/me/', **auth(self.student)).json()
        ladder = payload['ladder']
        self.assertEqual(len(ladder), 10)
        self.assertEqual([row['level'] for row in ladder], list(range(1, 11)))

        current = [row for row in ladder if row['current']]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]['name'], '格物修士')
        # 刚踩到门槛，到下一阶的进度为 0
        self.assertEqual(current[0]['progress'], 0.0)
        self.assertEqual(current[0]['remaining'], '150.0')
        # 其余阶段没有进度字段
        self.assertIsNone(ladder[3]['progress'])

    def test_ladder_keeps_peak_after_demotion(self):
        award_points(
            self.student, Decimal('1000'), reason=PointsReason.TYPING,
            source_type='typing_attempt', source_id='1',
        )
        spend_points(self.student, Decimal('900'), source_type='hex', source_id='1')

        ladder = self.client.get('/api/points/me/', **auth(self.student)).json()['ladder']
        top = next(row for row in ladder if row['level'] == 6)
        self.assertEqual(top['name'], '创新术士')
        self.assertFalse(top['reached'])
        self.assertTrue(top['was_reached'])


class PathTests(APITestCase):
    """道号（疾风 / 智识 / 双修）：只看累计发放的结构，不看余额。"""

    def setUp(self):
        self.student = make_student()

    def test_path_rules(self):
        from .titles import path_payload

        self.assertIsNone(path_payload(Decimal('0'), Decimal('0')))
        self.assertIsNone(path_payload(Decimal('40'), Decimal('30')))
        self.assertEqual(path_payload(Decimal('300'), Decimal('0'))['label'], '疾风')
        self.assertEqual(path_payload(Decimal('0'), Decimal('200'))['label'], '智识')
        self.assertEqual(path_payload(Decimal('100'), Decimal('70'))['label'], '双修')
        self.assertEqual(path_payload(Decimal('100'), Decimal('69.9'))['label'], '疾风')

    def test_path_gives_upgrade_hint(self):
        from .titles import path_payload

        payload = path_payload(Decimal('457'), Decimal('272'))
        self.assertEqual(payload['label'], '疾风')
        # 457 × 0.7 = 319.9，小测差 47.9 分转双修
        self.assertEqual(payload['upgrade']['need'], '47.9')
        self.assertIn('小测再得 47.9 分即可双修', payload['upgrade']['hint'])

        newcomer = path_payload(Decimal('300'), Decimal('0'))
        self.assertIn('迈过 50 分门槛', newcomer['upgrade']['hint'])

        balanced = path_payload(Decimal('300'), Decimal('320'))
        self.assertIsNone(balanced['upgrade'])

    def test_me_exposes_path_and_split(self):
        award_points(
            self.student, Decimal('300'), reason=PointsReason.TYPING,
            source_type='typing_attempt', source_id='1',
        )
        award_points(
            self.student, Decimal('320'), reason=PointsReason.QUIZ_BEST,
            source_type='info_quiz', source_id='1',
        )
        payload = self.client.get('/api/points/me/', **auth(self.student)).json()

        self.assertEqual(payload['typing_total'], '300.0')
        self.assertEqual(payload['quiz_total'], '320.0')
        self.assertEqual(payload['title']['path']['label'], '双修')
        self.assertEqual(len(payload['paths']), 3)
        self.assertEqual(
            [item['label'] for item in payload['paths']], ['疾风', '智识', '双修'],
        )

    def test_path_ignores_spending(self):
        """消费掉积分不该改变道号：道号看的是练过什么，不是还剩多少。"""
        award_points(
            self.student, Decimal('300'), reason=PointsReason.TYPING,
            source_type='typing_attempt', source_id='1',
        )
        award_points(
            self.student, Decimal('320'), reason=PointsReason.QUIZ_BEST,
            source_type='info_quiz', source_id='1',
        )
        spend_points(self.student, Decimal('500'), source_type='hex', source_id='1')

        payload = self.client.get('/api/points/me/', **auth(self.student)).json()
        self.assertEqual(payload['balance'], '120.0')
        self.assertEqual(payload['title']['path']['label'], '双修')

    def test_leaderboard_rows_carry_path(self):
        award_points(
            self.student, Decimal('300'), reason=PointsReason.TYPING,
            source_type='typing_attempt', source_id='1',
        )
        entries = self.client.get(
            '/api/points/leaderboard/', **auth(self.student),
        ).json()['entries']
        self.assertEqual(entries[0]['title']['path']['label'], '疾风')
