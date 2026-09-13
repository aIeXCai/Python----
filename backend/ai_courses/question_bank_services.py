"""Transactional services for the AI unit and choice-question bank."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from users.scopes import (
    TeacherScopeError, is_platform_admin, require_teacher_grade, scope_by_grade,
)

from .models import AIChoiceQuestion, AIUnit


class QuestionBankError(Exception):
    def __init__(self, message, *, code='invalid_request', status_code=400, current_version=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.current_version = current_version


def _scope_error(exc):
    status_code = 400 if exc.code == 'invalid_grade' else 403
    return QuestionBankError(exc.message, code=exc.code, status_code=status_code)


def _required_grade(actor, requested=None):
    try:
        grade = require_teacher_grade(actor, requested)
    except TeacherScopeError as exc:
        raise _scope_error(exc) from exc
    if not grade:
        raise QuestionBankError('请指定年级', code='grade_required')
    return grade


def _validation_error(exc):
    if hasattr(exc, 'message_dict'):
        message = '；'.join(
            f'{field}: {"、".join(messages)}'
            for field, messages in exc.message_dict.items()
        )
    else:
        message = '；'.join(exc.messages)
    return QuestionBankError(message, code='validation_error')


def scoped_units(actor, *, include_archived=False):
    queryset = scope_by_grade(
        AIUnit.objects.select_related('parent', 'created_by'), actor,
    )
    if not include_archived:
        queryset = queryset.filter(archived_at__isnull=True).filter(
            models_parent_active_filter(),
        )
    return queryset


def models_parent_active_filter():
    # Kept as a helper so all list entry points share effective-archive semantics.
    from django.db.models import Q
    return Q(parent__isnull=True) | Q(parent__archived_at__isnull=True)


def scoped_choice_questions(actor, *, include_archived=False):
    queryset = scope_by_grade(
        AIChoiceQuestion.objects.select_related('unit', 'unit__parent', 'created_by'),
        actor,
        'unit__grade',
    )
    if not include_archived:
        queryset = queryset.filter(
            archived_at__isnull=True,
            unit__archived_at__isnull=True,
            unit__parent__archived_at__isnull=True,
        )
    return queryset


def _get_unit(actor, unit_id, *, include_archived=False, lock=False):
    queryset = AIUnit.objects.select_related('parent')
    if lock:
        queryset = queryset.select_for_update()
    queryset = scope_by_grade(queryset, actor)
    if not include_archived:
        queryset = queryset.filter(archived_at__isnull=True).filter(
            models_parent_active_filter(),
        )
    try:
        return queryset.get(pk=unit_id)
    except AIUnit.DoesNotExist as exc:
        raise QuestionBankError('单元不存在', code='unit_not_found', status_code=404) from exc


def _get_question(actor, question_id, *, include_archived=False, lock=False):
    queryset = AIChoiceQuestion.objects.select_related('unit', 'unit__parent')
    if lock:
        queryset = queryset.select_for_update()
    queryset = scope_by_grade(queryset, actor, 'unit__grade')
    if not include_archived:
        queryset = queryset.filter(
            archived_at__isnull=True,
            unit__archived_at__isnull=True,
            unit__parent__archived_at__isnull=True,
        )
    try:
        return queryset.get(pk=question_id)
    except AIChoiceQuestion.DoesNotExist as exc:
        raise QuestionBankError('选择题不存在', code='choice_question_not_found', status_code=404) from exc


def _parent_for_write(actor, parent_id, grade):
    if parent_id in (None, ''):
        return None
    parent = _get_unit(actor, parent_id)
    if parent.parent_id is not None or parent.grade != grade:
        raise QuestionBankError(
            '所属大单元无效', code='invalid_parent', status_code=400,
        )
    return parent


def _assert_unique_unit_name(*, unit=None, grade, parent, name):
    queryset = AIUnit.objects.select_for_update().filter(
        grade=grade, parent=parent, name=name,
    )
    if unit is not None:
        queryset = queryset.exclude(pk=unit.pk)
    if queryset.exists():
        raise QuestionBankError(
            f'同年级同层级已存在同名单元“{name}”',
            code='duplicate_unit_name', status_code=409,
        )


@transaction.atomic
def create_unit(*, actor, values):
    grade = _required_grade(actor, values.get('grade'))
    parent = _parent_for_write(actor, values.get('parent'), grade)
    name = (values.get('name') or '').strip()
    display_name = (values.get('display_name') or name).strip()
    _assert_unique_unit_name(grade=grade, parent=parent, name=name)
    unit = AIUnit(
        grade=grade,
        parent=parent,
        name=name,
        display_name=display_name,
        order=values.get('order', 0),
        created_by=actor,
    )
    try:
        unit.full_clean()
        unit.save()
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    except IntegrityError as exc:
        raise QuestionBankError(
            '同年级同层级已存在同名单元',
            code='duplicate_unit_name', status_code=409,
        ) from exc
    return unit


@transaction.atomic
def update_unit(*, actor, unit_id, values):
    unit = _get_unit(actor, unit_id, include_archived=True, lock=True)
    if unit.archived_at:
        raise QuestionBankError('已归档单元请先恢复', code='unit_archived', status_code=409)
    grade = _required_grade(actor, values.get('grade', unit.grade))
    if grade != unit.grade:
        raise QuestionBankError('单元年级不可修改', code='unit_grade_immutable', status_code=409)
    parent_value = values.get('parent', unit.parent_id)
    parent = _parent_for_write(actor, parent_value, grade)
    if unit.sections.exists() and parent is not None:
        raise QuestionBankError(
            '已包含小节的大单元不能移到其他单元下',
            code='unit_has_sections', status_code=409,
        )
    if parent is None and unit.parent_id is not None and (
        unit.choice_questions.exists() or unit.programming_problems.exists()
    ):
        raise QuestionBankError(
            '已包含题目的小节不能改为大单元',
            code='unit_has_questions', status_code=409,
        )
    name = (values.get('name', unit.name) or '').strip()
    _assert_unique_unit_name(unit=unit, grade=grade, parent=parent, name=name)
    unit.parent = parent
    unit.name = name
    unit.display_name = (values.get('display_name', unit.display_name) or '').strip()
    unit.order = values.get('order', unit.order)
    try:
        unit.full_clean()
        unit.save(update_fields=['parent', 'name', 'display_name', 'order', 'updated_at'])
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    except IntegrityError as exc:
        raise QuestionBankError(
            '同年级同层级已存在同名单元',
            code='duplicate_unit_name', status_code=409,
        ) from exc
    return unit


@transaction.atomic
def archive_unit(*, actor, unit_id):
    unit = _get_unit(actor, unit_id, include_archived=True, lock=True)
    if unit.archived_at is None:
        unit.archived_at = timezone.now()
        unit.save(update_fields=['archived_at', 'updated_at'])
    return unit


@transaction.atomic
def delete_empty_unit(*, actor, unit_id):
    """Permanently delete a unit only when no content depends on it."""
    unit = _get_unit(actor, unit_id, include_archived=True, lock=True)
    blockers = []
    if unit.sections.exists():
        blockers.append('小节')
    if unit.choice_questions.exists():
        blockers.append('选择题')
    if unit.programming_problems.exists():
        blockers.append('编程题')
    if unit.quiz_sessions.exists():
        blockers.append('小测')
    if blockers:
        raise QuestionBankError(
            f'该单元仍关联{"、".join(blockers)}，只能归档，不能永久删除',
            code='unit_not_empty', status_code=409,
        )
    unit.delete()


@transaction.atomic
def restore_unit(*, actor, unit_id):
    unit = _get_unit(actor, unit_id, include_archived=True, lock=True)
    if unit.parent_id and unit.parent.archived_at:
        raise QuestionBankError(
            '请先恢复所属大单元', code='parent_unit_archived', status_code=409,
        )
    if unit.archived_at is not None:
        unit.archived_at = None
        unit.save(update_fields=['archived_at', 'updated_at'])
    return unit


QUESTION_FIELDS = (
    'unit', 'difficulty', 'category', 'text', 'option_a', 'option_b',
    'option_c', 'option_d', 'answer', 'explanation',
)


def _choice_values(actor, values, *, existing=None):
    unit_id = values.get('unit', existing.unit_id if existing else None)
    if not unit_id:
        raise QuestionBankError('请选择所属小节', code='unit_required')
    unit = _get_unit(actor, unit_id)
    _required_grade(actor, unit.grade)
    if unit.parent_id is None:
        raise QuestionBankError(
            '选择题必须归入小节', code='leaf_unit_required', status_code=400,
        )
    result = {}
    for field in QUESTION_FIELDS:
        if field == 'unit':
            result[field] = unit
        elif field in values:
            result[field] = values[field]
        elif existing is not None:
            result[field] = getattr(existing, field)
    return result


@transaction.atomic
def create_choice_question(*, actor, values):
    question = AIChoiceQuestion(
        **_choice_values(actor, values), created_by=actor,
    )
    try:
        question.full_clean()
        question.save()
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    return question


@transaction.atomic
def copy_choice_question(*, actor, question_id, unit_id=None):
    source = _get_question(actor, question_id)
    values = {field: getattr(source, field) for field in QUESTION_FIELDS if field != 'unit'}
    values['unit'] = unit_id or source.unit_id
    return create_choice_question(actor=actor, values=values)


def _check_question_version(question, expected_version):
    if question.management_version != expected_version:
        raise QuestionBankError(
            '选择题已被其他教师更新，请重新加载后再保存',
            code='version_conflict', status_code=409,
            current_version=question.management_version,
        )


def _check_question_owner(actor, question):
    if is_platform_admin(actor) or question.created_by_id == actor.pk:
        return
    raise QuestionBankError(
        '共享选择题内容只能由创建教师或超级管理员编辑',
        code='content_owner_required', status_code=403,
    )


@transaction.atomic
def update_choice_question(*, actor, question_id, values, expected_version):
    question = _get_question(actor, question_id, include_archived=True, lock=True)
    _check_question_owner(actor, question)
    if question.archived_at:
        raise QuestionBankError(
            '已归档选择题请先恢复', code='choice_question_archived', status_code=409,
        )
    _check_question_version(question, expected_version)
    prepared = _choice_values(actor, values, existing=question)
    for field, value in prepared.items():
        setattr(question, field, value)
    question.management_version += 1
    try:
        question.full_clean()
        question.save(update_fields=[*QUESTION_FIELDS, 'management_version', 'updated_at'])
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    return question


@transaction.atomic
def archive_choice_question(*, actor, question_id, expected_version):
    question = _get_question(actor, question_id, include_archived=True, lock=True)
    _check_question_owner(actor, question)
    _check_question_version(question, expected_version)
    if question.archived_at is None:
        question.archived_at = timezone.now()
        question.management_version += 1
        question.save(update_fields=['archived_at', 'management_version', 'updated_at'])
    return question


@transaction.atomic
def delete_choice_question(*, actor, question_id, expected_version):
    question = _get_question(actor, question_id, include_archived=True, lock=True)
    _check_question_owner(actor, question)
    _check_question_version(question, expected_version)
    question.delete()


@transaction.atomic
def bulk_delete_choice_questions(*, actor, items):
    versions = {item['id']: item['expected_version'] for item in items}
    questions = list(
        scoped_choice_questions(actor, include_archived=True)
        .select_for_update()
        .filter(pk__in=versions)
        .order_by('pk')
    )
    if len(questions) != len(versions):
        raise QuestionBankError(
            '部分选择题不存在或不在你的管理范围内',
            code='choice_question_not_found', status_code=404,
        )
    for question in questions:
        _check_question_owner(actor, question)
        _check_question_version(question, versions[question.pk])
    deleted_count = len(questions)
    AIChoiceQuestion.objects.filter(pk__in=versions).delete()
    return deleted_count


@transaction.atomic
def restore_choice_question(*, actor, question_id, expected_version):
    question = _get_question(actor, question_id, include_archived=True, lock=True)
    _check_question_owner(actor, question)
    _check_question_version(question, expected_version)
    if question.unit.is_effectively_archived:
        raise QuestionBankError(
            '请先恢复选择题所属单元', code='unit_archived', status_code=409,
        )
    if question.archived_at is not None:
        question.archived_at = None
        question.management_version += 1
        question.save(update_fields=['archived_at', 'management_version', 'updated_at'])
    return question


def _normalize_import_question(raw, index):
    if not isinstance(raw, dict):
        raise QuestionBankError(
            f'第 {index} 题必须是 JSON 对象', code='invalid_import_question',
        )
    values = dict(raw)
    if 'options' in raw:
        options = raw.get('options')
        if not isinstance(options, list):
            raise QuestionBankError(
                f'第 {index} 题 options 必须是数组', code='invalid_import_options',
            )
        mapped = {}
        for option in options:
            if isinstance(option, dict):
                key = str(option.get('key', '')).upper()
                if key in ('A', 'B', 'C', 'D'):
                    mapped[key] = option.get('text', '')
        for letter in ('A', 'B', 'C', 'D'):
            values[f'option_{letter.lower()}'] = mapped.get(letter, '')
    values.pop('options', None)
    allowed = set(QUESTION_FIELDS) - {'unit'}
    return {key: value for key, value in values.items() if key in allowed}


def resolve_import_unit(*, actor, unit_id=None, unit_name='', grade=None):
    if unit_id:
        unit = _get_unit(actor, unit_id)
    else:
        requested_grade = _required_grade(actor, grade)
        queryset = scoped_units(actor).filter(
            grade=requested_grade,
            parent__isnull=False,
            name=(unit_name or '').strip(),
        )
        try:
            unit = queryset.get()
        except AIUnit.DoesNotExist as exc:
            raise QuestionBankError(
                '导入目标小节不存在，请先在 AI 单元管理中创建',
                code='unit_not_found', status_code=404,
            ) from exc
        except AIUnit.MultipleObjectsReturned as exc:
            raise QuestionBankError(
                '小节名称不唯一，请使用 unit_id 指定导入目标',
                code='ambiguous_unit', status_code=409,
            ) from exc
    if unit.parent_id is None:
        raise QuestionBankError(
            '选择题必须导入到小节', code='leaf_unit_required',
        )
    return unit


@transaction.atomic
def import_choice_questions(*, actor, unit_id, questions):
    unit = _get_unit(actor, unit_id)
    _required_grade(actor, unit.grade)
    if unit.parent_id is None:
        raise QuestionBankError(
            '选择题必须导入到小节', code='leaf_unit_required',
        )
    if not questions:
        raise QuestionBankError('题目列表不能为空', code='questions_required')
    prepared = []
    for index, raw in enumerate(questions, 1):
        values = _normalize_import_question(raw, index)
        question = AIChoiceQuestion(unit=unit, created_by=actor, **values)
        try:
            question.full_clean()
        except ValidationError as exc:
            error = _validation_error(exc)
            raise QuestionBankError(
                f'第 {index} 题：{error.message}', code='invalid_import_question',
            ) from exc
        prepared.append(question)
    # Save after the whole batch validates so IDs are returned consistently on
    # both SQLite and the production MySQL backend while the transaction stays atomic.
    for question in prepared:
        question.save()
    return prepared
