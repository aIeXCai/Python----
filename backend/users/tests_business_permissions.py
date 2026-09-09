from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from info_tech.models import Unit, QuizSession, QuizSubmission
from users.models import CustomUser, PasswordSecurityAudit
from users.services import set_student_password


def token(user):
    return Token.objects.get_or_create(user=user)[0].key


def auth(user):
    return {'HTTP_AUTHORIZATION': f'Token {token(user)}'}


class Stage6BusinessPermissionTests(APITestCase):
    def setUp(self):
        self.grade7 = CustomUser.objects.create(
            username='stage6-7-01', role='student', grade='七年级',
            class_num='1', student_number='01', display_name='七年级学生',
        )
        set_student_password(
            self.grade7, 'student-stage6-password',
            validate=False, invalidate_tokens=False,
        )
        self.grade8 = CustomUser.objects.create_user(
            username='stage6-8-01', password='password', role='student',
            grade='八年级', class_num='1', student_number='01',
            display_name='八年级学生',
        )
        self.teacher7 = CustomUser.objects.create_user(
            username='stage6-teacher7', password='password', role='teacher',
            managed_grade='七年级',
        )
        self.no_scope = CustomUser.objects.create_user(
            username='stage6-no-scope', password='password', role='teacher',
            is_staff=True,
        )
        self.unit7 = Unit.objects.create(
            grade='七年级', name='stage6-u7', display_name='七年级单元',
        )
        self.unit8 = Unit.objects.create(
            grade='八年级', name='stage6-u8', display_name='八年级单元',
        )

    def test_alias_and_whitespace_student_login(self):
        response = self.client.post('/api/auth/login/', {
            'grade': ' 初一 ', 'class_num': ' 1 ',
            'student_number': ' 01 ', 'password': 'student-stage6-password',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user']['grade'], '七年级')
        self.assertEqual(response.data['user']['student_number'], '01')

    def test_unknown_grade_registration_is_rejected(self):
        response = self.client.post('/api/auth/register/', {
            'grade': '大一', 'class_num': '1', 'student_number': '01',
            'display_name': '测试', 'password': 'safe-stage6-password',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_teacher_student_data_is_grade_scoped(self):
        listing = self.client.get('/api/ai/admin/students/', **auth(self.teacher7))
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([row['id'] for row in listing.data], [self.grade7.id])
        detail = self.client.get(f'/api/auth/{self.grade8.id}/', **auth(self.teacher7))
        self.assertEqual(detail.status_code, 404)

        edit = self.client.put(
            f'/api/auth/{self.grade7.id}/', {'grade': '八年级'},
            format='json', **auth(self.teacher7),
        )
        self.assertEqual(edit.status_code, 403)
        self.grade7.refresh_from_db()
        self.assertEqual(self.grade7.grade, '七年级')

    def test_cross_grade_password_reveal_is_denied_before_decryption(self):
        response = self.client.post(
            f'/api/auth/students/{self.grade8.id}/password/reveal/',
            **auth(self.teacher7),
        )
        self.assertEqual(response.status_code, 403)
        audit = PasswordSecurityAudit.objects.latest('id')
        self.assertEqual(audit.outcome, 'denied')
        self.assertEqual(audit.reason_code, 'teacher_grade_forbidden')

    def test_is_staff_without_scope_does_not_bypass_business_scope(self):
        listing = self.client.get('/api/ai/admin/students/', **auth(self.no_scope))
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data, [])
        units = self.client.get('/api/admin/info/units/', **auth(self.no_scope))
        self.assertEqual(units.status_code, 200)
        self.assertEqual(units.data, [])

    def test_info_content_and_explicit_grade_are_scoped(self):
        units = self.client.get('/api/admin/info/units/', **auth(self.teacher7))
        self.assertEqual([row['id'] for row in units.data], [self.unit7.id])
        forbidden = self.client.get(
            '/api/admin/info/units/?grade=八年级', **auth(self.teacher7),
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_teacher_cannot_use_student_submission_history(self):
        response = self.client.get('/api/ai/submissions/history/', **auth(self.teacher7))
        self.assertEqual(response.status_code, 403)

    def test_edit_student_number_syncs_submission_identity_snapshots(self):
        """改学生学号/班级后，历史作答的身份快照同步为当前档案值"""
        session = QuizSession.objects.create(
            title='快照同步测试', created_by=self.teacher7,
            num_questions=3, difficulty_ratio={'easy': 3},
            status=QuizSession.STATUS_OPEN, visible_grades=['七年级'],
        )
        session.units.add(self.unit7)
        QuizSubmission.objects.create(
            user=self.grade7, session=session,
            status=QuizSubmission.STATUS_SUBMITTED,
            score=80, correct_count=2, total_count=3, answers_json='{}',
            grade='七年级', class_num_snapshot='1', student_number_snapshot='01',
        )

        # 只改学号：学号快照同步，班级快照保持
        resp = self.client.put(
            f'/api/auth/{self.grade7.id}/', {'student_number': '05'},
            format='json', **auth(self.teacher7),
        )
        self.assertEqual(resp.status_code, 200)
        sub = QuizSubmission.objects.get(user=self.grade7, session=session)
        self.assertEqual(sub.student_number_snapshot, '05')
        self.assertEqual(sub.class_num_snapshot, '1')
        self.assertEqual(sub.grade, '七年级')

        # 改班级：班级快照一并同步
        resp2 = self.client.put(
            f'/api/auth/{self.grade7.id}/', {'class_num': '2'},
            format='json', **auth(self.teacher7),
        )
        self.assertEqual(resp2.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.class_num_snapshot, '2')
        self.assertEqual(sub.student_number_snapshot, '05')
