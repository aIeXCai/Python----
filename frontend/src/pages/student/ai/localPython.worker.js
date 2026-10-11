// The interpreter and its standard library are served by the classroom website.
// Student code runs in this worker so a busy loop cannot freeze the quiz page.
let interpreterPromise

const EXECUTE = `
import contextlib, io, json, sys, traceback

class _LimitedOutput(io.StringIO):
    def __init__(self, limit):
        super().__init__()
        self.limit = limit
        self.used = 0
    def write(self, text):
        self.used += len(text.encode('utf-8'))
        if self.used > self.limit:
            raise OverflowError('输出超过大小限制')
        return super().write(text)

_out = _LimitedOutput(131072)
_err = _LimitedOutput(131072)
_input = io.StringIO(_student_stdin)
_status = 'succeeded'
with contextlib.redirect_stdout(_out), contextlib.redirect_stderr(_err):
    _previous_stdin = sys.stdin
    sys.stdin = _input
    try:
        exec(compile(_student_code, '<student>', 'exec'), {'__name__': '__main__'})
    except BaseException:
        _status = 'runtime_error'
        try:
            _err.write(traceback.format_exc())
        except OverflowError:
            pass
    finally:
        sys.stdin = _previous_stdin
json.dumps({'status': _status, 'output': _out.getvalue(), 'error': _err.getvalue()}, ensure_ascii=False)
`

async function interpreter() {
  if (!interpreterPromise) {
    interpreterPromise = (async () => {
      const base = new URL(`${import.meta.env.BASE_URL}pyodide/`, self.location.origin)
      const { loadPyodide } = await import(/* @vite-ignore */ new URL('pyodide.mjs', base).href)
      return loadPyodide({ indexURL: base.href })
    })()
  }
  return interpreterPromise
}

self.onmessage = async ({ data }) => {
  if (data.type === 'init') {
    try {
      await interpreter()
      self.postMessage({ type: 'ready' })
    } catch (error) {
      self.postMessage({ type: 'init_error', error: String(error?.message || error) })
    }
    return
  }
  if (data.type !== 'execute') return
  try {
    const pyodide = await interpreter()
    pyodide.globals.set('_student_code', data.code)
    pyodide.globals.set('_student_stdin', data.stdin || '')
    const started = performance.now()
    const result = JSON.parse(pyodide.runPython(EXECUTE))
    self.postMessage({ type: 'result', id: data.id, ...result, execution_ms: Math.round(performance.now() - started) })
  } catch (error) {
    self.postMessage({ type: 'result', id: data.id, status: 'system_error', output: '', error: String(error?.message || error) })
  }
}
