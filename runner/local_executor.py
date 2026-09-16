from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable, Mapping

import psutil

from .config import RunnerConfig
from .results import (
    ProcessResult,
    STATUS_RESOURCE_LIMITED,
    STATUS_RUNTIME_ERROR,
    STATUS_SUCCEEDED,
    STATUS_SYSTEM_ERROR,
    STATUS_TIMED_OUT,
)


POLL_SECONDS = 0.02
KILL_GRACE_SECONDS = 0.4
SENSITIVE_ENV_FRAGMENTS = (
    'SECRET', 'TOKEN', 'PASSWORD', 'API_KEY', 'DJANGO_', 'RUNNER_', 'DATABASE_', 'MYSQL_',
)


def _platform_spawn_kwargs(platform_name: str = os.name) -> dict[str, object]:
    if platform_name == 'nt':
        return {
            'creationflags': (
                getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
                | getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            ),
        }
    return {'start_new_session': True}


def _windows_taskkill_command(pid: int) -> list[str]:
    return ['taskkill', '/PID', str(pid), '/T', '/F']


def _bounded_number(value: object, fallback: float, minimum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum:
        return fallback
    return float(value)


def _student_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return the minimum cross-platform environment needed to launch Python."""
    source = os.environ if source is None else source
    allowed_names = {'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'TMP', 'TEMP', 'TMPDIR'}
    result = {
        name: value for name, value in source.items()
        if name.upper() in allowed_names
        and not any(fragment in name.upper() for fragment in SENSITIVE_ENV_FRAGMENTS)
    }
    result.update({
        'PYTHONIOENCODING': 'utf-8',
        'PYTHONUTF8': '1',
        'PYTHONDONTWRITEBYTECODE': '1',
        'PYTHONHASHSEED': '0',
    })
    return result


class _OutputBudget:
    def __init__(self, limit: int):
        self.limit = limit
        self.used = 0
        self.lock = threading.Lock()
        self.exceeded = threading.Event()

    def take(self, chunk: bytes) -> bytes:
        with self.lock:
            remaining = max(0, self.limit - self.used)
            accepted = chunk[:remaining]
            self.used += len(accepted)
            if len(accepted) < len(chunk):
                self.exceeded.set()
            return accepted


class _BoundedPipeReader(threading.Thread):
    def __init__(self, pipe: BinaryIO, budget: _OutputBudget):
        super().__init__(daemon=True)
        self.pipe = pipe
        self.budget = budget
        self.chunks: list[bytes] = []

    def run(self) -> None:
        try:
            while True:
                chunk = self.pipe.read(4096)
                if not chunk:
                    return
                accepted = self.budget.take(chunk)
                if accepted:
                    self.chunks.append(accepted)
                if self.budget.exceeded.is_set():
                    return
        except (OSError, ValueError):
            return
        finally:
            try:
                self.pipe.close()
            except OSError:
                pass

    def text(self) -> str:
        return b''.join(self.chunks).decode('utf-8', errors='replace')


class _PipeWriter(threading.Thread):
    def __init__(self, pipe: BinaryIO, data: bytes):
        super().__init__(daemon=True)
        self.pipe = pipe
        self.data = data

    def run(self) -> None:
        try:
            self.pipe.write(self.data)
            self.pipe.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass
        finally:
            try:
                self.pipe.close()
            except OSError:
                pass


class _ProcessTree:
    """Track and terminate a process tree on both Unix and Windows."""

    def __init__(self, process: subprocess.Popen[bytes]):
        self.process = process
        self.known: dict[int, psutil.Process] = {}
        self.sample()

    def sample(self) -> tuple[int, int]:
        processes: list[psutil.Process] = []
        try:
            root = psutil.Process(self.process.pid)
            processes = [root, *root.children(recursive=True)]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            processes = list(self.known.values())

        memory_bytes = 0
        live_pids = 0
        for item in processes:
            self.known[item.pid] = item
            try:
                if item.is_running() and item.status() != psutil.STATUS_ZOMBIE:
                    live_pids += 1
                    memory_bytes += item.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return memory_bytes, live_pids

    @staticmethod
    def _signal_processes(processes: list[psutil.Process], *, force: bool) -> None:
        for item in reversed(processes):
            try:
                item.kill() if force else item.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def terminate(self) -> None:
        self.sample()
        processes = list(self.known.values())

        if os.name == 'nt':
            # taskkill is the most reliable built-in Windows tree cleanup while
            # the root still exists. Arguments are never passed through a shell.
            try:
                subprocess.run(
                    _windows_taskkill_command(self.process.pid),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError):
                pass
        else:
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass

        self._signal_processes(processes, force=False)
        _gone, alive = psutil.wait_procs(processes, timeout=KILL_GRACE_SECONDS)

        if os.name != 'nt':
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        self._signal_processes(alive, force=True)
        psutil.wait_procs(alive, timeout=KILL_GRACE_SECONDS)

        try:
            self.process.wait(timeout=KILL_GRACE_SECONDS)
        except (subprocess.TimeoutExpired, OSError):
            try:
                self.process.kill()
                self.process.wait(timeout=KILL_GRACE_SECONDS)
            except (subprocess.SubprocessError, OSError):
                pass


@dataclass(frozen=True)
class _EffectiveLimits:
    wall_seconds: float
    memory_bytes: int
    pids: int
    output_bytes: int


class LocalProcessExecutor:
    def __init__(
        self,
        config: RunnerConfig,
        *,
        temp_root: Path | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.config = config
        self.temp_root = temp_root
        self.monotonic = monotonic
        self._active_lock = threading.Lock()
        self._active_trees: set[_ProcessTree] = set()

    def _limits(self, task_limits: Mapping[str, object], wall_seconds: float | None) -> _EffectiveLimits:
        task_wall = wall_seconds
        if task_wall is None:
            task_wall = _bounded_number(task_limits.get('wall_seconds'), 10.0, 0.05)
        else:
            task_wall = _bounded_number(task_wall, 10.0, 0.05)
        task_memory = int(_bounded_number(
            task_limits.get('memory_mb'), float(self.config.max_memory_mb), 1,
        ))
        task_pids = int(_bounded_number(task_limits.get('pids'), float(self.config.max_pids), 1))
        task_output = int(_bounded_number(
            task_limits.get('output_bytes'), float(self.config.max_output_bytes), 1,
        ))
        return _EffectiveLimits(
            wall_seconds=min(task_wall, self.config.max_task_seconds),
            memory_bytes=min(task_memory, self.config.max_memory_mb) * 1024 * 1024,
            pids=min(task_pids, self.config.max_pids),
            output_bytes=min(task_output, self.config.max_output_bytes),
        )

    def _spawn(self, source_path: Path, work_dir: Path) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            [self.config.python_executable, '-I', '-B', str(source_path)],
            cwd=str(work_dir),
            env=_student_environment(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            **_platform_spawn_kwargs(),
        )

    def execute(
        self,
        code: str,
        stdin: str = '',
        *,
        limits: Mapping[str, object] | None = None,
        wall_seconds: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> ProcessResult:
        limits = self._limits(limits or {}, wall_seconds)
        started = self.monotonic()
        process: subprocess.Popen[bytes] | None = None
        tree: _ProcessTree | None = None
        stdout_reader: _BoundedPipeReader | None = None
        stderr_reader: _BoundedPipeReader | None = None
        budget = _OutputBudget(limits.output_bytes)
        termination_reason = 'completed'
        status = STATUS_SYSTEM_ERROR

        try:
            with tempfile.TemporaryDirectory(
                prefix='python-local-runner-', dir=str(self.temp_root) if self.temp_root else None,
            ) as directory:
                work_dir = Path(directory)
                source_path = work_dir / 'main.py'
                source_path.write_text(code, encoding='utf-8')
                process = self._spawn(source_path, work_dir)
                if process.stdout is None or process.stderr is None or process.stdin is None:
                    raise RuntimeError('无法创建学生程序管道')
                tree = _ProcessTree(process)
                with self._active_lock:
                    self._active_trees.add(tree)

                stdout_reader = _BoundedPipeReader(process.stdout, budget)
                stderr_reader = _BoundedPipeReader(process.stderr, budget)
                writer = _PipeWriter(process.stdin, stdin.encode('utf-8'))
                stdout_reader.start()
                stderr_reader.start()
                writer.start()

                deadline = started + limits.wall_seconds
                while process.poll() is None:
                    if cancel_event is not None and cancel_event.is_set():
                        status, termination_reason = STATUS_SYSTEM_ERROR, 'runner_shutdown'
                        break
                    if budget.exceeded.is_set():
                        status, termination_reason = STATUS_RESOURCE_LIMITED, 'output_limit'
                        break
                    memory_bytes, live_pids = tree.sample()
                    if memory_bytes > limits.memory_bytes:
                        status, termination_reason = STATUS_RESOURCE_LIMITED, 'memory_limit'
                        break
                    if live_pids > limits.pids:
                        status, termination_reason = STATUS_RESOURCE_LIMITED, 'process_limit'
                        break
                    if self.monotonic() >= deadline:
                        status, termination_reason = STATUS_TIMED_OUT, 'wall_time_limit'
                        break
                    time.sleep(POLL_SECONDS)
                else:
                    if budget.exceeded.is_set():
                        status, termination_reason = STATUS_RESOURCE_LIMITED, 'output_limit'
                    else:
                        status = STATUS_SUCCEEDED if process.returncode == 0 else STATUS_RUNTIME_ERROR
                        termination_reason = 'completed' if process.returncode == 0 else 'nonzero_exit'

                # Kill background descendants even when the root process exits normally.
                tree.terminate()
                writer.join(timeout=1)
                stdout_reader.join(timeout=1)
                stderr_reader.join(timeout=1)
                if budget.exceeded.is_set() and status not in {
                    STATUS_TIMED_OUT, STATUS_RESOURCE_LIMITED, STATUS_SYSTEM_ERROR,
                }:
                    status, termination_reason = STATUS_RESOURCE_LIMITED, 'output_limit'
        except Exception as exc:
            status = STATUS_SYSTEM_ERROR
            termination_reason = 'runner_error'
            if tree is not None:
                tree.terminate()
            stderr_text = f'本机执行服务错误：{type(exc).__name__}'
            return ProcessResult(
                status=status,
                stdout=stdout_reader.text() if stdout_reader else '',
                stderr=stderr_text,
                execution_ms=max(0, int((self.monotonic() - started) * 1000)),
                termination_reason=termination_reason,
                output_truncated=budget.exceeded.is_set(),
                exit_code=process.returncode if process else None,
            )
        finally:
            if tree is not None:
                with self._active_lock:
                    self._active_trees.discard(tree)

        return ProcessResult(
            status=status,
            stdout=stdout_reader.text() if stdout_reader else '',
            stderr=stderr_reader.text() if stderr_reader else '',
            execution_ms=max(0, int((self.monotonic() - started) * 1000)),
            termination_reason=termination_reason,
            output_truncated=budget.exceeded.is_set(),
            exit_code=process.returncode if process else None,
        )

    def terminate_all(self) -> None:
        """Best-effort cleanup used by the controller during shutdown."""
        with self._active_lock:
            trees = list(self._active_trees)
        for tree in trees:
            tree.terminate()
