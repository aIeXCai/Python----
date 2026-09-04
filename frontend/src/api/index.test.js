/**
 * API module tests
 * Run: cd frontend && npx vitest run src/api/index.test.js
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

beforeEach(() => {
  // Reset localStorage mock
  vi.stubGlobal('localStorage', {
    store: {},
    getItem(key) {
      return this.store[key] || null
    },
    setItem(key, value) {
      this.store[key] = value
    },
    removeItem(key) {
      delete this.store[key]
    },
    clear() {
      this.store = {}
    },
  })
  localStorage.clear()
})

describe('runCode (src/api/index.js)', () => {
  it('sends POST to /api/ai/run_code/ with code and default stdin', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ output: 'hello\n', error: '', execution_time: 0.05 }),
    })
    vi.stubGlobal('fetch', mockFetch)
    // use a module-level reload trick — re-import for fresh mocks
    const mod = await import('./index.js?t=' + Math.random())

    const result = await mod.runCode('print("hello")')

    expect(mockFetch).toHaveBeenCalledTimes(1)
    const [url, options] = mockFetch.mock.calls[0]
    expect(url).toBe('/api/ai/run_code/')
    expect(options.method).toBe('POST')
    expect(options.headers['Content-Type']).toBe('application/json')
    expect(options.headers['Idempotency-Key']).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    )
    const body = JSON.parse(options.body)
    expect(body.code).toBe('print("hello")')
    expect(body.stdin).toBe('')
    expect(result).toEqual({ output: 'hello\n', error: '', execution_time: 0.05 })
  })

  it('passes stdin to backend', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ output: '3\n', error: '', execution_time: 0.02 }),
    })
    vi.stubGlobal('fetch', mockFetch)
    const mod = await import('./index.js?t=' + Math.random())

    await mod.runCode('a=int(input())\nprint(a+1)', '2')

    const body = JSON.parse(mockFetch.mock.calls[0][1].body)
    expect(body.stdin).toBe('2')
    expect(body.code).toBe('a=int(input())\nprint(a+1)')
  })

  it('includes Authorization header when token exists', async () => {
    localStorage.setItem('token', 'test-token-abc')
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ output: '', error: '', execution_time: 0 }),
    })
    vi.stubGlobal('fetch', mockFetch)
    const mod = await import('./index.js?t=' + Math.random())

    await mod.runCode('x=1')

    const headers = mockFetch.mock.calls[0][1].headers
    expect(headers['Authorization']).toBe('Token test-token-abc')
  })

  it('does not include Authorization header when no token', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ output: '', error: '', execution_time: 0 }),
    })
    vi.stubGlobal('fetch', mockFetch)
    const mod = await import('./index.js?t=' + Math.random())

    await mod.runCode('x=1')

    const headers = mockFetch.mock.calls[0][1].headers
    expect(headers['Authorization']).toBeUndefined()
  })

  it('throws on non-ok response with error message', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ error: 'code is required' }),
    })
    vi.stubGlobal('fetch', mockFetch)
    const mod = await import('./index.js?t=' + Math.random())

    // The request() function throws on non-ok responses
    // And also redirects to /login if status is 401
    // For 400, it will throw with the error message
    await expect(mod.runCode('')).rejects.toThrow('code is required')
  })

  it('handles error response with details field', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ error: 'validation error', details: { code: 'too long' } }),
    })
    vi.stubGlobal('fetch', mockFetch)
    // We also need to mock window.location
    const mod = await import('./index.js?t=' + Math.random())

    await expect(mod.runCode('print("x"*9999)')).rejects.toThrow()
  })

  it('returns execution result with error field for runtime errors', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        output: '',
        error: "NameError: name 'x' is not defined",
        execution_time: 0.01,
      }),
    })
    vi.stubGlobal('fetch', mockFetch)
    const mod = await import('./index.js?t=' + Math.random())

    const result = await mod.runCode('print(x)')

    expect(result.error).toBe("NameError: name 'x' is not defined")
    expect(result.output).toBe('')
  })
})

describe('execution task API', () => {
  it('returns null for the active-task 204 response', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, status: 204 })
    vi.stubGlobal('fetch', mockFetch)
    const mod = await import('./index.js?t=' + Math.random())

    const result = await mod.getActiveExecutionTask({ taskType: 'grade', problemId: 'p 1' })

    expect(result).toBeNull()
    expect(mockFetch.mock.calls[0][0]).toBe('/api/ai/executions/active/?task_type=grade&problem_id=p+1')
  })

  it('polls queued tasks until a final result and reports updates', async () => {
    const responses = [
      { task_id: 'task-1', status: 'running', poll_after_ms: 0 },
      { task_id: 'task-1', status: 'succeeded', output: 'ok\n' },
    ]
    const mockFetch = vi.fn().mockImplementation(async () => ({
      ok: true,
      status: 200,
      json: async () => responses.shift(),
    }))
    vi.stubGlobal('fetch', mockFetch)
    const mod = await import('./index.js?t=' + Math.random())
    const onUpdate = vi.fn()

    const result = await mod.pollExecutionTask('task-1', {
      initialDelay: 0, maxDelay: 0, maxAttempts: 3, onUpdate,
    })

    expect(result.status).toBe('succeeded')
    expect(mockFetch).toHaveBeenCalledTimes(2)
    expect(onUpdate).toHaveBeenCalledTimes(2)
  })

  it('passes AbortSignal to task detail requests', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({ task_id: 'task-2', status: 'queued' }),
    })
    vi.stubGlobal('fetch', mockFetch)
    const mod = await import('./index.js?t=' + Math.random())
    const controller = new AbortController()

    await mod.getExecutionTask('task-2', { signal: controller.signal })

    expect(mockFetch.mock.calls[0][1].signal).toBe(controller.signal)
  })
})

describe('account security API', () => {
  it('logout calls backend before clearing local credentials', async () => {
    localStorage.setItem('token', 'logout-token')
    localStorage.setItem('user', '{"role":"teacher"}')
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({ message: '已登出' }),
    })
    vi.stubGlobal('fetch', mockFetch)
    const mod = await import('./index.js?t=' + Math.random())
    await mod.logout()
    expect(mockFetch).toHaveBeenCalledTimes(1)
    expect(mockFetch.mock.calls[0][0]).toBe('/api/auth/logout/')
    expect(mockFetch.mock.calls[0][1].method).toBe('POST')
    expect(mockFetch.mock.calls[0][1].headers.Authorization).toBe('Token logout-token')
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
  })

  it('logout clears local credentials even when network fails', async () => {
    localStorage.setItem('token', 'logout-token')
    localStorage.setItem('user', '{"role":"teacher"}')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))
    const mod = await import('./index.js?t=' + Math.random())
    await expect(mod.logout()).rejects.toThrow('network down')
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
  })

  it('password APIs use dedicated POST endpoints and expected bodies', async () => {
    localStorage.setItem('token', 'teacher-token')
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({ message: 'ok' }),
    })
    vi.stubGlobal('fetch', mockFetch)
    const mod = await import('./index.js?t=' + Math.random())
    await mod.revealStudentPassword(7)
    await mod.resetStudentPassword(7, 'NewPassword42')
    await mod.generateStudentTemporaryPassword(7)

    expect(mockFetch.mock.calls[0][0]).toBe('/api/auth/students/7/password/reveal/')
    expect(mockFetch.mock.calls[0][1].method).toBe('POST')
    expect(JSON.parse(mockFetch.mock.calls[1][1].body)).toEqual({
      mode: 'manual', password: 'NewPassword42',
    })
    expect(JSON.parse(mockFetch.mock.calls[2][1].body)).toEqual({ mode: 'generated' })
  })
})
