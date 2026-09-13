"""Build immutable per-student papers from an AI quiz publish blueprint."""

import random
import uuid

from .quiz_services import blueprint_digest


class AIQuizSnapshotError(ValueError):
    def __init__(self, message, *, code='quiz_blueprint_invalid'):
        super().__init__(message)
        self.message = message
        self.code = code


def _choice_item(source, position, *, rng, uuid_factory):
    source_options = source.get('options') or {}
    if set(source_options) != set('ABCD'):
        raise AIQuizSnapshotError('发布蓝图中的选择题选项不完整')
    source_order = list('ABCD')
    rng.shuffle(source_order)
    options = {
        display: source_options[source_letter]
        for display, source_letter in zip('ABCD', source_order)
    }
    correct_source = source.get('correct_source_option')
    if correct_source not in source_order:
        raise AIQuizSnapshotError('发布蓝图中的选择题答案无效')
    correct_display = 'ABCD'[source_order.index(correct_source)]
    return {
        'item_id': str(uuid_factory()),
        'type': 'choice',
        'position': position,
        'source_question_id': source.get('source_question_id'),
        'source_version': source.get('source_version'),
        'unit_id': source.get('unit_id'),
        'difficulty': source.get('difficulty', ''),
        'category': source.get('category', ''),
        'text': source.get('text', ''),
        'options': options,
        'source_option_by_display': dict(zip('ABCD', source_order)),
        'correct_display_option': correct_display,
        'explanation': source.get('explanation', ''),
    }


def build_attempt_snapshot(session, *, rng=None, uuid_factory=uuid.uuid4):
    blueprint = session.blueprint_json or {}
    if (
        session.blueprint_version != 1
        or blueprint.get('schema_version') != 1
        or not session.blueprint_hash
        or blueprint_digest(blueprint) != session.blueprint_hash
    ):
        raise AIQuizSnapshotError('小测发布蓝图缺失或校验失败')
    rng = rng or random.SystemRandom()
    config = blueprint.get('session') or {}
    ratio = config.get('choice_difficulty_ratio') or {}
    pool = blueprint.get('choice_pool') or []
    selected = []
    for difficulty in ('easy', 'medium', 'hard'):
        required = ratio.get(difficulty, 0)
        if isinstance(required, bool) or not isinstance(required, int) or required < 0:
            raise AIQuizSnapshotError('发布蓝图中的难度题数无效')
        candidates = [item for item in pool if item.get('difficulty') == difficulty]
        if len(candidates) < required:
            raise AIQuizSnapshotError(
                '冻结题池不足，无法生成完整试卷', code='quiz_pool_insufficient',
            )
        selected.extend(rng.sample(candidates, required))
    expected_count = config.get('choice_question_count', 0)
    if len(selected) != expected_count:
        raise AIQuizSnapshotError('发布蓝图中的选择题数量不一致')
    rng.shuffle(selected)
    choice_items = [
        _choice_item(source, position, rng=rng, uuid_factory=uuid_factory)
        for position, source in enumerate(selected, 1)
    ]

    programming_items = []
    for source in sorted(
        blueprint.get('programming_items') or [], key=lambda item: item.get('position', 0),
    ):
        item_id = source.get('item_id')
        if not item_id:
            raise AIQuizSnapshotError('发布蓝图中的编程题标识缺失')
        programming_items.append({
            'item_id': item_id,
            'type': 'programming',
            'position': len(choice_items) + source.get('position', 0),
            'programming_position': source.get('position'),
            'source_problem_id': source.get('source_problem_id'),
            'source_management_version': source.get('source_management_version'),
            'title': source.get('title', ''),
            'description': source.get('description', ''),
            'template_code': source.get('template_code', ''),
            'points': source.get('points', '0.0'),
            'test_snapshot_hash': source.get('test_snapshot_hash', ''),
        })

    return {
        'schema_version': 1,
        'session_id': session.pk,
        'blueprint_version': session.blueprint_version,
        'blueprint_hash': session.blueprint_hash,
        'session': {
            'title': config.get('title') or session.title,
            'content_grade': config.get('content_grade') or session.content_grade,
            'time_limit': config.get('time_limit'),
            'choice_question_count': len(choice_items),
            'programming_question_count': len(programming_items),
            'choice_points': config.get('choice_points', '0.0'),
            'total_points': '100.0',
        },
        'items': [*choice_items, *programming_items],
    }


def student_snapshot_items(snapshot):
    """Explicit allowlist: never return answers, mappings, source IDs, or hidden tests."""
    visible = []
    for item in (snapshot or {}).get('items', []):
        if item.get('type') == 'choice':
            visible.append({
                'item_id': item.get('item_id'),
                'type': 'choice',
                'position': item.get('position'),
                'difficulty': item.get('difficulty', ''),
                'category': item.get('category', ''),
                'text': item.get('text', ''),
                'options': item.get('options') or {},
            })
        elif item.get('type') == 'programming':
            visible.append({
                'item_id': item.get('item_id'),
                'type': 'programming',
                'position': item.get('position'),
                'title': item.get('title', ''),
                'points': item.get('points', '0.0'),
            })
    return visible
