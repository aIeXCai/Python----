"""Cross-platform local execution runner.

The runner is intentionally independent from Django and never imports backend
models or settings.  It communicates with the Web process only through the
signed internal runner protocol.
"""
