from __future__ import annotations

from dataclasses import dataclass


STATUS_SUCCEEDED = 'succeeded'
STATUS_RUNTIME_ERROR = 'runtime_error'
STATUS_TIMED_OUT = 'timed_out'
STATUS_RESOURCE_LIMITED = 'resource_limited'
STATUS_SYSTEM_ERROR = 'system_error'


@dataclass(frozen=True)
class ProcessResult:
    status: str
    stdout: str
    stderr: str
    execution_ms: int
    termination_reason: str
    output_truncated: bool = False
    exit_code: int | None = None

    def as_runner_payload(self) -> dict[str, object]:
        return {
            'status': self.status,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'execution_ms': self.execution_ms,
            'detail': {
                'termination_reason': self.termination_reason,
                'output_truncated': self.output_truncated,
            },
        }
