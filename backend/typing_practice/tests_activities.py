from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APITestCase

from .models import TypingActivity, TypingArticleRevision, TypingAttempt, TypingSpeedRule
from .peaks import PEAKS


class TypingActivityTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.teacher = User.objects.create_user(username='teacher', role='teacher', managed_grade='七年级')
        cls.teacher8 = User.objects.create_user(username='teacher8', role='teacher', managed_grade='八年级')
        cls.alice = User.objects.create_user(username='alice', grade='七年级', class_num='1', student_number='1')
        cls.bob = User.objects.create_user(username='bob', grade='七年级', class_num='1', student_number='2')
        cls.other_class = User.objects.create_user(username='other-class', grade='七年级', class_num='2', student_number='1')
        cls.other_grade = User.objects.create_user(username='other-grade', grade='八年级', class_num='1', student_number='1')
        call_command('seed_typing_trial', stdout=StringIO())

    def publish(self, zh=None, en=None, **overrides):
        self.client.force_authenticate(self.teacher)
        payload = {
            'title': '第 1 节训练', 'grade': 7, 'class_num': '1',
            'zh': zh or {'mode': 'random', 'difficulty': '基础'},
            'en': en or {'mode': 'free', 'difficulty': '基础'},
            **overrides,
        }
        return self.client.post('/api/typing/teacher/activities/', payload, format='json')

    def start(self, student, activity, language='zh', **extra):
        self.client.force_authenticate(student)
        return self.client.post('/api/typing/attempts/', {'activity_id': activity, 'language': language, **extra}, format='json')

    def test_same_language_peak_and_independent_five_minute_windows(self):
        result = self.publish()
        self.assertEqual(result.status_code, 201, result.data)
        activity = result.data
        zh = activity['languages']['zh']['peak']['id']
        en = activity['languages']['en']['peak']['id']
        self.assertNotEqual(zh, en)
        self.assertEqual(len(PEAKS), 14)
        clock = datetime(2026, 11, 20, 13, tzinfo=timezone.utc)
        with patch('typing_practice.activities.timezone.now', return_value=clock):
            alice = self.start(self.alice, activity['id'])
        with patch('typing_practice.activities.timezone.now', return_value=clock + timedelta(seconds=22)):
            bob = self.start(self.bob, activity['id'])
            repeat = self.start(self.alice, activity['id'])
        for reply in (alice, bob):
            self.assertEqual(reply.status_code, 201, reply.data)
            self.assertEqual(reply.data['activity']['languages']['zh']['peak']['id'], zh)
            self.assertIsNone(reply.data['article']['pinyin'])
            self.assertEqual(reply.data['deadline_at'] - reply.data['started_at'], timedelta(minutes=5))
        self.assertNotEqual(alice.data['started_at'], bob.data['started_at'])
        self.assertEqual(repeat.status_code, 200)
        self.assertEqual(repeat.data['id'], alice.data['id'])
        self.assertEqual(repeat.data['article'], alice.data['article'])
        self.assertEqual(repeat.data['deadline_at'], alice.data['deadline_at'])
        stored_activity = TypingActivity.objects.get(pk=activity['id'])
        self.assertEqual(len(stored_activity.languages['zh']['article_ids']), 2)
        self.assertEqual(TypingAttempt.objects.count(), 2)
        TypingSpeedRule.objects.filter(grade=7, language='zh').update(target_per_minute=100)
        stored_activity.refresh_from_db()
        self.assertEqual(stored_activity.languages['zh']['rule']['target_per_minute'], '26.00')

    def test_fixed_random_free_and_article_validation(self):
        zh_article = TypingArticleRevision.objects.get(grade=7, language='zh', version=2, article__source_id='7-zh-01')
        other_grade = TypingArticleRevision.objects.filter(grade=8, language='zh', difficulty='基础').first()
        fixed = {'mode': 'fixed', 'difficulty': '基础', 'article_id': zh_article.id, 'pinyin': True}
        rejected = self.publish(zh={**fixed, 'article_id': other_grade.id})
        self.assertEqual(rejected.status_code, 400)
        unsupported = self.publish(zh={'mode': 'random', 'difficulty': '挑战', 'pinyin': True})
        self.assertEqual(unsupported.status_code, 400)
        result = self.publish(zh=fixed)
        self.assertEqual(result.status_code, 201, result.data)
        activity_id = result.data['id']

        started = self.start(self.alice, activity_id)
        self.assertEqual(started.status_code, 201)
        self.assertEqual(started.data['article']['id'], zh_article.id)
        self.assertTrue(started.data['article']['pinyin'])
        self.assertEqual(TypingAttempt.objects.get(pk=started.data['id']).article_sequence, [zh_article.id])

        self.client.force_authenticate(self.bob)
        activities = self.client.get('/api/typing/activities/').data['activities']
        choices = activities[0]['languages']['en']['articles']
        self.assertEqual(len(choices), 2)
        self.assertEqual(self.start(self.bob, activity_id, 'en', article_id=zh_article.id).status_code, 400)
        english = self.start(self.bob, activity_id, 'en', article_id=choices[1]['id'])
        self.assertEqual(english.status_code, 201)
        self.assertEqual(english.data['article']['id'], choices[1]['id'])
        self.assertIsNone(english.data['article']['pinyin'])
        attempt = TypingAttempt.objects.get(pk=english.data['id'])
        self.assertEqual(attempt.article_sequence, [choices[1]['id'], choices[0]['id']])

    def test_activity_visibility_access_and_stop_joining(self):
        activity = self.publish().data['id']
        a = self.start(self.alice, activity).data
        self.assertEqual(self.start(self.alice, activity, 'en', article_id=1).status_code, 409)
        for outsider in (self.other_class, self.other_grade):
            self.assertEqual(self.start(outsider, activity).status_code, 404)
            self.assertEqual(self.client.get('/api/typing/activities/').data['activities'], [])
            self.assertEqual(self.client.get(f"/api/typing/attempts/{a['id']}/").status_code, 404)
        self.client.force_authenticate(self.teacher8)
        self.assertEqual(self.client.post(f'/api/typing/teacher/activities/{activity}/close/').status_code, 404)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post(f'/api/typing/teacher/activities/{activity}/close/').status_code, 200)
        self.assertEqual(self.start(self.bob, activity).status_code, 409)
        self.assertEqual(self.start(self.alice, activity).status_code, 200)
        listing = self.client.get('/api/typing/activities/').data
        self.assertEqual(listing, {'activities': [], 'active_attempt_id': a['id']})
        resumed = self.client.get(f"/api/typing/attempts/{a['id']}/")
        self.assertEqual(resumed.data['deadline_at'], a['deadline_at'])
        self.assertFalse(resumed.data['expired'])
        with patch('typing_practice.activities.timezone.now', return_value=a['deadline_at']):
            self.assertTrue(self.client.get(f"/api/typing/attempts/{a['id']}/").data['expired'])
            self.assertEqual(self.start(self.alice, activity).status_code, 409)

    def test_teacher_article_options_respect_grade_and_reviewed_pinyin(self):
        self.client.force_authenticate(self.teacher)
        base = '/api/typing/teacher/articles/?class_num=1&language=zh&pinyin=true&grade='
        self.assertEqual(self.client.get(base + '8').status_code, 403)
        response = self.client.get(base + '7')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['difficulty'] for item in response.data], ['基础'])
        articles = response.data[0]['articles']
        self.assertEqual(len(articles), 2)
        self.assertTrue(all(item['version'] == 2 for item in articles))
