#!/usr/bin/env python3
"""Create, execute, settle, and remove one real mixed AI quiz."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from decimal import Decimal

from benchmark_local_runner import PROJECT_ROOT, request_json
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from ai_courses.models import (
    AIChoiceQuestion,
    AIQuizAttempt,
    AIQuizSession,
    AIUnit,
    Problem,
    Submission,
)
from ai_courses.quizzes.services import create_quiz, publish_quiz
from execution.models import ExecutionTask


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    problem_id = f'step6_mixed_{run_id}'
    problem_dir = settings.PROBLEMS_DIR / 'ai' / 'programming' / '八年级' / problem_id
    teacher = student = root = section = question = problem = session = attempt = None
    try:
        problem_dir.mkdir(parents=True, exist_ok=False)
        (problem_dir / 'input1.txt').write_text('', encoding='utf-8')
        (problem_dir / 'output1.txt').write_text('MIXED_OK\n', encoding='utf-8')

        User = get_user_model()
        teacher = User.objects.create_user(
            username=f'__step6_teacher_{run_id}', password=None, role='teacher',
            managed_grade='八年级',
        )
        student = User.objects.create_user(
            username=f'__step6_student_{run_id}', password=None, role='student',
            grade='八年级', class_num='20', student_number=f'Q{run_id}',
            display_name='混合小测验收',
        )
        token = Token.objects.create(user=student).key
        root = AIUnit.objects.create(
            grade='八年级', name=f'step6-root-{run_id}', display_name='Step6 验收',
            created_by=teacher,
        )
        section = AIUnit.objects.create(
            grade='八年级', parent=root, name=f'step6-section-{run_id}',
            display_name='混合小测', created_by=teacher,
        )
        question = AIChoiceQuestion.objects.create(
            unit=section, difficulty='easy', category='验收', text='Python 文件扩展名是什么？',
            option_a='.py', option_b='.txt', option_c='.jpg', option_d='.xlsx', answer='A',
            explanation='Python 源代码通常使用 .py 扩展名。', created_by=teacher,
        )
        problem = Problem.objects.create(
            problem_id=problem_id, title='输出 MIXED_OK', description='输出 MIXED_OK',
            template_code='', difficulty='easy', grade_tag='八年级', unit=section,
            course='ai', created_by=teacher,
        )
        session = create_quiz(actor=teacher, values={
            'title': f'Step6 混合小测 {run_id}',
            'content_grade': '八年级',
            'choice_unit_ids': [section.pk],
            'choice_question_count': 1,
            'choice_difficulty_ratio': {'easy': 1, 'medium': 0, 'hard': 0},
            'choice_points': Decimal('40.0'),
            'programming_items': [{'problem_id': problem_id, 'position': 1, 'points': Decimal('60.0')}],
            'time_limit': 30,
            'audience': [{'scope_type': 'grade_all', 'grade': '八年级'}],
        })
        session = publish_quiz(actor=teacher, session_id=session.pk, expected_version=1)

        base_url = 'http://127.0.0.1:8080'
        status, started = request_json(
            'POST', f'{base_url}/api/ai/quizzes/{session.pk}/attempt/', token=token, body={},
        )
        if status not in (200, 201):
            raise RuntimeError(f'开始小测失败: HTTP {status} {started}')
        attempt = AIQuizAttempt.objects.get(pk=started['attempt_id'])
        choice_item = next(item for item in attempt.snapshot_json['items'] if item['type'] == 'choice')
        programming_item = next(item for item in attempt.snapshot_json['items'] if item['type'] == 'programming')

        status, queued = request_json(
            'POST',
            f'{base_url}/api/ai/quizzes/{session.pk}/attempt/items/{programming_item["item_id"]}/submit/',
            token=token,
            body={'attempt_id': attempt.pk, 'code': 'print("MIXED_OK")'},
            idempotency_key=str(uuid.uuid4()),
        )
        if status != 202:
            raise RuntimeError(f'编程题提交失败: HTTP {status} {queued}')

        deadline = time.monotonic() + 30
        grade = None
        while time.monotonic() < deadline:
            status, grade = request_json(
                'GET', f'{base_url}/api/ai/executions/{queued["task_id"]}/', token=token,
            )
            if status == 200 and grade.get('status') not in {'queued', 'running'}:
                break
            time.sleep(0.2)
        if not grade or grade.get('status') != 'succeeded' or grade.get('score') != 100:
            raise RuntimeError(f'编程题评测未通过: {grade}')

        status, settled = request_json(
            'POST', f'{base_url}/api/ai/quizzes/{session.pk}/attempt/submit/', token=token,
            body={
                'attempt_id': attempt.pk,
                'revision': 0,
                'answers': {choice_item['item_id']: choice_item['correct_display_option']},
            },
        )
        passed = (
            status == 200
            and settled.get('status') == 'submitted'
            and settled.get('scores') == {'choice': '40.0', 'programming': '60.0', 'total': '100.0'}
        )
        print(json.dumps({
            'passed': passed,
            'attempt_created': started.get('created'),
            'programming_task_status': grade.get('status'),
            'programming_score': grade.get('score'),
            'quiz_status': settled.get('status'),
            'scores': settled.get('scores'),
            'grading_issue_count': settled.get('grading_issue_count'),
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if passed else 1
    finally:
        if attempt is not None:
            Submission.objects.filter(quiz_attempt=attempt).delete()
            ExecutionTask.objects.filter(quiz_attempt=attempt).delete()
            AIQuizAttempt.objects.filter(pk=attempt.pk).delete()
        if session is not None:
            AIQuizSession.objects.filter(pk=session.pk).delete()
        if problem is not None:
            Problem.objects.filter(pk=problem.pk).delete()
        if question is not None:
            AIChoiceQuestion.objects.filter(pk=question.pk).delete()
        if section is not None:
            AIUnit.objects.filter(pk=section.pk).delete()
        if root is not None:
            AIUnit.objects.filter(pk=root.pk).delete()
        if student is not None:
            get_user_model().objects.filter(pk=student.pk).delete()
        if teacher is not None:
            get_user_model().objects.filter(pk=teacher.pk).delete()
        if problem_dir.exists() and problem_dir.is_dir() and problem_dir.name == problem_id:
            shutil.rmtree(problem_dir)


if __name__ == '__main__':
    raise SystemExit(main())
