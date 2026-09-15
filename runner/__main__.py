from __future__ import annotations

import logging
import signal
import sys

from .api_client import RunnerApiError
from .config import RunnerConfigError, load_config
from .controller import LocalRunnerController


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
    )
    try:
        config = load_config()
        controller = LocalRunnerController(config)
    except RunnerConfigError as exc:
        logging.getLogger('local_runner').error('Runner 配置无效：%s', exc)
        return 2

    def stop(_signum, _frame):
        controller.request_stop()

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, stop)
    try:
        controller.run()
    except RunnerApiError as exc:
        logging.getLogger('local_runner').error(
            'Runner 无法注册 code=%s status=%s', exc.code, exc.status_code,
        )
        return 1
    except KeyboardInterrupt:
        controller.request_stop()
        return 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
