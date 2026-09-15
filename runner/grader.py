from __future__ import annotations

import time
from typing import Callable, Mapping

from .local_executor import LocalProcessExecutor
from .results import (
    STATUS_RESOURCE_LIMITED,
    STATUS_RUNTIME_ERROR,
    STATUS_SUCCEEDED,
    STATUS_SYSTEM_ERROR,
    STATUS_TIMED_OUT,
)


STATUS_WRONG_ANSWER = 'wrong_answer'
CASE_STATUS_BY_PROCESS_STATUS = {
    STATUS_RUNTIME_ERROR: STATUS_RUNTIME_ERROR,
    STATUS_TIMED_OUT: STATUS_TIMED_OUT,
    STATUS_RESOURCE_LIMITED: STATUS_RESOURCE_LIMITED,
}
STATUS_PRIORITY = {
    STATUS_SUCCEEDED: 0,
    STATUS_WRONG_ANSWER: 1,
    STATUS_RUNTIME_ERROR: 2,
    STATUS_TIMED_OUT: 3,
    STATUS_RESOURCE_LIMITED: 4,
    STATUS_SYSTEM_ERROR: 5,
}


def _positive_number(value: object, fallback: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return fallback
    return float(value)


class TaskEvaluator:
    def __init__(
        self,
        executor: LocalProcessExecutor,
        *,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.executor = executor
        self.monotonic = monotonic

    def evaluate(self, envelope: Mapping[str, object], *, cancel_event=None) -> dict[str, object]:
        task_type = envelope.get('task_type')
        if task_type == 'run':
            return self._run(envelope, cancel_event=cancel_event)
        if task_type == 'grade':
            return self._grade(envelope, cancel_event=cancel_event)
        return self._system_error('invalid_task_type')

    def _run(self, envelope: Mapping[str, object], *, cancel_event=None) -> dict[str, object]:
        code = envelope.get('code')
        stdin = envelope.get('stdin', '')
        limits = envelope.get('limits') or {}
        if not isinstance(code, str) or not isinstance(stdin, str) or not isinstance(limits, Mapping):
            return self._system_error('invalid_task_envelope')
        wall_seconds = _positive_number(limits.get('wall_seconds'), 10.0)
        result = self.executor.execute(
            code, stdin, limits=limits, wall_seconds=wall_seconds, cancel_event=cancel_event,
        )
        return result.as_runner_payload()

    def _grade(self, envelope: Mapping[str, object], *, cancel_event=None) -> dict[str, object]:
        code = envelope.get('code')
        snapshot = envelope.get('test_snapshot')
        limits = envelope.get('limits') or {}
        if (
            not isinstance(code, str)
            or not isinstance(snapshot, Mapping)
            or not isinstance(limits, Mapping)
        ):
            return self._system_error('invalid_task_envelope')
        cases = snapshot.get('cases')
        if not isinstance(cases, list) or not cases:
            return self._system_error('invalid_test_snapshot')

        started = self.monotonic()
        task_seconds = min(
            _positive_number(limits.get('task_wall_seconds'), 30.0),
            float(self.executor.config.max_task_seconds),
        )
        case_seconds = min(
            _positive_number(limits.get('case_wall_seconds'), 5.0),
            float(self.executor.config.max_case_seconds),
        )
        output_remaining = min(
            int(_positive_number(limits.get('output_bytes'), self.executor.config.max_output_bytes)),
            self.executor.config.max_output_bytes,
        )
        passed = 0
        tests: list[dict[str, object]] = []
        final_status = STATUS_SUCCEEDED
        termination_reason = 'completed'

        for raw_case in cases:
            elapsed = self.monotonic() - started
            remaining_seconds = task_seconds - elapsed
            if remaining_seconds <= 0:
                final_status = self._more_severe(final_status, STATUS_TIMED_OUT)
                termination_reason = 'task_wall_time_limit'
                break
            if output_remaining <= 0:
                final_status = self._more_severe(final_status, STATUS_RESOURCE_LIMITED)
                termination_reason = 'output_limit'
                break
            if not isinstance(raw_case, Mapping):
                return self._system_error('invalid_test_snapshot', started=started)
            number = raw_case.get('number')
            test_input = raw_case.get('input', '')
            expected = raw_case.get('output', '')
            if (
                not isinstance(number, int)
                or isinstance(number, bool)
                or not isinstance(test_input, str)
                or not isinstance(expected, str)
            ):
                return self._system_error('invalid_test_snapshot', started=started)

            case_limits = dict(limits)
            case_limits['output_bytes'] = output_remaining
            result = self.executor.execute(
                code,
                test_input,
                limits=case_limits,
                wall_seconds=min(case_seconds, remaining_seconds),
                cancel_event=cancel_event,
            )
            output_used = len(result.stdout.encode('utf-8')) + len(result.stderr.encode('utf-8'))
            output_remaining = max(0, output_remaining - output_used)
            actual = result.stdout.strip()

            if result.status == STATUS_SYSTEM_ERROR:
                return self._system_error(
                    result.termination_reason, started=started, tests=tests,
                )
            if result.status == STATUS_SUCCEEDED:
                case_status = 'passed' if actual == expected else STATUS_WRONG_ANSWER
            else:
                case_status = CASE_STATUS_BY_PROCESS_STATUS.get(result.status, STATUS_RUNTIME_ERROR)
            if case_status == 'passed':
                passed += 1
            else:
                final_status = self._more_severe(final_status, case_status)
                termination_reason = result.termination_reason if result.status != STATUS_SUCCEEDED else 'wrong_answer'

            tests.append({
                'number': number,
                'status': case_status,
                'actual_output': actual,
                'stderr': result.stderr,
                'execution_ms': result.execution_ms,
            })
            if result.status in {STATUS_RESOURCE_LIMITED, STATUS_TIMED_OUT}:
                break

        execution_ms = max(0, int((self.monotonic() - started) * 1000))
        score = passed / len(cases) * 100
        if final_status == STATUS_SUCCEEDED and passed != len(cases):
            final_status = STATUS_WRONG_ANSWER
            termination_reason = 'incomplete_tests'
        return {
            'status': final_status,
            'stdout': '',
            'stderr': '',
            'execution_ms': execution_ms,
            'score': score,
            'detail': {
                'tests': tests,
                'termination_reason': termination_reason,
            },
        }

    @staticmethod
    def _more_severe(current: str, candidate: str) -> str:
        return candidate if STATUS_PRIORITY[candidate] > STATUS_PRIORITY[current] else current

    def _system_error(
        self,
        reason: str,
        *,
        started: float | None = None,
        tests: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        execution_ms = 0 if started is None else max(0, int((self.monotonic() - started) * 1000))
        return {
            'status': STATUS_SYSTEM_ERROR,
            'stdout': '',
            'stderr': '',
            'execution_ms': execution_ms,
            'score': None,
            'detail': {
                'tests': tests or [],
                'termination_reason': reason,
            },
        }
