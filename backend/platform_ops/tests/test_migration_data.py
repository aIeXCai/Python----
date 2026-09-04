import json
import os
import sqlite3
import tempfile
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase

from ai_courses.models import Problem
from chat.models import ChatMessage, ChatSession
from info_tech.models import QuizSession, Unit
from platform_ops.management.commands.backup_platform_sqlite import sqlite_checks
from platform_ops.migration_data import (
    MANIFEST_VERSION,
    MODEL_LABELS,
    assert_business_tables_empty,
    database_summary,
    validate_local_mysql_target,
    validate_manifest,
    write_private_bytes,
    write_private_json,
)
from rest_framework.authtoken.models import Token
from users.models import CustomUser, PasswordSecurityAudit
from users.services import set_student_password


class MigrationDataTests(TestCase):
    def create_sensitive_graph(self):
        user = CustomUser.objects.create(
            username='migration-student',
            role='student',
            grade='七年级', class_num='1', student_number='01',
        )
        set_student_password(
            user, 'private-password-value', validate=False, invalidate_tokens=False
        )
        PasswordSecurityAudit.objects.create(
            event_type='reveal', actor_user_id=99, target_user_id=user.pk,
            outcome='success', reason_code='test_only',
        )
        Token.objects.create(user=user)
        problem = Problem.objects.create(
            problem_id='migration-problem',
            title='迁移题目',
            description='private-code-and-description',
        )
        parent = Unit.objects.create(name='parent', display_name='大单元', order=1)
        child = Unit.objects.create(
            name='child', display_name='小节', order=2, parent=parent
        )
        quiz = QuizSession.objects.create(
            title='迁移小测',
            created_by=user,
            num_questions=1,
            difficulty_ratio={'easy': 1},
            visible_grades=['七年级'],
        )
        quiz.units.add(child)
        session = ChatSession.objects.create(user=user, title='迁移对话')
        ChatMessage.objects.create(
            session=session,
            role='user',
            content='private-chat-content',
        )
        return problem

    def test_model_order_covers_required_business_models(self):
        self.assertEqual(
            MODEL_LABELS,
            (
                'auth.Group',
                'users.CustomUser',
                'users.PasswordSecurityAudit',
                'authtoken.Token',
                'ai_courses.Problem',
                'info_tech.Unit',
                'ai_courses.Submission',
                'info_tech.Question',
                'info_tech.QuizSession',
                'info_tech.QuizSubmission',
                'chat.ChatSession',
                'chat.ChatMessage',
            ),
        )

    def test_summary_is_deterministic_and_manifest_safe(self):
        self.create_sensitive_graph()
        first, _ = database_summary()
        second, _ = database_summary()
        self.assertEqual(first, second)
        rendered = json.dumps(first, ensure_ascii=False)
        for secret in (
            'private-password-value',
            'private-code-and-description',
            'private-chat-content',
        ):
            self.assertNotIn(secret, rendered)

    def test_content_change_changes_overall_digest(self):
        problem = self.create_sensitive_graph()
        before, _ = database_summary()
        problem.title = '变更后的题目'
        problem.save(update_fields=['title'])
        after, _ = database_summary()
        self.assertNotEqual(before['overall_sha256'], after['overall_sha256'])

    def test_relation_counts_include_quiz_units(self):
        self.create_sensitive_graph()
        summary, _ = database_summary()
        self.assertEqual(summary['relations']['info_tech.quizsession.units'], 1)

    def test_empty_guard_rejects_existing_business_data(self):
        self.create_sensitive_graph()
        with self.assertRaisesMessage(ImproperlyConfigured, '目标业务表不是空库'):
            assert_business_tables_empty()

    def test_relationship_graph_and_cascade_behavior(self):
        self.create_sensitive_graph()
        user = CustomUser.objects.get(username='migration-student')
        parent = Unit.objects.get(name='parent')
        child_id = Unit.objects.get(name='child').pk

        parent.delete()
        self.assertFalse(Unit.objects.filter(pk=child_id).exists())
        self.assertEqual(QuizSession.units.through.objects.count(), 0)

        user.delete()
        self.assertEqual(Token.objects.count(), 0)
        self.assertEqual(QuizSession.objects.count(), 0)
        self.assertEqual(ChatSession.objects.count(), 0)
        self.assertEqual(ChatMessage.objects.count(), 0)


class MigrationSafetyHelperTests(SimpleTestCase):
    def test_local_mysql_target_guard(self):
        self.assertIsNone(
            validate_local_mysql_target(
                'mysql', '127.0.0.1', 3308, 'python_learning_stage2'
            )
        )
        invalid_targets = (
            ('sqlite', '127.0.0.1', 3308, 'python_learning_stage2'),
            ('mysql', 'db.example.com', 3308, 'python_learning_stage2'),
            ('mysql', '127.0.0.1', 3306, 'python_learning_stage2'),
            ('mysql', '127.0.0.1', 3308, 'production'),
        )
        for values in invalid_targets:
            with self.subTest(values=values), self.assertRaises(ImproperlyConfigured):
                validate_local_mysql_target(*values)

    def test_manifest_schema_validation(self):
        valid = {
            'manifest_version': MANIFEST_VERSION,
            'fixture_sha256': 'a',
            'models': {},
            'relations': {},
            'migrations': [],
            'overall_sha256': 'b',
        }
        self.assertIsNone(validate_manifest(valid))
        for key in tuple(valid):
            broken = {**valid}
            broken.pop(key)
            with self.subTest(key=key), self.assertRaises(ImproperlyConfigured):
                validate_manifest(broken)

    def test_private_writers_set_0600_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            bytes_path = Path(directory) / 'data.bin'
            json_path = Path(directory) / 'data.json'
            write_private_bytes(bytes_path, b'sensitive')
            write_private_json(json_path, {'digest': 'safe'})
            self.assertEqual(os.stat(bytes_path).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(json_path).st_mode & 0o777, 0o600)

    def test_sqlite_checks_detect_foreign_key_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'broken.sqlite3'
            with sqlite3.connect(database) as sqlite_connection:
                sqlite_connection.execute('PRAGMA foreign_keys=OFF')
                sqlite_connection.execute('CREATE TABLE parent (id INTEGER PRIMARY KEY)')
                sqlite_connection.execute(
                    'CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id))'
                )
                sqlite_connection.execute('INSERT INTO child VALUES (1, 999)')
                integrity, foreign_keys = sqlite_checks(sqlite_connection)
            self.assertEqual(integrity, ['ok'])
            self.assertEqual(len(foreign_keys), 1)
