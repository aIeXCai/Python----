import { useEffect, useRef } from 'react'
import { useChat } from '../contexts/ChatContext.jsx'
import { MessageCircle, X, Plus, Send, Clock, Trash2, ArrowLeft, Loader } from 'lucide-react'

/**
 * 将消息内容中的 <think>...</think> 块渲染为可折叠区域
 */
function formatContent(content) {
  if (!content) return null

  const regex = /<think>([\s\S]*?)(<\/think>|$)/g
  const parts = []
  let lastIndex = 0
  let match

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push(
        <span key={`t${lastIndex}`}>{content.slice(lastIndex, match.index)}</span>
      )
    }

    const inner = match[1]
    const closed = match[2] === '</think>'
    parts.push(
      <details key={`think${match.index}`} className="chat-think">
        <summary>{closed ? '💭 思考过程' : '💭 思考中...'}</summary>
        <div className="chat-think-body">{inner}</div>
      </details>
    )

    lastIndex = match.index + match[0].length
  }

  if (lastIndex < content.length) {
    parts.push(<span key={`t${lastIndex}`}>{content.slice(lastIndex)}</span>)
  }

  return parts.length > 0 ? parts : content
}

/** 简单的时间友好显示 */
function timeAgo(isoString) {
  const now = Date.now()
  const then = new Date(isoString).getTime()
  const diffMin = Math.floor((now - then) / 60000)
  if (diffMin < 1) return '刚才'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr} 小时前`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay < 7) return `${diffDay} 天前`
  return new Date(isoString).toLocaleDateString('zh-CN')
}

export default function FloatingChat() {
  const {
    isOpen, messages, context, inputText, isStreaming, error,
    toggle, setInputText, sendMessage, newSession, setError,
    view, setView, sessions, isLoadingSessions,
    loadHistory, removeSession, openHistory,
    isDisabled,
  } = useChat()

  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const panelRef = useRef(null)

  // 自动滚到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 打开面板时聚焦输入框
  useEffect(() => {
    if (isOpen && view === 'chat') {
      setTimeout(() => inputRef.current?.focus(), 200)
    }
  }, [isOpen, view])

  // 面板外点击关闭
  useEffect(() => {
    if (!isOpen) return
    function handleClick(e) {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        toggle()
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [isOpen, toggle])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(inputText)
    }
  }

  const handleSend = () => {
    if (!inputText.trim() || isStreaming) return
    sendMessage(inputText)
  }

  if (isDisabled) return null

  const contextLabel = context
    ? `${context.type === 'ai_problem' ? '题目' : '小测'}：${context.title}`
    : null

  const isChat = view === 'chat'

  return (
    <>
      {/* 悬浮按钮 */}
      <button
        className={`chat-float-btn ${isOpen ? 'chat-float-btn--hidden' : ''}`}
        onClick={toggle}
        title="AI 学习助手"
        aria-label="打开 AI 对话"
      >
        <MessageCircle size={28} />
      </button>

      {/* 聊天面板 */}
      <div
        ref={panelRef}
        className={`chat-panel ${isOpen ? 'chat-panel--open' : ''}`}
      >
        {/* 顶部栏 */}
        <div className="chat-panel-header">
          <div className="chat-panel-header-left">
            {isChat ? (
              <>
                <span className="chat-panel-title">AI 学习助手</span>
                {contextLabel && (
                  <span className="chat-context-badge">{contextLabel}</span>
                )}
              </>
            ) : (
              <>
                <button
                  className="chat-icon-btn"
                  onClick={() => setView('chat')}
                  title="返回聊天"
                >
                  <ArrowLeft size={18} />
                </button>
                <span className="chat-panel-title">历史会话</span>
              </>
            )}
          </div>
          <div className="chat-panel-header-right">
            {isChat && (
              <>
                <button
                  className="chat-icon-btn"
                  onClick={openHistory}
                  title="历史会话"
                  disabled={isStreaming}
                >
                  <Clock size={18} />
                </button>
                <button
                  className="chat-icon-btn"
                  onClick={() => { newSession(); inputRef.current?.focus() }}
                  title="新建对话"
                  disabled={isStreaming}
                >
                  <Plus size={18} />
                </button>
              </>
            )}
            <button className="chat-icon-btn" onClick={toggle} title="关闭">
              <X size={18} />
            </button>
          </div>
        </div>

        {/* ── 聊天视图 ── */}
        {isChat && (
          <>
            <div className="chat-messages">
              {messages.length === 0 && (
                <div className="chat-empty">
                  <MessageCircle size={40} strokeWidth={1} />
                  <p>你好！我是小 P 教师 👋</p>
                  <p>有任何编程课的问题，随时问我～</p>
                </div>
              )}

              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`chat-bubble ${
                    msg.role === 'user' ? 'chat-bubble--user' : 'chat-bubble--ai'
                  }`}
                >
                  {msg.role === 'assistant' && (
                    <div className="chat-bubble-avatar">P</div>
                  )}
                  <div className="chat-bubble-content">
                    {formatContent(msg.content)}
                    {msg.isStreaming && <span className="chat-cursor" />}
                  </div>
                </div>
              ))}

              <div ref={messagesEndRef} />
            </div>

            {error && (
              <div className="chat-error">
                <span>{error}</span>
                <button onClick={() => setError('')}>&times;</button>
              </div>
            )}

            <div className="chat-input-area">
              <textarea
                ref={inputRef}
                className="chat-input"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入你的问题..."
                rows={1}
                disabled={isStreaming}
              />
              <button
                className="chat-send-btn"
                onClick={handleSend}
                disabled={!inputText.trim() || isStreaming}
                title="发送"
              >
                <Send size={18} />
              </button>
            </div>
          </>
        )}

        {/* ── 历史视图 ── */}
        {!isChat && (
          <div className="chat-messages">
            {isLoadingSessions && (
              <div className="chat-empty">
                <Loader size={24} className="spin" />
                <p>加载中...</p>
              </div>
            )}

            {!isLoadingSessions && sessions.length === 0 && (
              <div className="chat-empty">
                <Clock size={40} strokeWidth={1} />
                <p>暂无历史会话</p>
                <p>开始一段新对话吧～</p>
              </div>
            )}

            {!isLoadingSessions && sessions.map((s) => (
              <button
                key={s.id}
                className="chat-session-item"
                onClick={() => loadHistory(s.id)}
              >
                <div className="chat-session-info">
                  <span className="chat-session-title">{s.title}</span>
                  <span className="chat-session-meta">
                    {s.message_count} 条消息 · {timeAgo(s.updated_at)}
                  </span>
                </div>
                <button
                  className="chat-session-delete"
                  onClick={(e) => { e.stopPropagation(); removeSession(s.id) }}
                  title="删除会话"
                >
                  <Trash2 size={14} />
                </button>
              </button>
            ))}
          </div>
        )}
      </div>
    </>
  )
}
