import hashlib
import json

from django.conf import settings


class InvalidTestSnapshot(ValueError):
    pass


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )


def snapshot_digest(value):
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def validate_test_snapshot(snapshot, *, expected_problem_id=None):
    """Validate a persisted snapshot before handing it to an untrusted-code runner."""
    if not isinstance(snapshot, dict) or snapshot.get('schema_version') != 1:
        raise InvalidTestSnapshot('测试点快照版本无效')
    problem_id = snapshot.get('problem_id')
    if not isinstance(problem_id, str) or not problem_id:
        raise InvalidTestSnapshot('测试点快照题目标识无效')
    if expected_problem_id is not None and problem_id != expected_problem_id:
        raise InvalidTestSnapshot('测试点快照与题目不匹配')
    cases = snapshot.get('cases')
    if not isinstance(cases, list) or not cases:
        raise InvalidTestSnapshot('测试点快照为空')
    if len(cases) > settings.EXECUTION_TEST_CASES_MAX:
        raise InvalidTestSnapshot('测试点快照数量超出系统上限')
    for index, case in enumerate(cases, 1):
        if (
            not isinstance(case, dict)
            or case.get('number') != index
            or not isinstance(case.get('input'), str)
            or not isinstance(case.get('output'), str)
        ):
            raise InvalidTestSnapshot(f'第 {index} 个测试点快照无效')
        if (
            len(case['input'].encode('utf-8')) > settings.EXECUTION_TEST_CASE_MAX_BYTES
            or len(case['output'].encode('utf-8')) > settings.EXECUTION_TEST_CASE_MAX_BYTES
        ):
            raise InvalidTestSnapshot(f'第 {index} 个测试点超出系统大小上限')
    return snapshot


def build_test_snapshot(problem):
    raw_cases = problem.get_test_cases()
    if not raw_cases:
        raise InvalidTestSnapshot('该题暂无可用测试点，请联系教师')
    if len(raw_cases) > settings.EXECUTION_TEST_CASES_MAX:
        raise InvalidTestSnapshot('该题测试点数量超出系统上限')

    cases = []
    for index, case in enumerate(raw_cases, 1):
        input_text = str(case.get('input', ''))
        output_text = str(case.get('output', ''))
        if (
            len(input_text.encode('utf-8')) > settings.EXECUTION_TEST_CASE_MAX_BYTES
            or len(output_text.encode('utf-8')) > settings.EXECUTION_TEST_CASE_MAX_BYTES
        ):
            raise InvalidTestSnapshot(f'第 {index} 个测试点超出系统大小上限')
        cases.append({
            'number': index,
            'input': input_text,
            'output': output_text,
        })

    return validate_test_snapshot({
        'schema_version': 1,
        'problem_id': problem.problem_id,
        'cases': cases,
    }, expected_problem_id=problem.problem_id)
