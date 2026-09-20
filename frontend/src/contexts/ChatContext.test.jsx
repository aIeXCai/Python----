import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

vi.mock('../api/chat.js', () => ({
  sendChatMessage: vi.fn(),
  getChatSessions: vi.fn(),
  getChatMessages: vi.fn(),
  deleteChatSession: vi.fn(),
}))

import { ChatProvider, useChat } from './ChatContext.jsx'
import { sendChatMessage } from '../api/chat.js'

function Probe() {
  const chat = useChat()
  return <div>
    <span data-testid="state">{chat.isDisabled ? chat.disabledReason : 'enabled'}</span>
    <button onClick={() => chat.setDisabled(true, '正式小测')}>disable</button>
    <button onClick={() => chat.setDisabled(false)}>enable</button>
  </div>
}

function ContextProbe() {
  const chat = useChat()
  return <div>
    <button onClick={() => chat.setContext({ type: 'ai_free_practice', title: '自由练习', code: 'print(1)' })}>code-one</button>
    <button onClick={() => chat.setContext({ type: 'ai_free_practice', title: '自由练习', code: 'print(2)' })}>code-two</button>
    <button onClick={() => chat.sendMessage('帮我看看')}>send</button>
  </div>
}

beforeEach(() => {
  vi.clearAllMocks()
  sendChatMessage.mockResolvedValue({ session_id: 1, title: '帮我看看' })
})

describe('ChatContext quiz disable state', () => {
  it('can disable and restore the assistant with an explicit reason', () => {
    render(<ChatProvider><Probe /></ChatProvider>)
    expect(screen.getByTestId('state')).toHaveTextContent('enabled')
    fireEvent.click(screen.getByText('disable'))
    expect(screen.getByTestId('state')).toHaveTextContent('正式小测')
    fireEvent.click(screen.getByText('enable'))
    expect(screen.getByTestId('state')).toHaveTextContent('enabled')
  })
})

describe('ChatContext page context', () => {
  it('发送消息时读取自由练习最后一次更新的代码', async () => {
    render(<ChatProvider><ContextProbe /></ChatProvider>)

    fireEvent.click(screen.getByText('code-one'))
    fireEvent.click(screen.getByText('code-two'))
    fireEvent.click(screen.getByText('send'))

    await waitFor(() => expect(sendChatMessage).toHaveBeenCalledWith(expect.objectContaining({
      message: '帮我看看',
      context: {
        type: 'ai_free_practice',
        title: '自由练习',
        code: 'print(2)',
      },
    })))
  })
})
