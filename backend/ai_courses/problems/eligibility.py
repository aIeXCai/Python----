"""Quiz eligibility checks for programming problems."""


REASON_LABELS = {
    'problem_archived': '题目已归档',
    'unit_missing': '未归类到 AI 小节',
    'unit_archived': '所属单元已归档',
    'description_missing': '题目描述为空',
    'test_cases_missing': '没有可用测试点',
}


def cached_test_count(problem):
    if not hasattr(problem, '_quiz_test_count'):
        problem._quiz_test_count = problem.get_test_count()
    return problem._quiz_test_count


def programming_quiz_eligibility(problem):
    """Return a stable, UI-safe eligibility summary for future quiz assembly."""
    reason_codes = []
    if problem.archived_at is not None:
        reason_codes.append('problem_archived')
    if not problem.unit_id:
        reason_codes.append('unit_missing')
    elif problem.unit.is_effectively_archived:
        reason_codes.append('unit_archived')
    if not (problem.description or '').strip():
        reason_codes.append('description_missing')
    if cached_test_count(problem) <= 0:
        reason_codes.append('test_cases_missing')
    return {
        'usable': not reason_codes,
        'reasons': [
            {'code': code, 'label': REASON_LABELS[code]}
            for code in reason_codes
        ],
    }
