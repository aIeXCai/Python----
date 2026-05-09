/**
 * API module tests
 * Run: cd frontend && npx vitest run src/api/index.test.js
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// We import the module under test dynamically after setting up mocks
let runCode, request, getToken

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
    expect(url).toBe('http://localhost:8080/api/ai/run_code/')
    expect(options.method).toBe('POST')
    expect(options.headers['Content-Type']).toBe('application/json')
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
