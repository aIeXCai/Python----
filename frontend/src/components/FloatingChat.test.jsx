/**
 * FloatingChat AI 聊天组件测试
 * 运行: cd frontend && npx vitest run src/components/FloatingChat.test.jsx
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const mockToggle = vi.fn()
const mockSetInputText = vi.fn()
const mockSendMessage = vi.fn()
const mockNewSession = vi.fn()
const mockSetError = vi.fn()
const mockSetContext = vi.fn()
const mockSetView = vi.fn()
const mockLoadHistory = vi.fn()
const mockRemoveSession = vi.fn()
const mockOpenHistory = vi.fn()

const mockUseChat = vi.fn(() => ({
  isOpen: false,
  messages: [],
  sessionId: null,
  context: null,
  inputText: '',
  isStreaming: false,
  error: '',
  view: 'chat',
  sessions: [],
  isLoadingSessions: false,
  isDisabled: false,
  toggle: mockToggle,
  open: vi.fn(),
  close: vi.fn(),
  setContext: mockSetContext,
  sendMessage: mockSendMessage,
  setInputText: mockSetInputText,
  newSession: mockNewSession,
  setError: mockSetError,
  setView: mockSetView,
  loadHistory: mockLoadHistory,
  removeSession: mockRemoveSession,
  openHistory: mockOpenHistory,
}))

vi.mock('../contexts/ChatContext.jsx', () => ({
  useChat: () => mockUseChat(),
  ChatProvider: ({ children }) => children,
}))

vi.mock('lucide-react', () => ({
  MessageCircle: () => 'MessageCircle',
  X: () => 'X',
  Plus: () => 'Plus',
  Send: () => 'Send',
  Clock: () => 'Clock',
  Trash2: () => 'Trash2',
  ArrowLeft: () => 'ArrowLeft',
  Loader: () => 'Loader',
}))

import FloatingChat from './FloatingChat.jsx'

function setChat(overrides = {}) {
  mockUseChat.mockReturnValue({
    isOpen: false,
    messages: [],
    sessionId: null,
    context: null,
    inputText: '',
    isStreaming: false,
    error: '',
    view: 'chat',
    sessions: [],
    isLoadingSessions: false,
    isDisabled: false,
    toggle: mockToggle,
    open: vi.fn(),
    close: vi.fn(),
    setContext: mockSetContext,
    sendMessage: mockSendMessage,
    setInputText: mockSetInputText,
    newSession: mockNewSession,
    setError: mockSetError,
    setView: mockSetView,
    loadHistory: mockLoadHistory,
    removeSession: mockRemoveSession,
    openHistory: mockOpenHistory,
    ...overrides,
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  setChat()
  Element.prototype.scrollIntoView = vi.fn()
})

describe('FloatingChat — 悬浮按钮', () => {
  it('渲染悬浮按钮', () => {
    render(<FloatingChat />)
    expect(screen.getByRole('button', { name: /打开 AI 对话/i })).toBeInTheDocument()
  })

  it('点击悬浮按钮调用 toggle', () => {
    render(<FloatingChat />)
    fireEvent.click(screen.getByRole('button', { name: /打开 AI 对话/i }))
    expect(mockToggle).toHaveBeenCalled()
  })

  it('正式小测作答期间完全隐藏入口', () => {
    setChat({ isDisabled: true })
    render(<FloatingChat />)
    expect(screen.queryByRole('button', { name: /打开 AI 对话/i })).not.toBeInTheDocument()
  })
})

describe('FloatingChat — 聊天面板', () => {
  it('面板关闭时不可见', () => {
    render(<FloatingChat />)
    expect(document.querySelector('.chat-panel')).not.toHaveClass('chat-panel--open')
  })

  it('isOpen=true 时面板可见', () => {
    setChat({ isOpen: true })
    render(<FloatingChat />)
    expect(document.querySelector('.chat-panel')).toHaveClass('chat-panel--open')
  })

  it('点击关闭按钮调用 toggle', () => {
    setChat({ isOpen: true })
    render(<FloatingChat />)
    fireEvent.click(screen.getByTitle('关闭'))
    expect(mockToggle).toHaveBeenCalled()
  })
})

describe('FloatingChat — 上下文标签', () => {
  it('无上下文时不显示标签', () => {
    setChat({ isOpen: true, context: null })
    render(<FloatingChat />)
    expect(screen.queryByText(/题目：/)).not.toBeInTheDocument()
    expect(screen.queryByText(/小测：/)).not.toBeInTheDocument()
  })

  it('AI 题目上下文时显示标签', () => {
    setChat({ isOpen: true, context: { type: 'ai_problem', title: '变量与赋值', id: '1' } })
    render(<FloatingChat />)
    expect(screen.getByText(/题目：变量与赋值/)).toBeInTheDocument()
  })

  it('信息课小测上下文时显示标签', () => {
    setChat({ isOpen: true, context: { type: 'info_quiz', title: '第一单元小测', id: '1' } })
    render(<FloatingChat />)
    expect(screen.getByText(/小测：第一单元小测/)).toBeInTheDocument()
  })
})

describe('FloatingChat — 消息列表', () => {
  it('无消息时显示空状态', () => {
    setChat({ isOpen: true })
    render(<FloatingChat />)
    expect(screen.getByText(/小 P 教师/)).toBeInTheDocument()
  })

  it('显示用户消息气泡', () => {
    setChat({ isOpen: true, messages: [{ id: 1, role: 'user', content: '什么是变量？' }] })
    render(<FloatingChat />)
    expect(screen.getByText('什么是变量？')).toBeInTheDocument()
  })

  it('显示 AI 消息气泡', () => {
    setChat({
      isOpen: true,
      messages: [
        { id: 1, role: 'user', content: '你好' },
        { id: 2, role: 'assistant', content: '你好！有什么可以帮你的？' },
      ],
    })
    render(<FloatingChat />)
    expect(screen.getByText('你好！有什么可以帮你的？')).toBeInTheDocument()
  })

  it('流式消息显示打字光标', () => {
    setChat({
      isOpen: true,
      messages: [{ id: 1, role: 'assistant', content: '正在输入...', isStreaming: true }],
    })
    render(<FloatingChat />)
    expect(document.querySelector('.chat-cursor')).toBeInTheDocument()
  })
})

describe('FloatingChat — think 折叠', () => {
  it('完整 think 块渲染为可折叠 details', () => {
    setChat({
      isOpen: true,
      messages: [{ id: 1, role: 'assistant', content: '<think>分析题目要求</think>你好！' }],
    })
    render(<FloatingChat />)
    const details = document.querySelector('.chat-think')
    expect(details).toBeInTheDocument()
    expect(details.querySelector('summary').textContent).toBe('💭 思考过程')
  })

  it('不完整 think 块显示思考中', () => {
    setChat({
      isOpen: true,
      messages: [{ id: 1, role: 'assistant', content: '<think>正在分析题目...' }],
    })
    render(<FloatingChat />)
    const details = document.querySelector('.chat-think')
    expect(details).toBeInTheDocument()
    expect(details.querySelector('summary').textContent).toBe('💭 思考中...')
  })
})

describe('FloatingChat — 输入与发送', () => {
  it('Enter 发送消息', async () => {
    setChat({ isOpen: true, inputText: '什么是变量？' })
    render(<FloatingChat />)
    await userEvent.type(screen.getByPlaceholderText('输入你的问题...'), '{Enter}')
    expect(mockSendMessage).toHaveBeenCalledWith('什么是变量？')
  })

  it('流式中禁用输入', () => {
    setChat({ isOpen: true, isStreaming: true })
    render(<FloatingChat />)
    expect(screen.getByPlaceholderText('输入你的问题...')).toBeDisabled()
    expect(screen.getByTitle('发送')).toBeDisabled()
  })

  it('空输入时发送按钮禁用', () => {
    setChat({ isOpen: true, inputText: '' })
    render(<FloatingChat />)
    expect(screen.getByTitle('发送')).toBeDisabled()
  })
})

describe('FloatingChat — 错误处理', () => {
  it('显示错误信息', () => {
    setChat({ isOpen: true, error: 'AI 服务繁忙，请稍后重试' })
    render(<FloatingChat />)
    expect(screen.getByText('AI 服务繁忙，请稍后重试')).toBeInTheDocument()
  })

  it('可关闭错误提示', () => {
    setChat({ isOpen: true, error: '出错了' })
    render(<FloatingChat />)
    fireEvent.click(document.querySelector('.chat-error button'))
    expect(mockSetError).toHaveBeenCalledWith('')
  })
})

describe('FloatingChat — 新建对话', () => {
  it('点击新建按钮调用 newSession', () => {
    setChat({ isOpen: true })
    render(<FloatingChat />)
    fireEvent.click(screen.getByTitle('新建对话'))
    expect(mockNewSession).toHaveBeenCalled()
  })
})
