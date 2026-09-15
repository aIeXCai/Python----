#!/usr/bin/env python3
"""Stable script entry point so service managers can identify this Runner."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from runner.__main__ import main  # noqa: E402


if __name__ == '__main__':
    raise SystemExit(main())
