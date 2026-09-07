"""Transactional management services for AI problem content and publication."""

import hashlib
from functools import wraps

from django.db import transaction
from django.utils import timezone

from users.grade_levels import CANONICAL_GRADES, normalize_grade, normalize_student_identifier
from users.models import CustomUser
from users.scopes import TeacherScopeError, is_platform_admin, teacher_grade

from .models import (
    AUDIENCE_ALL_SCHOOL,
    AUDIENCE_CLASS,
    AUDIENCE_GRADE_ALL,
    Problem,
    ProblemAudience,
    ProblemManagementAudit,
)


class ProblemManagementError(Exception):
    def __init__(self, message, *, code='invalid_request', status_code=400, current_version=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.current_version = current_version


def _content_hash(value):
    return hashlib.sha256((value or '').encode('utf-8')).hexdigest()[:16]


def _summary(problem):
    active = list(
        problem.audience_rules.filter(is_active=True)
        .order_by('scope_type', 'grade', 'class_num')
        .values('scope_type', 'grade', 'class_num')
    )
    return {
        'title': problem.title,
        'description_hash': _content_hash(problem.description),
        'template_hash': _content_hash(problem.template_code),
        'difficulty': problem.difficulty,
        'grade_tag': problem.grade_tag,
        'publishing_suspended': problem.publishing_suspended,
        'archived': problem.archived_at is not None,
        'management_version': problem.management_version,
        'active_scopes': active,
    }


def _audit(*, event_type, outcome, actor, problem_id='', reason_code='', before=None, after=None, source_ip=None):
    return ProblemManagementAudit.objects.create(
        event_type=event_type,
        outcome=outcome,
        actor_user_id=getattr(actor, 'pk', None),
        problem_id=problem_id,
        reason_code=reason_code,
        before_summary=before or {},
        after_summary=after or {},
        source_ip=source_ip,
    )


def _audit_failures(event_type):
    """Persist rejected/conflicting attempts after the business transaction rolls back."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ProblemManagementError as exc:
                outcome = 'conflict' if exc.status_code == 409 else (
                    'denied' if exc.status_code == 403 else 'failed'
                )
                _audit(
                    event_type=event_type,
                    outcome=outcome,
                    actor=kwargs.get('actor'),
                    problem_id=kwargs.get('problem_id', ''),
                    reason_code=exc.code,
                    source_ip=kwargs.get('source_ip'),
                )
                raise
        return wrapper
    return decorator


def _locked_problem(problem_id, *, include_archived=False):
    queryset = Problem.objects.select_for_update().prefetch_related('audience_rules')
    if not include_archived:
        queryset = queryset.filter(archived_at__isnull=True)
    try:
        return queryset.get(problem_id=problem_id, course='ai')
    except Problem.DoesNotExist as exc:
        raise ProblemManagementError('题目不存在', code='problem_not_found', status_code=404) from exc


def _check_version(problem, expected_version, *, actor=None, event_type=None, source_ip=None):
    if problem.management_version == expected_version:
        return
    raise ProblemManagementError(
        '题目已被其他教师更新，请重新加载后再保存',
        code='version_conflict',
        status_code=409,
        current_version=problem.management_version,
    )


def publication_data(problem, actor):
    rules = list(problem.audience_rules.all().order_by('scope_type', 'grade', 'class_num'))
    all_school = next((rule for rule in rules if rule.scope_type == AUDIENCE_ALL_SCHOOL), None)
    if is_platform_admin(actor):
        grades = CANONICAL_GRADES
    else:
        grades = (teacher_grade(actor),)

    scopes = []
    for grade in grades:
        grade_all = next(
            (rule for rule in rules if rule.scope_type == AUDIENCE_GRADE_ALL and rule.grade == grade),
            None,
        )
        classes = [
            rule.class_num for rule in rules
            if rule.scope_type == AUDIENCE_CLASS and rule.grade == grade and rule.is_active
        ]
        any_active = bool(grade_all and grade_all.is_active) or bool(classes)
        draft_classes = [
            rule.class_num for rule in rules
            if rule.scope_type == AUDIENCE_CLASS and rule.grade == grade
        ]
        draft_all_classes = bool(grade_all and (grade_all.is_active or not any_active))
        scopes.append({
            'grade': grade,
            'visible': any_active,
            'all_classes': draft_all_classes,
            'classes': [] if draft_all_classes else draft_classes,
        })

    return {
        'problem_id': problem.problem_id,
        'management_version': problem.management_version,
        'publishing_suspended': problem.publishing_suspended,
        'all_school': bool(all_school and all_school.is_active),
        'scopes': scopes,
    }


def publication_label(problem, actor):
    if problem.archived_at:
        return '已归档'
    if problem.publishing_suspended:
        return '已暂停'
    data = publication_data(problem, actor)
    if data['all_school']:
        return '全校可见'
    visible = [scope for scope in data['scopes'] if scope['visible']]
    if not visible:
        return '不可见'
    parts = []
    for scope in visible:
        if scope['all_classes']:
            parts.append(f"{scope['grade']}全年级")
        else:
            parts.append(f"{scope['grade']}" + '、'.join(scope['classes']) + '班')
    return '；'.join(parts)


@_audit_failures('content_edit')
@transaction.atomic
def edit_problem_content(*, actor, problem_id, values, expected_version, source_ip=None):
    problem = _locked_problem(problem_id)
    if not is_platform_admin(actor) and problem.created_by_id != actor.pk:
        raise ProblemManagementError(
            '共享题目内容只能由创建教师或超级管理员编辑',
            code='content_owner_required', status_code=403,
        )
    _check_version(
        problem, expected_version, actor=actor,
        event_type='content_edit', source_ip=source_ip,
    )
    before = _summary(problem)
    changed = False
    for field in ('title', 'description', 'difficulty', 'grade_tag', 'template_code'):
        if field in values and getattr(problem, field) != values[field]:
            setattr(problem, field, values[field])
            changed = True
    if changed:
        problem.management_version += 1
        problem.save(update_fields=[
            'title', 'description', 'difficulty', 'grade_tag', 'template_code',
            'management_version', 'updated_at',
        ])
    after = _summary(problem)
    _audit(
        event_type='content_edit', outcome='success', actor=actor,
        problem_id=problem.problem_id, before=before, after=after, source_ip=source_ip,
    )
    return problem


def _known_classes(grade):
    return set(
        CustomUser.objects.filter(role='student', grade=grade)
        .exclude(class_num__isnull=True).exclude(class_num='')
        .values_list('class_num', flat=True)
    )


def _normalize_classes(raw_classes, grade):
    classes = []
    for value in raw_classes:
        try:
            normalized = normalize_student_identifier(value, label='班级')
        except Exception as exc:
            raise ProblemManagementError(
                '班级格式无效', code='invalid_class', status_code=400,
            ) from exc
        if normalized not in classes:
            classes.append(normalized)
    unknown = set(classes) - _known_classes(grade)
    if unknown:
        raise ProblemManagementError(
            '包含该年级不存在的班级：' + '、'.join(sorted(unknown)),
            code='unknown_class', status_code=400,
        )
    return classes


def _upsert_rule(problem, *, scope_type, grade='', class_num='', active, actor):
    rule, _ = ProblemAudience.objects.update_or_create(
        problem=problem,
        scope_type=scope_type,
        grade=grade,
        class_num=class_num,
        defaults={'is_active': active, 'configured_by': actor},
    )
    return rule


def _apply_grade_scope(problem, *, grade, visible, all_classes, classes, actor):
    rules = ProblemAudience.objects.filter(problem=problem, grade=grade)
    if not visible:
        rules.update(is_active=False, configured_by=actor, updated_at=timezone.now())
        return
    if all_classes:
        rules.filter(scope_type=AUDIENCE_CLASS).delete()
        _upsert_rule(
            problem, scope_type=AUDIENCE_GRADE_ALL, grade=grade,
            active=True, actor=actor,
        )
        return
    normalized = _normalize_classes(classes, grade)
    if not normalized:
        raise ProblemManagementError(
            '指定范围至少需要选择一个班级',
            code='publication_scope_required', status_code=400,
        )
    rules.filter(scope_type=AUDIENCE_GRADE_ALL).delete()
    rules.filter(scope_type=AUDIENCE_CLASS).exclude(class_num__in=normalized).delete()
    for class_num in normalized:
        _upsert_rule(
            problem, scope_type=AUDIENCE_CLASS, grade=grade,
            class_num=class_num, active=True, actor=actor,
        )


@_audit_failures('scope_update')
@transaction.atomic
def update_problem_audience(*, actor, problem_id, values, expected_version, source_ip=None):
    problem = _locked_problem(problem_id)
    _check_version(
        problem, expected_version, actor=actor,
        event_type='scope_update', source_ip=source_ip,
    )
    before = _summary(problem)
    all_school_rule = ProblemAudience.objects.filter(
        problem=problem, scope_type=AUDIENCE_ALL_SCHOOL,
        grade='', class_num='', is_active=True,
    ).first()

    if is_platform_admin(actor):
        all_school = values.get('all_school', False)
        suspended = values.get('publishing_suspended', problem.publishing_suspended)
        scopes = values.get('scopes', [])
        if not suspended and not all_school and not any(scope.get('visible', True) for scope in scopes):
            raise ProblemManagementError(
                '发布题目时至少选择一个年级或班级',
                code='publication_scope_required', status_code=400,
            )
        _upsert_rule(
            problem, scope_type=AUDIENCE_ALL_SCHOOL,
            active=all_school, actor=actor,
        )
        if not all_school:
            scopes_by_grade = {normalize_grade(scope['grade']): scope for scope in scopes}
            for grade in CANONICAL_GRADES:
                scope = scopes_by_grade.get(grade)
                if not scope:
                    _apply_grade_scope(
                        problem, grade=grade, visible=False,
                        all_classes=False, classes=[], actor=actor,
                    )
                    continue
                _apply_grade_scope(
                    problem,
                    grade=grade,
                    visible=scope.get('visible', True),
                    all_classes=scope.get('all_classes', False),
                    classes=scope.get('classes', []),
                    actor=actor,
                )
        problem.publishing_suspended = suspended
    else:
        try:
            grade = teacher_grade(actor)
        except TeacherScopeError as exc:
            raise ProblemManagementError(
                exc.message, code=exc.code, status_code=403,
            ) from exc
        if all_school_rule:
            raise ProblemManagementError(
                '当前题目由超级管理员设置为全校可见，请联系超级管理员调整',
                code='all_school_managed_by_admin', status_code=409,
            )
        _apply_grade_scope(
            problem,
            grade=grade,
            visible=values['visible'],
            all_classes=values.get('all_classes', False),
            classes=values.get('classes', []),
            actor=actor,
        )

    problem.management_version += 1
    problem.save(update_fields=['publishing_suspended', 'management_version', 'updated_at'])
    after = _summary(problem)
    event_type = 'scope_update'
    if before['publishing_suspended'] != after['publishing_suspended']:
        event_type = 'global_suspend' if after['publishing_suspended'] else 'global_resume'
    _audit(
        event_type=event_type, outcome='success', actor=actor,
        problem_id=problem.problem_id, before=before, after=after, source_ip=source_ip,
    )
    return problem


@_audit_failures('archive')
@transaction.atomic
def archive_problem(*, actor, problem_id, expected_version, source_ip=None):
    if not is_platform_admin(actor):
        raise ProblemManagementError('只有超级管理员可以归档题目', code='superuser_required', status_code=403)
    problem = _locked_problem(problem_id, include_archived=True)
    _check_version(problem, expected_version, actor=actor, event_type='archive', source_ip=source_ip)
    if problem.archived_at:
        return problem
    before = _summary(problem)
    problem.archived_at = timezone.now()
    problem.management_version += 1
    problem.save(update_fields=['archived_at', 'management_version', 'updated_at'])
    _audit(
        event_type='archive', outcome='success', actor=actor,
        problem_id=problem.problem_id, before=before, after=_summary(problem), source_ip=source_ip,
    )
    return problem


@_audit_failures('restore')
@transaction.atomic
def restore_problem(*, actor, problem_id, expected_version, source_ip=None):
    if not is_platform_admin(actor):
        raise ProblemManagementError('只有超级管理员可以恢复题目', code='superuser_required', status_code=403)
    problem = _locked_problem(problem_id, include_archived=True)
    _check_version(problem, expected_version, actor=actor, event_type='restore', source_ip=source_ip)
    if not problem.archived_at:
        return problem
    before = _summary(problem)
    problem.archived_at = None
    problem.publishing_suspended = True
    problem.management_version += 1
    problem.save(update_fields=[
        'archived_at', 'publishing_suspended', 'management_version', 'updated_at',
    ])
    _audit(
        event_type='restore', outcome='success', actor=actor,
        problem_id=problem.problem_id, before=before, after=_summary(problem), source_ip=source_ip,
    )
    return problem
