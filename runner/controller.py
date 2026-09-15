from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from .api_client import RunnerApiClient, RunnerApiError
from .config import RunnerConfig
from .grader import TaskEvaluator
from .local_executor import LocalProcessExecutor


logger = logging.getLogger('local_runner')


class LocalRunnerController:
    def __init__(
        self,
        config: RunnerConfig,
        *,
        api_client: RunnerApiClient | None = None,
        executor: LocalProcessExecutor | None = None,
        evaluator: TaskEvaluator | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.config = config
        self.api = api_client or RunnerApiClient(config)
        self.executor = executor or LocalProcessExecutor(config)
        self.evaluator = evaluator or TaskEvaluator(self.executor)
        self.sleeper = sleeper
        self.stop_event = threading.Event()
        self._active_lock = threading.Lock()
        self._active_tasks: dict[str, threading.Event] = {}
        self._workers: list[threading.Thread] = []
        self._heartbeat_thread: threading.Thread | None = None

    @property
    def active_slots(self) -> int:
        with self._active_lock:
            return len(self._active_tasks)

    def request_stop(self) -> None:
        self.stop_event.set()

    def _safe_node_heartbeat(self, status: str = 'online', last_error: str = '') -> None:
        try:
            self.api.node_heartbeat(
                active_slots=self.active_slots, status=status, last_error=last_error,
            )
        except RunnerApiError as exc:
            logger.warning('Runner 节点心跳失败 code=%s status=%s', exc.code, exc.status_code)

    def _node_heartbeat_loop(self) -> None:
        while not self.stop_event.is_set():
            self._safe_node_heartbeat()
            self.stop_event.wait(self.config.heartbeat_seconds)

    def _lease_heartbeat_loop(
        self, task_id: str, lease_token: str, finished: threading.Event, cancel: threading.Event,
    ) -> None:
        interval = max(1.0, self.config.heartbeat_seconds)
        while not finished.wait(interval):
            try:
                self.api.task_heartbeat(task_id, lease_token)
            except RunnerApiError as exc:
                logger.warning(
                    '任务续租失败 task_id=%s code=%s status=%s',
                    task_id, exc.code, exc.status_code,
                )
                if exc.code in {'invalid_lease', 'lease_expired', 'task_not_found'}:
                    cancel.set()
                    return

    @staticmethod
    def _system_error_payload(reason: str = 'runner_error') -> dict[str, object]:
        return {
            'status': 'system_error',
            'stdout': '',
            'stderr': '',
            'execution_ms': 0,
            'score': None,
            'detail': {'tests': [], 'termination_reason': reason},
        }

    def process_task(self, envelope: dict[str, object]) -> None:
        task_id = envelope.get('task_id')
        lease_token = envelope.get('lease_token')
        if not isinstance(task_id, str) or not isinstance(lease_token, str):
            logger.error('拒绝无效任务信封')
            return

        cancel = threading.Event()
        lease_finished = threading.Event()
        with self._active_lock:
            self._active_tasks[task_id] = cancel
        lease_thread = threading.Thread(
            target=self._lease_heartbeat_loop,
            args=(task_id, lease_token, lease_finished, cancel),
            name=f'lease-{task_id[:8]}',
            daemon=True,
        )
        lease_thread.start()
        logger.info('开始执行 task_id=%s type=%s', task_id, envelope.get('task_type'))

        try:
            result = self.evaluator.evaluate(envelope, cancel_event=cancel)
        except Exception:
            logger.exception('Runner 内部执行失败 task_id=%s', task_id)
            result = self._system_error_payload()

        try:
            response = self.api.complete_task(task_id, lease_token, result)
            logger.info(
                '完成回写 task_id=%s status=%s applied=%s',
                task_id, result.get('status'), response.get('applied'),
            )
        except RunnerApiError as exc:
            logger.error(
                '完成回写失败 task_id=%s code=%s status=%s',
                task_id, exc.code, exc.status_code,
            )
        finally:
            lease_finished.set()
            lease_thread.join(timeout=2)
            with self._active_lock:
                self._active_tasks.pop(task_id, None)

    def _worker_loop(self, worker_index: int) -> None:
        while not self.stop_event.is_set():
            try:
                envelope = self.api.claim_task()
            except RunnerApiError as exc:
                logger.warning(
                    '领取任务失败 worker=%s code=%s status=%s',
                    worker_index, exc.code, exc.status_code,
                )
                self.stop_event.wait(min(2.0, self.config.claim_idle_seconds * 2))
                continue
            if envelope is None:
                self.stop_event.wait(self.config.claim_idle_seconds)
                continue
            self.process_task(envelope)

    def run(self) -> None:
        logger.info(
            '本机 Runner 启动 runner_id=%s capacity=%s',
            self.config.runner_id, self.config.concurrency,
        )
        # Register before claims; the Web rejects unregistered/stale nodes.
        self.api.node_heartbeat(active_slots=0, status='online')
        self._heartbeat_thread = threading.Thread(
            target=self._node_heartbeat_loop, name='runner-heartbeat', daemon=True,
        )
        self._heartbeat_thread.start()
        self._workers = [
            threading.Thread(
                target=self._worker_loop,
                args=(index,),
                name=f'runner-worker-{index}',
                daemon=True,
            )
            for index in range(self.config.concurrency)
        ]
        for worker in self._workers:
            worker.start()

        self.stop_event.wait()
        self._safe_node_heartbeat(status='draining')
        deadline = time.monotonic() + self.config.shutdown_grace_seconds
        for worker in self._workers:
            worker.join(timeout=max(0.0, deadline - time.monotonic()))

        alive = [worker for worker in self._workers if worker.is_alive()]
        if alive:
            with self._active_lock:
                cancel_events = list(self._active_tasks.values())
            for event in cancel_events:
                event.set()
            self.executor.terminate_all()
            for worker in alive:
                worker.join(timeout=2)
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2)
        logger.info('本机 Runner 已停止 active_slots=%s', self.active_slots)
