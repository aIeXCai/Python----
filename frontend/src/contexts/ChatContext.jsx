import { createContext, useContext, useState, useCallback, useRef } from 'react'
import { sendChatMessage, getChatSessions, getChatMessages, deleteChatSession } from '../api/chat.js'

const ChatContext = createContext(null)

export function ChatProvider({ children }) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [context, setContext] = useState(null)     // 页面上下文
  const [inputText, setInputText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState('')
  const [view, setView] = useState('chat')          // 'chat' | 'history'
  const [sessions, setSessions] = useState([])      // 历史会话列表
  const [isLoadingSessions, setIsLoadingSessions] = useState(false)
  const [isDisabled, setIsDisabledState] = useState(false)
  const [disabledReason, setDisabledReason] = useState('')
  const contextRef = useRef(null)  // 避免闭包过时

  // 同步 context 到 ref
  const updateContext = useCallback((ctx) => {
    contextRef.current = ctx
    setContext(ctx)
  }, [])

  const toggle = useCallback(() => setIsOpen((v) => !v), [])

  const open = useCallback(() => setIsOpen(true), [])
  const close = useCallback(() => setIsOpen(false), [])

  const setDisabled = useCallback((disabled, reason = '') => {
    setIsDisabledState(Boolean(disabled))
    setDisabledReason(disabled ? reason : '')
    if (disabled) setIsOpen(false)
  }, [])

  /** 发送消息 */
  const send = useCallback(async (text) => {
    const trimmed = text.trim()
    if (!trimmed || isStreaming || isDisabled) return

    setInputText('')
    setError('')

    // 追加用户消息
    const userMsg = { id: Date.now(), role: 'user', content: trimmed }
    const assistantMsg = { id: Date.now() + 1, role: 'assistant', content: '', isStreaming: true }

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setIsStreaming(true)

    try {
      const result = await sendChatMessage({
        message: trimmed,
        sessionId,
        context: contextRef.current,
        onToken(token) {
          // 逐 token 追加到 AI 消息
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last && last.role === 'assistant') {
              updated[updated.length - 1] = { ...last, content: last.content + token }
            }
            return updated
          })
        },
      })

      // 流结束，标记完成
      setMessages((prev) => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        if (last && last.role === 'assistant') {
          updated[updated.length - 1] = { ...last, isStreaming: false }
        }
        return updated
      })

      if (result && result.session_id) {
        setSessionId(result.session_id)
      }
    } catch (err) {
      setError(err.message || 'AI 服务异常')
      // 移除未完成的 placeholder
      setMessages((prev) => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        if (last && last.role === 'assistant' && !last.content) {
          updated.pop()
        } else if (last && last.role === 'assistant') {
          updated[updated.length - 1] = { ...last, isStreaming: false }
        }
        return updated
      })
    } finally {
      setIsStreaming(false)
    }
  }, [sessionId, isStreaming, isDisabled])

  /** 开始新会话 */
  const newSession = useCallback(() => {
    setSessionId(null)
    setMessages([])
    setError('')
    setInputText('')
    setView('chat')
  }, [])

  /** 加载历史会话列表 */
  const loadSessions = useCallback(async () => {
    setIsLoadingSessions(true)
    try {
      const data = await getChatSessions()
      setSessions(data)
    } catch {
      setError('加载历史会话失败')
    } finally {
      setIsLoadingSessions(false)
    }
  }, [])

  /** 从历史加载某条会话 */
  const loadHistory = useCallback(async (id) => {
    try {
      const data = await getChatMessages(id)
      const msgs = (data.messages || []).map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        isStreaming: false,
      }))
      setSessionId(id)
      setMessages(msgs)
      setError('')
      setInputText('')
      setView('chat')
    } catch {
      setError('加载会话记录失败')
    }
  }, [])

  /** 删除会话 */
  const removeSession = useCallback(async (id) => {
    try {
      await deleteChatSession(id)
      if (id === sessionId) {
        setSessionId(null)
        setMessages([])
      }
      // 刷新列表
      const data = await getChatSessions()
      setSessions(data)
    } catch {
      setError('删除失败')
    }
  }, [sessionId])

  /** 打开历史面板 */
  const openHistory = useCallback(() => {
    setView('history')
    loadSessions()
  }, [loadSessions])

  return (
    <ChatContext.Provider
      value={{
        isOpen,
        messages,
        sessionId,
        context,
        inputText,
        isStreaming,
        error,
        toggle,
        open,
        close,
        setContext: updateContext,
        sendMessage: send,
        setInputText,
        newSession,
        setError,
        view,
        setView,
        sessions,
        isLoadingSessions,
        isDisabled,
        disabledReason,
        setDisabled,
        loadSessions,
        loadHistory,
        removeSession,
        openHistory,
      }}
    >
      {children}
    </ChatContext.Provider>
  )
}

const noop = () => {}
export function useChat() {
  const ctx = useContext(ChatContext)
  if (!ctx) {
    return {
      isOpen: false,
      messages: [],
      sessionId: null,
      context: null,
      inputText: '',
      isStreaming: false,
      error: '',
      toggle: noop,
      open: noop,
      close: noop,
      setContext: noop,
      sendMessage: noop,
      setInputText: noop,
      newSession: noop,
      setError: noop,
      view: 'chat',
      setView: noop,
      sessions: [],
      isLoadingSessions: false,
      isDisabled: false,
      disabledReason: '',
      setDisabled: noop,
      loadSessions: noop,
      loadHistory: noop,
      removeSession: noop,
      openHistory: noop,
    }
  }
  return ctx
}
