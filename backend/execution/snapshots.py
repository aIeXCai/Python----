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

    return {
        'schema_version': 1,
        'problem_id': problem.problem_id,
        'cases': cases,
    }
