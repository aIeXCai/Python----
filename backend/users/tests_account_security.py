from datetime import timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from users.models import CustomUser, PasswordSecurityAudit
from users.services import set_student_password


def create_teacher(username='security-teacher'):
    return CustomUser.objects.create_user(
        username=username,
        password='teacher-login-password',
        role='teacher',
        display_name='安全测试教师',
        managed_grade='七年级',
    )


def create_student(username='security-student', password='student-old-password'):
    student = CustomUser.objects.create(
        username=username,
        role='student',
        grade='七年级',
        class_num='1',
        student_number='01',
        display_name='安全测试学生',
    )
    set_student_password(
        student, password, validate=False, invalidate_tokens=False
    )
    return student


def auth(token):
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


class PasswordRevealAPITests(APITestCase):
    def setUp(self):
        self.teacher = create_teacher()
        self.student = create_student()
        self.teacher_token = Token.objects.create(user=self.teacher)
        self.student_token = Token.objects.create(user=self.student)
        self.url = f'/api/auth/students/{self.student.pk}/password/reveal/'

    def test_teacher_reveals_one_password_with_no_store_and_audit(self):
        response = self.client.post(self.url, **auth(self.teacher_token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['password'], 'student-old-password')
        self.assertEqual(response.data['display_seconds'], 30)
        self.assertIn('no-store', response['Cache-Control'])
        audit = PasswordSecurityAudit.objects.get(event_type='reveal')
        self.assertEqual(audit.outcome, 'success')
        self.assertEqual(audit.actor_user_id, self.teacher.pk)
        self.assertNotIn('student-old-password', audit.reason_code)

    def test_student_and_anonymous_are_rejected_and_audited(self):
        student_response = self.client.post(self.url, **auth(self.student_token))
        anonymous_response = self.client.post(self.url)
        self.assertEqual(student_response.status_code, 403)
        self.assertEqual(anonymous_response.status_code, 401)
        self.assertEqual(
            PasswordSecurityAudit.objects.filter(
                event_type='reveal', outcome='denied'
            ).count(),
            2,
        )

    def test_teacher_cannot_reveal_teacher_or_missing_target(self):
        for target in (self.teacher.pk, 999999):
            with self.subTest(target=target):
                response = self.client.post(
                    f'/api/auth/students/{target}/password/reveal/',
                    **auth(self.teacher_token),
                )
                self.assertEqual(response.status_code, 404)

    def test_unavailable_or_corrupt_password_fails_closed(self):
        self.student.password_recovery_status = 'missing_legacy'
        self.student.encrypted_password = None
        self.student.password_encryption_key_id = None
        self.student.save()
        response = self.client.post(self.url, **auth(self.teacher_token))
        self.assertEqual(response.status_code, 409)
        self.assertNotIn('password', response.data)

    @override_settings(PASSWORD_REVEAL_LIMIT=2)
    def test_third_request_within_minute_is_rate_limited(self):
        first = self.client.post(self.url, **auth(self.teacher_token))
        second = self.client.post(self.url, **auth(self.teacher_token))
        third = self.client.post(self.url, **auth(self.teacher_token))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(third.status_code, 429)
        self.assertEqual(
            PasswordSecurityAudit.objects.filter(outcome='rate_limited').count(), 1
        )

    def test_detail_and_student_list_do_not_contain_password_material(self):
        detail = self.client.get(
            f'/api/auth/{self.student.pk}/', **auth(self.teacher_token)
        )
        listing = self.client.get('/api/ai/admin/students/', **auth(self.teacher_token))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(listing.status_code, 200)
        forbidden = {'password', 'encrypted_password', 'password_encryption_key_id'}
        self.assertFalse(forbidden & set(detail.data))
        self.assertFalse(forbidden & set(listing.data[0]))


class PasswordResetAPITests(APITestCase):
    def setUp(self):
        self.teacher = create_teacher('reset-teacher')
        self.student = create_student('reset-student')
        self.teacher_token = Token.objects.create(user=self.teacher)
        self.old_student_token = Token.objects.create(user=self.student)
        self.url = f'/api/auth/students/{self.student.pk}/password/reset/'

    def test_manual_reset_invalidates_old_password_and_token(self):
        response = self.client.post(
            self.url,
            {'mode': 'manual', 'password': 'NewClassroomPass42'},
            format='json',
            **auth(self.teacher_token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertFalse(Token.objects.filter(pk=self.old_student_token.pk).exists())
        old_token_response = self.client.get(
            '/api/auth/me/', **auth(self.old_student_token)
        )
        self.assertEqual(old_token_response.status_code, 401)
        old_login = self.client.post('/api/auth/login/', {
            'grade': '七年级', 'class_num': '1', 'student_number': '01',
            'password': 'student-old-password',
        }, format='json')
        new_login = self.client.post('/api/auth/login/', {
            'grade': '七年级', 'class_num': '1', 'student_number': '01',
            'password': 'NewClassroomPass42',
        }, format='json')
        self.assertEqual(old_login.status_code, 401)
        self.assertEqual(new_login.status_code, 200)
        self.assertTrue(
            PasswordSecurityAudit.objects.filter(
                event_type='manual_reset', outcome='success'
            ).exists()
        )

    def test_generated_reset_returns_once_and_new_password_logs_in(self):
        response = self.client.post(
            self.url, {'mode': 'generated'}, format='json',
            **auth(self.teacher_token),
        )
        self.assertEqual(response.status_code, 200)
        temporary = response.data['temporary_password']
        self.assertGreaterEqual(len(temporary), 12)
        login = self.client.post('/api/auth/login/', {
            'grade': '七年级', 'class_num': '1', 'student_number': '01',
            'password': temporary,
        }, format='json')
        self.assertEqual(login.status_code, 200)
        self.assertTrue(
            PasswordSecurityAudit.objects.filter(
                event_type='generated_reset', outcome='success'
            ).exists()
        )

    def test_short_password_rejected_without_changing_existing_password(self):
        response = self.client.post(
            self.url,
            {'mode': 'manual', 'password': 'short'},
            format='json',
            **auth(self.teacher_token),
        )
        self.assertEqual(response.status_code, 400)
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password('student-old-password'))
        self.assertTrue(Token.objects.filter(pk=self.old_student_token.pk).exists())

    def test_student_cannot_reset_password(self):
        response = self.client.post(
            self.url,
            {'mode': 'generated'},
            format='json',
            **auth(self.old_student_token),
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            PasswordSecurityAudit.objects.filter(
                event_type='generated_reset', outcome='denied'
            ).exists()
        )


class ExpiringTokenTests(APITestCase):
    def setUp(self):
        self.student = create_student('token-student')

    def test_expired_token_is_deleted_and_login_issues_new_token(self):
        token = Token.objects.create(user=self.student)
        Token.objects.filter(pk=token.pk).update(
            created=timezone.now() - timedelta(hours=13)
        )
        response = self.client.get('/api/auth/me/', **auth(token))
        self.assertEqual(response.status_code, 401)
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())
        login = self.client.post('/api/auth/login/', {
            'grade': '七年级', 'class_num': '1', 'student_number': '01',
            'password': 'student-old-password',
        }, format='json')
        self.assertEqual(login.status_code, 200)
        self.assertNotEqual(login.data['token'], token.key)

    def test_disabled_user_token_is_deleted(self):
        token = Token.objects.create(user=self.student)
        self.student.is_active = False
        self.student.save(update_fields=['is_active'])
        response = self.client.get('/api/auth/me/', **auth(token))
        self.assertEqual(response.status_code, 401)
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())
