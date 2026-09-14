"""Transactional services for AI quiz drafts and immutable publish blueprints."""

import hashlib
import json
import logging
import uuid
from decimal import Decimal
from functools import wraps

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from execution.models import ExecutionTask
from execution.snapshots import InvalidTestSnapshot, build_test_snapshot, snapshot_digest
from users.grade_levels import normalize_grade, normalize_student_identifier
from users.models import CustomUser
from users.scopes import TeacherScopeError, is_platform_admin, require_teacher_grade, scope_by_grade

from ..models import (
    AUDIENCE_ALL_SCHOOL,
    AUDIENCE_CLASS,
    AUDIENCE_GRADE_ALL,
    AIChoiceQuestion,
    AIQuizAttempt,
    AIQuizAudience,
    AIQuizManagementAudit,
    AIQuizProgrammingItem,
    AIQuizSession,
    AIUnit,
    Problem,
    Submission,
)
from ..problems.eligibility import programming_quiz_eligibility


logger = logging.getLogger(__name__)


class AIQuizServiceError(Exception):
    def __init__(
        self, message, *, code='invalid_request', status_code=400,
        current_version=None, details=None, **extra,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.current_version = current_version
        self.details = details
        self.extra = extra


def canonical_blueprint_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def blueprint_digest(value):
    return hashlib.sha256(canonical_blueprint_json(value).encode('utf-8')).hexdigest()


def _summary(session):
    return {
        'title': session.title,
        'content_grade': session.content_grade,
        'status': session.status,
        'management_version': session.management_version,
        'blueprint_version': session.blueprint_version,
        'blueprint_hash': session.blueprint_hash,
        'choice_question_count': session.choice_question_count,
        'choice_points': format(session.choice_points, '.1f'),
        'programming_item_count': session.programming_items.count() if session.pk else 0,
        'active_audience_count': session.audience_rules.filter(is_active=True).count() if session.pk else 0,
        'archived': session.archived_at is not None,
    }


def _audit(
    *, event_type, outcome, actor, object_id='', reason_code='',
    before=None, after=None, source_ip=None,
):
    return AIQuizManagementAudit.objects.create(
        event_type=event_type,
        outcome=outcome,
        actor_user_id=getattr(actor, 'pk', None),
        object_type='quiz',
        object_id=str(object_id or ''),
        reason_code=reason_code,
        before_summary=before or {},
        after_summary=after or {},
        source_ip=source_ip,
    )


def _audit_failures(event_type):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except AIQuizServiceError as exc:
                outcome = 'conflict' if exc.status_code == 409 else (
                    'denied' if exc.status_code == 403 else 'failed'
                )
                _audit(
                    event_type=event_type,
                    outcome=outcome,
                    actor=kwargs.get('actor'),
                    object_id=kwargs.get('session_id', ''),
                    reason_code=exc.code,
                    source_ip=kwargs.get('source_ip'),
                )
                raise
        return wrapper
    return decorator


def scoped_quizzes(actor, *, include_archived=False):
    queryset = scope_by_grade(
        AIQuizSession.objects.select_related('created_by').prefetch_related(
            'choice_units', 'programming_items__problem', 'audience_rules',
        ),
        actor,
        'content_grade',
    )
    if not include_archived:
        queryset = queryset.filter(archived_at__isnull=True)
    return queryset


def _locked_session(actor, session_id, *, include_archived=False):
    queryset = scope_by_grade(
        AIQuizSession.objects.select_for_update(), actor, 'content_grade',
    )
    if not include_archived:
        queryset = queryset.filter(archived_at__isnull=True)
    try:
        return queryset.get(pk=session_id)
    except AIQuizSession.DoesNotExist as exc:
        raise AIQuizServiceError(
            '小测不存在', code='quiz_not_found', status_code=404,
        ) from exc


def _check_version(session, expected_version):
    if session.management_version != expected_version:
        raise AIQuizServiceError(
            '小测已被其他教师更新，请重新加载',
            code='version_conflict', status_code=409,
            current_version=session.management_version,
        )


def _required_grade(actor, requested):
    try:
        grade = require_teacher_grade(actor, requested)
    except TeacherScopeError as exc:
        status_code = 400 if exc.code == 'invalid_grade' else 403
        raise AIQuizServiceError(
            exc.message, code=exc.code, status_code=status_code,
        ) from exc
    if not grade:
        raise AIQuizServiceError('请指定内容年级', code='grade_required')
    return grade


def _resolve_units(unit_ids, grade, *, lock=False):
    unit_ids = list(dict.fromkeys(unit_ids))
    if not unit_ids:
        return []
    queryset = AIUnit.objects.select_related('parent').filter(
        pk__in=unit_ids,
        grade=grade,
        parent__isnull=False,
        archived_at__isnull=True,
        parent__archived_at__isnull=True,
    )
    if lock:
        queryset = queryset.select_for_update()
    units_by_id = {unit.pk: unit for unit in queryset}
    if len(units_by_id) != len(unit_ids):
        raise AIQuizServiceError(
            '选择题小节不存在、已归档或不属于内容年级',
            code='invalid_choice_unit',
        )
    return [units_by_id[unit_id] for unit_id in unit_ids]


def _resolve_programming_items(items, grade, *, lock=False):
    problem_ids = [item['problem_id'] for item in items]
    positions = [item['position'] for item in items]
    if len(problem_ids) != len(set(problem_ids)):
        raise AIQuizServiceError('编程题不能重复', code='duplicate_programming_problem')
    if len(positions) != len(set(positions)):
        raise AIQuizServiceError('编程题顺序不能重复', code='duplicate_programming_position')
    if sorted(positions) != list(range(1, len(positions) + 1)):
        raise AIQuizServiceError(
            '编程题顺序必须从 1 开始且连续', code='invalid_programming_position',
        )
    queryset = Problem.objects.select_related('unit', 'unit__parent').filter(
        problem_id__in=problem_ids,
        course='ai',
        archived_at__isnull=True,
        grade_tag=grade,
        unit__grade=grade,
        unit__parent__isnull=False,
        unit__archived_at__isnull=True,
        unit__parent__archived_at__isnull=True,
    )
    if lock:
        queryset = queryset.select_for_update()
    problems = {problem.problem_id: problem for problem in queryset}
    if len(problems) != len(problem_ids):
        raise AIQuizServiceError(
            '包含未归类、已归档或跨年级的编程题',
            code='invalid_programming_problem',
        )
    return [
        {
            'problem': problems[item['problem_id']],
            'position': item['position'],
            'points': item['points'],
        }
        for item in sorted(items, key=lambda value: value['position'])
    ]


def _current_programming_values(session):
    return [
        {
            'problem_id': item.problem.problem_id,
            'position': item.position,
            'points': item.points,
        }
        for item in session.programming_items.select_related('problem').order_by('position')
    ]


def _known_classes(grade):
    return set(
        CustomUser.objects.filter(role='student', is_active=True, grade=grade)
        .exclude(class_num__isnull=True).exclude(class_num='')
        .values_list('class_num', flat=True)
    )


def _normalize_audience(actor, raw_rules):
    normalized = []
    seen = set()
    for raw in raw_rules:
        scope_type = raw['scope_type']
        grade = raw.get('grade', '') or ''
        class_num = raw.get('class_num', '') or ''
        if scope_type == AUDIENCE_ALL_SCHOOL:
            if not is_platform_admin(actor):
                raise AIQuizServiceError(
                    '普通教师不能发布到全校', code='quiz_scope_forbidden', status_code=403,
                )
            grade = ''
            class_num = ''
        else:
            try:
                grade = normalize_grade(grade)
                require_teacher_grade(actor, grade)
            except TeacherScopeError as exc:
                raise AIQuizServiceError(
                    exc.message, code='quiz_scope_forbidden', status_code=403,
                ) from exc
            except Exception as exc:
                raise AIQuizServiceError('发布年级无效', code='invalid_grade') from exc
            if scope_type == AUDIENCE_GRADE_ALL:
                class_num = ''
            elif scope_type == AUDIENCE_CLASS:
                try:
                    class_num = normalize_student_identifier(class_num, label='班级')
                except Exception as exc:
                    raise AIQuizServiceError('班级格式无效', code='invalid_class') from exc
                if class_num not in _known_classes(grade):
                    raise AIQuizServiceError(
                        f'{grade}不存在启用的{class_num}班学生', code='unknown_class',
                    )
        key = (scope_type, grade, class_num)
        if key in seen:
            raise AIQuizServiceError('发布范围不能重复', code='duplicate_audience')
        seen.add(key)
        normalized.append({
            'scope_type': scope_type,
            'grade': grade,
            'class_num': class_num,
            'is_active': raw.get('is_active', True),
        })
    return normalized


def _replace_audience(session, actor, raw_rules):
    rules = _normalize_audience(actor, raw_rules)
    session.audience_rules.all().delete()
    AIQuizAudience.objects.bulk_create([
        AIQuizAudience(session=session, configured_by=actor, **rule)
        for rule in rules
    ])


def _replace_programming_items(session, resolved_items):
    session.programming_items.all().delete()
    AIQuizProgrammingItem.objects.bulk_create([
        AIQuizProgrammingItem(session=session, **item) for item in resolved_items
    ])


def _apply_draft_values(session, actor, values):
    grade = _required_grade(actor, values.get('content_grade', session.content_grade))
    unit_ids = values.get(
        'choice_unit_ids', list(session.choice_units.values_list('pk', flat=True)),
    )
    programming_values = values.get('programming_items', _current_programming_values(session))
    units = _resolve_units(unit_ids, grade)
    programming_items = _resolve_programming_items(programming_values, grade)

    for field in (
        'title', 'choice_question_count', 'choice_difficulty_ratio',
        'choice_points', 'time_limit',
    ):
        if field in values:
            setattr(session, field, values[field])
    session.content_grade = grade
    try:
        session.full_clean()
    except ValidationError as exc:
        raise AIQuizServiceError(
            '小测配置校验失败', code='quiz_configuration_invalid',
            details=getattr(exc, 'message_dict', None),
        ) from exc
    session.save()
    session.choice_units.set(units)
    _replace_programming_items(session, programming_items)
    if 'audience' in values:
        _replace_audience(session, actor, values['audience'])


@_audit_failures('quiz_create')
@transaction.atomic
def create_quiz(*, actor, values, source_ip=None):
    grade = _required_grade(actor, values.get('content_grade'))
    session = AIQuizSession(
        title=values.get('title', ''),
        content_grade=grade,
        created_by=actor,
        choice_question_count=values.get('choice_question_count', 0),
        choice_difficulty_ratio=values.get('choice_difficulty_ratio', {}),
        choice_points=values.get('choice_points', Decimal('0')),
        time_limit=values.get('time_limit'),
    )
    session.save()
    _apply_draft_values(session, actor, values)
    _audit(
        event_type='quiz_create', outcome='success', actor=actor,
        object_id=session.pk, after=_summary(session), source_ip=source_ip,
    )
    return session


@_audit_failures('quiz_update')
@transaction.atomic
def update_quiz(*, actor, session_id, values, expected_version, source_ip=None):
    session = _locked_session(actor, session_id)
    _check_version(session, expected_version)
    if session.blueprint_version > 0:
        raise AIQuizServiceError(
            '小测首次发布后组卷内容已锁定，请复制后修改',
            code='quiz_locked', status_code=409,
        )
    before = _summary(session)
    _apply_draft_values(session, actor, values)
    session.management_version += 1
    session.save(update_fields=['management_version', 'updated_at'])
    _audit(
        event_type='quiz_update', outcome='success', actor=actor,
        object_id=session.pk, before=before, after=_summary(session), source_ip=source_ip,
    )
    return session


def _validate_and_build_blueprint(session, *, lock=False):
    units = _resolve_units(
        list(session.choice_units.values_list('pk', flat=True)),
        session.content_grade,
        lock=lock,
    )
    ratio = {
        difficulty: session.choice_difficulty_ratio.get(difficulty, 0)
        for difficulty, _label in AIChoiceQuestion.DIFFICULTY_CHOICES
    }
    if any(isinstance(count, bool) or not isinstance(count, int) or count < 0 for count in ratio.values()):
        raise AIQuizServiceError(
            '选择题难度题数必须是非负整数', code='quiz_pool_insufficient',
        )
    if session.choice_question_count == 0:
        if units or sum(ratio.values()) or session.choice_points != Decimal('0'):
            raise AIQuizServiceError(
                '不抽选择题时，选择题单元、难度题数和分值必须为空或为 0',
                code='quiz_points_invalid',
            )
    else:
        if not units or session.choice_points <= 0:
            raise AIQuizServiceError(
                '选择题部分需要选择小节并设置正分值', code='quiz_points_invalid',
            )
        if sum(ratio.values()) != session.choice_question_count:
            raise AIQuizServiceError(
                '选择题各难度题数之和必须等于抽题总数', code='quiz_pool_insufficient',
            )

    choice_queryset = AIChoiceQuestion.objects.select_related('unit').filter(
        unit__in=units,
        archived_at__isnull=True,
        unit__archived_at__isnull=True,
        unit__parent__archived_at__isnull=True,
    ).order_by('id')
    if lock:
        choice_queryset = choice_queryset.select_for_update()
    available = dict(
        choice_queryset.order_by().values('difficulty')
        .annotate(count=Count('id')).values_list('difficulty', 'count')
    )
    shortages = {
        difficulty: {'required': required, 'available': available.get(difficulty, 0)}
        for difficulty, required in ratio.items()
        if available.get(difficulty, 0) < required
    }
    if shortages:
        raise AIQuizServiceError(
            '选择题题池不足，请补充题目或调整难度题数',
            code='quiz_pool_insufficient', details=shortages,
        )

    programming_values = _current_programming_values(session)
    programming_items = _resolve_programming_items(
        programming_values, session.content_grade, lock=lock,
    )
    if session.choice_question_count == 0 and not programming_items:
        raise AIQuizServiceError(
            '小测至少需要包含一种题型', code='quiz_points_invalid',
        )
    programming_points = sum(
        (item['points'] for item in programming_items), Decimal('0'),
    )
    total_points = session.choice_points + programming_points
    if total_points != Decimal('100.0'):
        raise AIQuizServiceError(
            '小测总分必须严格等于 100 分',
            code='quiz_points_invalid',
            details={'total_points': format(total_points, '.1f')},
        )
    active_audience = list(session.audience_rules.filter(is_active=True))
    if not active_audience:
        raise AIQuizServiceError(
            '发布小测前至少需要设置一个可见范围', code='quiz_scope_forbidden',
        )

    choice_pool = [
        {
            'source_question_id': question.pk,
            'source_version': question.management_version,
            'unit_id': question.unit_id,
            'difficulty': question.difficulty,
            'category': question.category,
            'text': question.text,
            'options': {
                'A': question.option_a,
                'B': question.option_b,
                'C': question.option_c,
                'D': question.option_d,
            },
            'correct_source_option': question.answer,
            'explanation': question.explanation,
        }
        for question in choice_queryset
    ]
    blueprint_programming_items = []
    for item in programming_items:
        problem = item['problem']
        eligibility = programming_quiz_eligibility(problem)
        if not eligibility['usable']:
            raise AIQuizServiceError(
                f'编程题 {problem.problem_id} 当前不可用于组卷',
                code='invalid_programming_problem', details=eligibility['reasons'],
            )
        try:
            test_snapshot = build_test_snapshot(problem)
        except InvalidTestSnapshot as exc:
            raise AIQuizServiceError(
                f'编程题 {problem.problem_id} 测试点无效：{exc}',
                code='invalid_programming_problem',
            ) from exc
        blueprint_programming_items.append({
            'item_id': str(uuid.uuid4()),
            'source_problem_id': problem.problem_id,
            'source_management_version': problem.management_version,
            'position': item['position'],
            'points': format(item['points'], '.1f'),
            'title': problem.title,
            'description': problem.description,
            'template_code': problem.get_template_code(),
            'test_snapshot': test_snapshot,
            'test_snapshot_hash': snapshot_digest(test_snapshot),
        })

    blueprint = {
        'schema_version': 1,
        'session': {
            'title': session.title,
            'content_grade': session.content_grade,
            'time_limit': session.time_limit,
            'choice_question_count': session.choice_question_count,
            'choice_difficulty_ratio': ratio,
            'choice_points': format(session.choice_points, '.1f'),
        },
        'choice_pool': choice_pool,
        'programming_items': blueprint_programming_items,
    }
    return blueprint, {
        'choice_pool_count': len(choice_pool),
        'choice_available_by_difficulty': available,
        'choice_question_count': session.choice_question_count,
        'programming_question_count': len(programming_items),
        'choice_points': format(session.choice_points, '.1f'),
        'programming_points': format(programming_points, '.1f'),
        'total_points': format(total_points, '.1f'),
        'audience_count': len(active_audience),
    }


@transaction.atomic
def validate_quiz(*, actor, session_id, expected_version):
    session = _locked_session(actor, session_id)
    _check_version(session, expected_version)
    if session.blueprint_version > 0:
        if (
            not session.blueprint_json
            or blueprint_digest(session.blueprint_json) != session.blueprint_hash
        ):
            raise AIQuizServiceError(
                '发布蓝图校验失败', code='quiz_blueprint_invalid', status_code=409,
            )
        return {
            'valid': True,
            'management_version': session.management_version,
            'blueprint_version': session.blueprint_version,
            'blueprint_hash': session.blueprint_hash,
            'reuses_blueprint': True,
        }
    _blueprint, summary = _validate_and_build_blueprint(session, lock=True)
    return {
        'valid': True,
        'management_version': session.management_version,
        'blueprint_version': 0,
        'reuses_blueprint': False,
        **summary,
    }


@_audit_failures('quiz_publish')
@transaction.atomic
def publish_quiz(*, actor, session_id, expected_version, source_ip=None):
    session = _locked_session(actor, session_id)
    _check_version(session, expected_version)
    if session.status != AIQuizSession.STATUS_DRAFT or session.blueprint_version > 0:
        raise AIQuizServiceError(
            '只有未发布草稿可以首次发布', code='quiz_locked', status_code=409,
        )
    before = _summary(session)
    blueprint, _summary_data = _validate_and_build_blueprint(session, lock=True)
    now = timezone.now()
    session.blueprint_version = 1
    session.blueprint_json = blueprint
    session.blueprint_hash = blueprint_digest(blueprint)
    session.status = AIQuizSession.STATUS_OPEN
    session.opened_at = now
    session.closed_at = None
    session.management_version += 1
    session.full_clean()
    session.save(update_fields=[
        'blueprint_version', 'blueprint_json', 'blueprint_hash', 'status',
        'opened_at', 'closed_at', 'management_version', 'updated_at',
    ])
    _audit(
        event_type='quiz_publish', outcome='success', actor=actor,
        object_id=session.pk, before=before, after=_summary(session), source_ip=source_ip,
    )
    return session


@_audit_failures('quiz_audience_update')
@transaction.atomic
def update_quiz_audience(*, actor, session_id, audience, expected_version, source_ip=None):
    session = _locked_session(actor, session_id)
    _check_version(session, expected_version)
    before = _summary(session)
    _replace_audience(session, actor, audience)
    session.management_version += 1
    session.save(update_fields=['management_version', 'updated_at'])
    _audit(
        event_type='quiz_audience_update', outcome='success', actor=actor,
        object_id=session.pk, before=before, after=_summary(session), source_ip=source_ip,
    )
    return session


@_audit_failures('quiz_close')
@transaction.atomic
def close_quiz(*, actor, session_id, expected_version, source_ip=None):
    session = _locked_session(actor, session_id)
    _check_version(session, expected_version)
    if session.status != AIQuizSession.STATUS_OPEN:
        raise AIQuizServiceError('只有开放中的小测可以关闭', code='quiz_not_open', status_code=409)
    before = _summary(session)
    session.status = AIQuizSession.STATUS_CLOSED
    session.closed_at = timezone.now()
    session.management_version += 1
    session.save(update_fields=['status', 'closed_at', 'management_version', 'updated_at'])
    _audit(
        event_type='quiz_close', outcome='success', actor=actor,
        object_id=session.pk, before=before, after=_summary(session), source_ip=source_ip,
    )
    transaction.on_commit(lambda: _settle_closed_session(session.pk))
    return session


def _settle_closed_session(session_id):
    try:
        from .settlement_services import settle_session_attempts
        settle_session_attempts(session_id, reason='closed')
    except Exception:
        logger.exception('AI quiz close settlement failed', extra={'quiz_session_id': session_id})


@_audit_failures('quiz_reopen')
@transaction.atomic
def reopen_quiz(*, actor, session_id, expected_version, source_ip=None):
    session = _locked_session(actor, session_id)
    _check_version(session, expected_version)
    if session.status != AIQuizSession.STATUS_CLOSED:
        raise AIQuizServiceError('只有已关闭小测可以重新开放', code='quiz_locked', status_code=409)
    if not session.blueprint_json or blueprint_digest(session.blueprint_json) != session.blueprint_hash:
        raise AIQuizServiceError('发布蓝图校验失败', code='quiz_blueprint_invalid', status_code=409)
    if not session.audience_rules.filter(is_active=True).exists():
        raise AIQuizServiceError(
            '重新开放前至少需要设置一个可见范围', code='quiz_scope_forbidden',
        )
    before = _summary(session)
    session.status = AIQuizSession.STATUS_OPEN
    session.opened_at = timezone.now()
    session.closed_at = None
    session.management_version += 1
    session.save(update_fields=[
        'status', 'opened_at', 'closed_at', 'management_version', 'updated_at',
    ])
    _audit(
        event_type='quiz_reopen', outcome='success', actor=actor,
        object_id=session.pk, before=before, after=_summary(session), source_ip=source_ip,
    )
    return session


@_audit_failures('quiz_copy')
@transaction.atomic
def copy_quiz(*, actor, session_id, title=None, source_ip=None):
    source = _locked_session(actor, session_id, include_archived=True)
    grade = _required_grade(actor, source.content_grade)
    copied = AIQuizSession.objects.create(
        title=(title or f'{source.title}（副本）').strip(),
        content_grade=grade,
        created_by=actor,
        choice_question_count=source.choice_question_count,
        choice_difficulty_ratio=source.choice_difficulty_ratio,
        choice_points=source.choice_points,
        time_limit=source.time_limit,
    )
    copied.choice_units.set(source.choice_units.all())
    AIQuizProgrammingItem.objects.bulk_create([
        AIQuizProgrammingItem(
            session=copied, problem=item.problem,
            position=item.position, points=item.points,
        )
        for item in source.programming_items.select_related('problem').all()
    ])
    copied_rules = [
        {
            'scope_type': rule.scope_type,
            'grade': rule.grade,
            'class_num': rule.class_num,
            'is_active': rule.is_active,
        }
        for rule in source.audience_rules.all()
    ]
    _replace_audience(copied, actor, copied_rules)
    _audit(
        event_type='quiz_copy', outcome='success', actor=actor,
        object_id=copied.pk, after=_summary(copied), source_ip=source_ip,
    )
    return copied


@_audit_failures('quiz_archive')
@transaction.atomic
def archive_quiz(*, actor, session_id, expected_version, source_ip=None):
    session = _locked_session(actor, session_id)
    _check_version(session, expected_version)
    before = _summary(session)
    session.archived_at = timezone.now()
    session.management_version += 1
    session.save(update_fields=['archived_at', 'management_version', 'updated_at'])
    _audit(
        event_type='quiz_archive', outcome='success', actor=actor,
        object_id=session.pk, before=before, after=_summary(session), source_ip=source_ip,
    )
    return session


@_audit_failures('quiz_delete')
@transaction.atomic
def delete_quiz(*, actor, session_id, expected_version, source_ip=None):
    session = _locked_session(actor, session_id, include_archived=True)
    _check_version(session, expected_version)
    before = _summary(session)
    attempts = AIQuizAttempt.objects.filter(session=session)
    attempt_count = attempts.count()
    submission_count = Submission.objects.filter(quiz_attempt__session=session).count()
    execution_count = ExecutionTask.objects.filter(quiz_attempt__session=session).count()

    # Submission and attempt foreign keys are protective, so remove all quiz
    # execution history before deleting the attempts and the quiz itself.
    Submission.objects.filter(quiz_attempt__session=session).delete()
    ExecutionTask.objects.filter(quiz_attempt__session=session).delete()
    attempts.delete()
    session_id_value = session.pk
    session.delete()
    result = {
        'deleted': True,
        'attempt_count': attempt_count,
        'submission_count': submission_count,
        'execution_count': execution_count,
    }
    _audit(
        event_type='quiz_delete', outcome='success', actor=actor,
        object_id=session_id_value, before=before, after=result,
        source_ip=source_ip,
    )
    return result
