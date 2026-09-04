from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class QuizAttemptMigrationTests(TransactionTestCase):
    migrate_from = ('info_tech', '0003_add_grade_parent_to_unit')
    migrate_to = ('info_tech', '0007_quizsession_archived_at')
    users_latest = ('users', '0007_remove_plain_password')

    @property
    def executor(self):
        return MigrationExecutor(connection)

    def setUp(self):
        super().setUp()
        executor = self.executor
        executor.migrate([self.migrate_from, self.users_latest])
        apps = executor.loader.project_state([self.migrate_from, self.users_latest]).apps
        User = apps.get_model('users', 'CustomUser')
        Unit = apps.get_model('info_tech', 'Unit')
        QuizSession = apps.get_model('info_tech', 'QuizSession')
        QuizSubmission = apps.get_model('info_tech', 'QuizSubmission')

        teacher = User.objects.create(username='migration-quiz-teacher', role='teacher')
        student = User.objects.create(
            username='migration-quiz-student', role='student',
            grade='七年级', class_num='2', student_number='09',
        )
        unit = Unit.objects.create(grade='七年级', name='migrate', display_name='迁移单元')
        self.open_session_id = QuizSession.objects.create(
            title='开放小测', created_by=teacher, num_questions=2,
            difficulty_ratio={'easy': 2}, is_visible=True,
        ).pk
        open_session = QuizSession.objects.get(pk=self.open_session_id)
        open_session.units.add(unit)
        self.draft_session_id = QuizSession.objects.create(
            title='草稿小测', created_by=teacher, num_questions=2,
            difficulty_ratio={'easy': 2}, is_visible=False,
        ).pk
        first = QuizSubmission.objects.create(
            user=student, session=open_session, grade='七年级', score=50,
            correct_count=1, total_count=2, answers_json='{"1":"A"}',
        )
        second = QuizSubmission.objects.create(
            user=student, session=open_session, grade='七年级', score=100,
            correct_count=2, total_count=2, answers_json='{"1":"A","2":"B"}',
        )
        self.first_id = first.pk
        self.second_id = second.pk

        executor = self.executor
        executor.migrate([self.migrate_to, self.users_latest])
        self.apps = executor.loader.project_state([self.migrate_to, self.users_latest]).apps

    def tearDown(self):
        self.executor.migrate(self.executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_sessions_and_attempt_history_are_backfilled(self):
        QuizSession = self.apps.get_model('info_tech', 'QuizSession')
        QuizSubmission = self.apps.get_model('info_tech', 'QuizSubmission')
        opened = QuizSession.objects.get(pk=self.open_session_id)
        draft = QuizSession.objects.get(pk=self.draft_session_id)
        self.assertEqual(opened.status, 'open')
        self.assertIsNotNone(opened.opened_at)
        self.assertEqual(draft.status, 'draft')
        self.assertEqual(opened.visible_classes, [])
        self.assertEqual(draft.visible_classes, [])
        self.assertIsNone(opened.archived_at)
        self.assertIsNone(draft.archived_at)

        first = QuizSubmission.objects.get(pk=self.first_id)
        second = QuizSubmission.objects.get(pk=self.second_id)
        self.assertEqual((first.attempt_no, first.status, first.current_marker), (1, 'superseded', None))
        self.assertEqual((second.attempt_no, second.status, second.current_marker), (2, 'submitted', True))
        self.assertEqual(second.class_num_snapshot, '2')
        self.assertEqual(second.student_number_snapshot, '09')

    def test_legacy_visibility_column_is_removed(self):
        QuizSession = self.apps.get_model('info_tech', 'QuizSession')
        with connection.cursor() as cursor:
            columns = {
                column.name
                for column in connection.introspection.get_table_description(cursor, QuizSession._meta.db_table)
            }
        self.assertNotIn('is_visible', columns)
