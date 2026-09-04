import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

vi.mock('../api/chat.js', () => ({
  sendChatMessage: vi.fn(),
  getChatSessions: vi.fn(),
  getChatMessages: vi.fn(),
  deleteChatSession: vi.fn(),
}))

import { ChatProvider, useChat } from './ChatContext.jsx'

function Probe() {
  const chat = useChat()
  return <div>
    <span data-testid="state">{chat.isDisabled ? chat.disabledReason : 'enabled'}</span>
    <button onClick={() => chat.setDisabled(true, '正式小测')}>disable</button>
    <button onClick={() => chat.setDisabled(false)}>enable</button>
  </div>
}

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
