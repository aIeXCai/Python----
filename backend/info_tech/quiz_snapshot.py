import random
import uuid

from .models import Question


DISPLAY_LETTERS = ('A', 'B', 'C', 'D')


class SnapshotBuildError(ValueError):
    pass


def _question_options(question):
    return {
        'A': question.option_a,
        'B': question.option_b,
        'C': question.option_c,
        'D': question.option_d,
    }


def build_quiz_snapshot(session, *, rng=None):
    """Create the immutable server-side paper for one student."""
    rng = rng or random.SystemRandom()
    questions = list(Question.objects.filter(unit__in=session.units.all()).distinct())
    if len(questions) < session.num_questions:
        raise SnapshotBuildError(
            f'题库只有 {len(questions)} 题，无法生成 {session.num_questions} 题的小测'
        )

    grouped = {'easy': [], 'medium': [], 'hard': []}
    for question in questions:
        grouped.setdefault(question.difficulty, []).append(question)

    selected = []
    selected_ids = set()
    ratio = session.difficulty_ratio if isinstance(session.difficulty_ratio, dict) else {}
    for difficulty in ('easy', 'medium', 'hard'):
        raw_count = ratio.get(difficulty, 0)
        count = int(raw_count) if isinstance(raw_count, (int, float)) else 0
        pool = list(grouped.get(difficulty, ()))
        rng.shuffle(pool)
        for question in pool[:max(0, count)]:
            if question.pk not in selected_ids and len(selected) < session.num_questions:
                selected.append(question)
                selected_ids.add(question.pk)

    if len(selected) < session.num_questions:
        remaining = [q for q in questions if q.pk not in selected_ids]
        rng.shuffle(remaining)
        selected.extend(remaining[:session.num_questions - len(selected)])

    if len(selected) != session.num_questions:
        raise SnapshotBuildError('题库配置无法生成完整试卷')

    rng.shuffle(selected)
    snapshot_questions = []
    for position, question in enumerate(selected, start=1):
        if question.answer.upper() not in DISPLAY_LETTERS:
            raise SnapshotBuildError(f'题目 {question.pk} 的正确答案不是 A-D')
        source_order = list(DISPLAY_LETTERS)
        rng.shuffle(source_order)
        source_options = _question_options(question)
        displayed_options = {
            display_letter: source_options[source_letter]
            for display_letter, source_letter in zip(DISPLAY_LETTERS, source_order)
        }
        correct_index = source_order.index(question.answer.upper())
        snapshot_questions.append({
            'item_id': str(uuid.uuid4()),
            'source_question_id': question.pk,
            'position': position,
            'text': question.text,
            'category': question.category,
            'difficulty': question.difficulty,
            'options': displayed_options,
            'correct_option': DISPLAY_LETTERS[correct_index],
            'explanation': question.explanation,
        })

    return {
        'schema_version': 1,
        'session_title': session.title,
        'question_count': len(snapshot_questions),
        'questions': snapshot_questions,
    }


def student_snapshot_questions(snapshot):
    """Explicit allow-list: never expose source ids, answers, mappings or explanations."""
    return [
        {
            'item_id': item['item_id'],
            'position': item['position'],
            'text': item['text'],
            'category': item.get('category', ''),
            'options': dict(item['options']),
        }
        for item in snapshot.get('questions', [])
    ]


def result_payload(attempt):
    snapshot = attempt.snapshot_json or {}
    answers = attempt.answers
    wrong_questions = []
    for item in snapshot.get('questions', []):
        user_answer = answers.get(item['item_id'])
        correct_answer = item['correct_option']
        if user_answer == correct_answer:
            continue
        options = {
            letter: {
                'text': text,
                'is_user_answer': user_answer == letter,
                'is_correct_answer': correct_answer == letter,
            }
            for letter, text in item['options'].items()
        }
        wrong_questions.append({
            'item_id': item['item_id'],
            'question_id': item['item_id'],
            'text': item['text'],
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': False,
            'explanation': item.get('explanation', ''),
            'options': options,
        })
    return {
        'submission_id': attempt.pk,
        'attempt_id': attempt.pk,
        'quiz_title': snapshot.get('session_title') or attempt.session.title,
        'status': attempt.status,
        'score': attempt.score,
        'correct_count': attempt.correct_count,
        'total_count': attempt.total_count,
        'submitted_at': attempt.submitted_at,
        'question_results': wrong_questions,
        'legacy_record': False,
        'analysis_available': True,
        'can_retry': attempt.session.status == attempt.session.STATUS_OPEN,
    }
