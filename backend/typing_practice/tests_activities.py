from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APITestCase

from .models import TypingActivity, TypingArticleRevision, TypingAttempt, TypingClassSettings, TypingPointSubmission, TypingSpeedRule
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
        clock = activity['published_at']
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
        self.assertEqual(attempt.article_sequence, [choices[1]['id']])

    def test_activity_visibility_access_and_stop_joining(self):
        activity = self.publish().data['id']
        a = self.start(self.alice, activity).data
        self.assertEqual(self.start(self.alice, activity, 'en', article_id=1).status_code, 409)
        for outsider in (self.other_class, self.other_grade):
            self.assertEqual(self.start(outsider, activity).status_code, 404)
            separate, = self.client.get('/api/typing/activities/').data['activities']
            self.assertNotEqual(separate['id'], activity)
            self.assertTrue(separate['is_default'])
            self.assertEqual(self.client.get(f"/api/typing/attempts/{a['id']}/").status_code, 404)
        self.client.force_authenticate(self.teacher8)
        self.assertEqual(self.client.post(f'/api/typing/teacher/activities/{activity}/close/').status_code, 404)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post(f'/api/typing/teacher/activities/{activity}/close/').status_code, 200)
        self.assertEqual(self.start(self.bob, activity).status_code, 409)
        self.assertEqual(self.start(self.alice, activity).status_code, 200)
        listing = self.client.get('/api/typing/activities/').data
        self.assertEqual(listing['active_attempt_id'], a['id'])
        fallback, = listing['activities']
        self.assertTrue(fallback['is_default'])
        self.assertNotEqual(fallback['id'], activity)
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

    def test_first_visit_auto_opens_class_for_both_languages(self):
        self.assertFalse(TypingActivity.objects.exists())
        scope = '/api/typing/activities/'
        self.client.force_authenticate(self.alice)
        initial, = self.client.get(scope).data['activities']
        self.assertTrue(initial['is_default'])
        self.assertEqual(initial['grade'], 7)
        self.assertEqual(initial['class_num'], '1')
        self.assertEqual(initial['languages']['zh']['mode'], 'random')
        self.assertEqual(initial['languages']['en']['mode'], 'random')
        self.assertFalse(initial['languages']['zh']['pinyin'])
        self.assertNotEqual(initial['languages']['zh']['peak']['id'], initial['languages']['en']['peak']['id'])
        self.client.force_authenticate(self.bob)
        self.assertEqual(self.client.get(scope).data['activities'], [initial])
        self.assertEqual(self.start(self.bob, initial['id'], 'en').status_code, 201)
        self.assertEqual(TypingActivity.objects.count(), 1)
        self.assertEqual(TypingClassSettings.objects.count(), 1)

    def test_save_parameters_replaces_current_and_preserves_in_progress_attempt(self):
        self.client.force_authenticate(self.alice)
        initial, = self.client.get('/api/typing/activities/').data['activities']
        started = self.start(self.alice, initial['id']).data
        published = self.publish(zh={'mode': 'free', 'difficulty': '基础', 'pinyin': True})
        self.assertEqual(published.status_code, 201, published.data)
        current = published.data
        self.assertFalse(current['is_default'])
        self.assertNotEqual(current['id'], initial['id'])
        self.assertEqual(self.client.get('/api/typing/teacher/activities/?grade=7&class_num=1').data, current)
        self.assertEqual(self.start(self.bob, initial['id']).status_code, 409)
        listing = self.client.get('/api/typing/activities/').data
        next_activity, = listing['activities']
        self.assertEqual(next_activity['id'], current['id'])
        self.assertEqual(next_activity['languages']['zh']['mode'], 'free')
        self.assertTrue(next_activity['languages']['zh']['pinyin'])
        option = next_activity['languages']['zh']['articles'][0]
        self.assertEqual(self.start(self.bob, current['id'], article_id=option['id']).status_code, 201)
        self.client.force_authenticate(self.alice)
        resumed = self.client.get(f"/api/typing/attempts/{started['id']}/").data
        self.assertEqual(resumed['deadline_at'], started['deadline_at'])
        self.assertEqual(resumed['article'], started['article'])
        self.assertEqual(resumed['activity']['id'], initial['id'])
        self.assertFalse(resumed['activity']['languages']['zh']['pinyin'])

    def test_checkpoint_updates_real_board_and_settles_once(self):
        activity = self.publish().data['id']
        first = self.start(self.alice, activity).data
        second = self.start(self.bob, activity).data
        attempt_id = first['id']
        text = ''.join(first['article']['paragraphs'])[:12]
        checkpoint = {'seq': 1, 'segments': [{'text': text, 'first': '错' + text[1:]}]}
        sync_url = f'/api/typing/attempts/{attempt_id}/sync/'
        self.client.force_authenticate(self.alice)
        sync = self.client.post(sync_url, checkpoint, format='json')
        self.assertEqual(sync.status_code, 200, sync.data)
        self.assertEqual(sync.data['ack'], 1)
        self.assertEqual(sync.data['board'][0]['id'], self.alice.id)
        self.assertGreater(sync.data['board'][0]['progress'], 0)
        self.assertEqual(sync.data['board'][1]['id'], self.bob.id)
        reloaded = self.client.get(f'/api/typing/attempts/{attempt_id}/').data
        self.assertEqual(reloaded['checkpoint'], checkpoint['segments'])
        self.assertEqual(len(reloaded['articles']), 1)

        self.client.force_authenticate(self.bob)
        boards = f'/api/typing/activities/{activity}/leaderboard/'
        self.assertEqual(self.client.get(boards + '?language=en').data, [])
        self.assertEqual(self.client.get(boards + '?language=zh').data[0]['self'], False)
        self.assertEqual(self.client.post(sync_url, checkpoint, format='json').status_code, 404)
        self.client.force_authenticate(self.other_class)
        self.assertEqual(self.client.get(boards + '?language=zh').status_code, 404)
        self.client.force_authenticate(self.alice)
        with patch('typing_practice.workspace.timezone.now', return_value=first['deadline_at'] + timedelta(seconds=1)):
            checkpoint['seq'] = 2
            checkpoint['segments'] = []
            finished = self.client.post(sync_url, checkpoint, format='json').data
            replay = self.client.post(sync_url, checkpoint, format='json').data
            self.assertEqual(finished['result'], replay['result'])
            self.assertEqual(finished['ack'], 1)
            # 分数是成绩，积分是按折算系数算出的实发值（默认 0.6），两者不再相等
            from points.services import typing_points_for
            score = Decimal(finished['result']['score'])
            self.assertEqual(Decimal(finished['result']['points']), typing_points_for(score))
            self.assertLess(Decimal(finished['result']['points']), score)
            self.assertEqual(finished['result']['accuracy'], 100)
            self.assertEqual(TypingPointSubmission.objects.filter(attempt_id=attempt_id).count(), 1)
            self.assertIsNone(TypingAttempt.objects.get(pk=attempt_id).active_student_id)
        self.assertNotEqual(second['id'], attempt_id)

    def test_finishing_single_article_settles_early_with_actual_speed(self):
        activity = self.publish().data['id']
        started = self.start(self.alice, activity).data
        text = ''.join(started['article']['paragraphs'])
        url = f'/api/typing/attempts/{started["id"]}/sync/'
        self.client.force_authenticate(self.alice)
        premature = self.client.post(url, {
            'seq': 1, 'segments': [{'text': text[:2], 'first': text[:2]}], 'complete': True,
        }, format='json')
        self.assertEqual(premature.status_code, 400)
        self.assertEqual(TypingPointSubmission.objects.filter(attempt_id=started['id']).count(), 0)

        with patch('typing_practice.workspace.timezone.now',
                   return_value=started['started_at'] + timedelta(seconds=60)):
            completed = self.client.post(url, {
                'seq': 2, 'segments': [{'text': text, 'first': text}], 'complete': True,
            }, format='json')
        self.assertEqual(completed.status_code, 200, completed.data)
        self.assertIsNotNone(completed.data['result'])
        self.assertEqual(completed.data['result']['speed'],
                         sum('\u4e00' <= char <= '\u9fff' for char in text))
        self.assertEqual(TypingPointSubmission.objects.filter(attempt_id=started['id']).count(), 1)

    def test_pause_preserves_checkpoint_through_original_deadline(self):
        activity = self.publish().data['id']
        started = self.start(self.alice, activity).data
        attempt_id = started['id']
        begin = started['started_at']
        url = f'/api/typing/attempts/{attempt_id}/'
        typed = ''.join(started['article']['paragraphs'])[:7]
        checkpoint = {'seq': 1, 'segments': [{'text': typed, 'first': typed}]}

        with patch('typing_practice.workspace.timezone.now', return_value=begin + timedelta(seconds=40)):
            response = self.client.post(url + 'pause/', checkpoint, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertTrue(response.data['paused'])
            self.assertEqual(response.data['remaining_ms'], 260_000)

        resumed_at = begin + timedelta(seconds=340)
        with patch('typing_practice.workspace.timezone.now', return_value=resumed_at):
            state = self.client.get(url).data
            self.assertTrue(state['paused'])
            self.assertFalse(state['expired'])
            self.assertEqual(state['remaining_ms'], 260_000)
            self.assertEqual(state['checkpoint'], checkpoint['segments'])
            self.assertEqual(self.client.get('/api/typing/activities/').data['active_attempt_id'], attempt_id)
            self.assertEqual(self.start(self.alice, activity, 'en').status_code, 409)
            self.assertFalse(TypingPointSubmission.objects.filter(attempt_id=attempt_id).exists())
            running = self.client.post(url + 'resume/').data
            self.assertFalse(running['paused'])
            self.assertEqual(running['deadline_at'], resumed_at + timedelta(seconds=260))
            self.assertEqual(running['remaining_ms'], 260_000)
            self.assertEqual(self.client.post(url + 'resume/').data['deadline_at'], running['deadline_at'])
