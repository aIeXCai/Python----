import { describe, expect, it } from 'vitest'
import { API_BASE_URL, apiUrl, normalizeApiBase } from './config.js'

describe('API 地址配置', () => {
  it('未配置时使用同源 /api', () => {
    expect(normalizeApiBase()).toBe('/api')
    expect(normalizeApiBase('   ')).toBe('/api')
    expect(API_BASE_URL).toBe('/api')
  })

  it('清理自定义地址末尾的斜杠', () => {
    expect(normalizeApiBase(' https://example.test/api/// ')).toBe('https://example.test/api')
  })

  it('正确拼接有无开头斜杠的路径', () => {
    expect(apiUrl('/auth/login/')).toBe('/api/auth/login/')
    expect(apiUrl('auth/login/')).toBe('/api/auth/login/')
    expect(apiUrl()).toBe('/api')
  })
})
