import collections
import sys
import threading
import time
import unittest

from runner.config import RunnerConfig
from runner.controller import LocalRunnerController


SECRET = 'runner-test-secret-that-is-long-enough-123456'


def config(**overrides):
    values = {
        'RUNNER_SERVICE_SECRET': SECRET,
        'RUNNER_PYTHON_EXECUTABLE': sys.executable,
        'RUNNER_CONCURRENCY': '2',
        'RUNNER_HEARTBEAT_SECONDS': '1',
        'RUNNER_CLAIM_IDLE_SECONDS': '0.05',
        'RUNNER_SHUTDOWN_GRACE_SECONDS': '2',
    }
    values.update(overrides)
    return RunnerConfig.from_mapping(values)


class FakeApi:
    def __init__(self, tasks=None):
        self.tasks = collections.deque(tasks or [])
        self.lock = threading.Lock()
        self.node_heartbeats = []
        self.task_heartbeats = []
        self.completions = []
        self.on_complete = None

    def node_heartbeat(self, **values):
        with self.lock:
            self.node_heartbeats.append(values)
        return {'runner_id': 'local-runner-01'}

    def claim_task(self):
        with self.lock:
            return self.tasks.popleft() if self.tasks else None

    def task_heartbeat(self, task_id, lease_token):
        with self.lock:
            self.task_heartbeats.append((task_id, lease_token))
        return {'task_id': task_id}

    def complete_task(self, task_id, lease_token, result):
        with self.lock:
            self.completions.append((task_id, lease_token, result))
            count = len(self.completions)
        if self.on_complete:
            self.on_complete(count)
        return {'task_id': task_id, 'status': result['status'], 'applied': True}


class TrackingEvaluator:
    def __init__(self, delay=0.05):
        self.delay = delay
        self.lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def evaluate(self, envelope, cancel_event=None):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            deadline = time.monotonic() + self.delay
            while time.monotonic() < deadline:
                if cancel_event and cancel_event.is_set():
                    break
                time.sleep(0.01)
            return {
                'status': 'succeeded', 'stdout': '', 'stderr': '',
                'execution_ms': int(self.delay * 1000),
                'detail': {'termination_reason': 'completed'},
            }
        finally:
            with self.lock:
                self.active -= 1


class FakeExecutor:
    def __init__(self):
        self.terminate_calls = 0

    def terminate_all(self):
        self.terminate_calls += 1


def envelope(index):
    return {
        'task_id': f'task-{index}',
        'task_type': 'run',
        'lease_token': f'lease-token-that-is-long-enough-{index}',
        'code': f'print({index})',
        'stdin': '',
        'limits': {'wall_seconds': 2},
    }


class LocalRunnerControllerTest(unittest.TestCase):
    def test_fixed_worker_count_limits_concurrent_execution(self):
        tasks = [envelope(index) for index in range(6)]
        api = FakeApi(tasks)
        evaluator = TrackingEvaluator(delay=0.08)
        controller = LocalRunnerController(
            config(RUNNER_CONCURRENCY='2'),
            api_client=api,
            executor=FakeExecutor(),
            evaluator=evaluator,
        )
        api.on_complete = lambda count: controller.request_stop() if count == len(tasks) else None
        thread = threading.Thread(target=controller.run)
        thread.start()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(api.completions), 6)
        self.assertEqual(evaluator.max_active, 2)
        self.assertEqual(api.node_heartbeats[0]['status'], 'online')
        self.assertTrue(any(item['status'] == 'draining' for item in api.node_heartbeats))

    def test_long_task_sends_lease_heartbeat(self):
        api = FakeApi()
        controller = LocalRunnerController(
            config(), api_client=api, executor=FakeExecutor(),
            evaluator=TrackingEvaluator(delay=1.1),
        )
        controller.process_task(envelope(1))
        self.assertGreaterEqual(len(api.task_heartbeats), 1)
        self.assertEqual(len(api.completions), 1)

    def test_invalid_envelope_is_not_completed(self):
        api = FakeApi()
        controller = LocalRunnerController(
            config(), api_client=api, executor=FakeExecutor(), evaluator=TrackingEvaluator(),
        )
        controller.process_task({'task_type': 'run'})
        self.assertEqual(api.completions, [])
        self.assertEqual(controller.active_slots, 0)


if __name__ == '__main__':
    unittest.main()
