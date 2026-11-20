from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APITestCase

from .models import TypingActivity, TypingPointSubmission


class TypingHomeTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.teacher = User.objects.create_user(username='teacher', role='teacher', managed_grade='七年级')
        cls.student = User.objects.create_user(username='student', grade='七年级', class_num='1', student_number='1')
        cls.peer = User.objects.create_user(username='peer', grade='七年级', class_num='1', student_number='2')
        call_command('seed_typing_trial', stdout=StringIO())

    def current(self, student):
        self.client.force_authenticate(student)
        response = self.client.get('/api/typing/activities/')
        return response.data['activities'][0], response.data

    def save_settings(self):
        self.client.force_authenticate(self.teacher)
        response = self.client.post('/api/typing/teacher/activities/', {
            'grade': 7, 'class_num': '1',
            'zh': {'mode': 'free', 'difficulty': '基础', 'pinyin': True},
            'en': {'mode': 'random', 'difficulty': '挑战'},
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def start(self, student, activity_id, language='zh'):
        self.client.force_authenticate(student)
        response = self.client.post('/api/typing/attempts/', {
            'activity_id': activity_id, 'language': language,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_beijing_midnight_rotates_peaks_once_but_preserves_class_settings_and_attempts(self):
        before = datetime(2026, 11, 20, 15, 59, 55, tzinfo=timezone.utc)
        with patch('django.utils.timezone.now', return_value=before):
            yesterday, state = self.current(self.student)
            self.assertEqual(state['rotation_in_ms'], 5000)
            attempt = self.start(self.student, yesterday['id'])
            saved = self.save_settings()
            for language in ('zh', 'en'):
                self.assertEqual(saved['languages'][language]['peak'], yesterday['languages'][language]['peak'])

        after = before + timedelta(seconds=5)
        with patch('django.utils.timezone.now', return_value=after):
            today, state = self.current(self.peer)
            self.assertEqual(state['rotation_in_ms'], 86_400_000)
            self.assertNotEqual(today['id'], saved['id'])
            self.assertEqual(self.current(self.student)[0], today)
            before_peaks = {setup['peak']['id'] for setup in saved['languages'].values()}
            after_peaks = {setup['peak']['id'] for setup in today['languages'].values()}
            self.assertEqual(len(after_peaks), 2)
            self.assertTrue(before_peaks.isdisjoint(after_peaks))
            self.assertEqual(today['languages']['zh']['mode'], 'free')
            self.assertTrue(today['languages']['zh']['pinyin'])
            self.assertEqual(today['languages']['en']['difficulty'], '挑战')
            self.assertEqual(state['active_attempt_id'], None)
            resumed = self.client.get(f"/api/typing/attempts/{attempt['id']}/").data
            self.assertEqual(resumed['deadline_at'], attempt['deadline_at'])
            self.assertEqual(resumed['activity']['languages'], attempt['activity']['languages'])
            self.assertEqual(TypingActivity.objects.filter(closed_at__isnull=True).count(), 1)

    def test_bests_use_only_own_settled_scores_by_language(self):
        activity, _ = self.current(self.student)
        url = '/api/typing/me/bests/?student_id=' + str(self.peer.pk)
        self.assertEqual(self.client.get(url).data, {'zh': None, 'en': None})
        now = datetime(2026, 11, 20, 4, tzinfo=timezone.utc)
        from .models import TypingAttempt

        template = self.start(self.student, activity['id'])
        original = TypingAttempt.objects.get(pk=template['id'])

        def add_score(student, language, score, *, trial=True, settled_at=now):
            score_activity = original.activity
            if not trial:
                score_activity = TypingActivity.objects.create(
                    grade=7, class_num='1', title='正式训练', is_trial=False, languages=original.activity.languages,
                )
            attempt = TypingAttempt.objects.create(
                activity=score_activity, student=student, language=language,
                article_sequence=original.article_sequence, first_article=original.first_article,
                started_at=now, deadline_at=now + timedelta(minutes=5),
            )
            TypingPointSubmission.objects.create(attempt=attempt, score=score, settled_at=settled_at)

        add_score(self.student, 'zh', '87.4')
        add_score(self.student, 'zh', '6.2')
        add_score(self.student, 'en', '0.0')
        add_score(self.student, 'zh', '100.0', trial=False)
        add_score(self.peer, 'zh', '99.9')
        response = self.client.get(url)
        self.assertEqual(response.data, {'zh': '87.4', 'en': '0.0'})
        self.assertIn('no-store', response['Cache-Control'])
        start = datetime(2026, 11, 19, 16, tzinfo=timezone.utc)
        add_score(self.student, 'zh', '98.1', settled_at=start - timedelta(seconds=1))
        add_score(self.student, 'en', '62.0', settled_at=start)
        with patch('django.utils.timezone.now', return_value=now):
            today = self.client.get(url + '&period=today').data
            self.assertEqual(today, {'zh': '87.4', 'en': '62.0', 'rotation_in_ms': 43_200_000})
        with patch('django.utils.timezone.now', return_value=start + timedelta(days=1)):
            tomorrow = self.client.get(url + '&period=today').data
            self.assertEqual(tomorrow, {'zh': None, 'en': None, 'rotation_in_ms': 86_400_000})
        self.assertEqual(self.client.get(url).data['zh'], '98.1')
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get(url).status_code, 403)
