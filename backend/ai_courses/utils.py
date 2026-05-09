import subprocess
import time
import tempfile
import os
import sys


def run_code_interactive(code, stdin=""):
    """
    Execute Python code interactively in a subprocess.

    Args:
        code: Python source code string to execute
        stdin: Optional stdin input for the code

    Returns:
        dict with keys: output, error, execution_time, timed_out
    """
    start_time = time.time()
    timed_out = False
    output = ""
    error = ""

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', delete=False, encoding='utf-8'
        ) as f:
            f.write(code)
            tmp_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, tmp_path],
                input=stdin,
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = result.stdout
            error = result.stderr
        except subprocess.TimeoutExpired:
            timed_out = True
            error = "Code execution timed out after 10 seconds"
    except Exception as e:
        error = f"Execution error: {str(e)}"
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    execution_time = round(time.time() - start_time, 6)

    return {
        "output": output,
        "error": error,
        "execution_time": execution_time,
        "timed_out": timed_out,
    }
