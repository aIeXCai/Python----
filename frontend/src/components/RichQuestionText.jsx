import './RichQuestionText.css'

function InlineText({ value }) {
  const parts = String(value).split(/(`[^`\n]+`)/g)
  return parts.map((part, index) => part.startsWith('`') && part.endsWith('`')
    ? <code className="question-inline-code" key={index}>{part.slice(1, -1)}</code>
    : <span key={index}>{part}</span>)
}

/**
 * Safe question renderer for plain text plus Markdown-style inline/fenced code.
 * React escapes every value; question content is never injected as HTML.
 */
export default function RichQuestionText({ value = '', className = '' }) {
  const source = String(value).replace(/\r\n?/g, '\n')
  const blocks = []
  const fence = /```([^\n`]*)\n([\s\S]*?)```/g
  let cursor = 0
  let match
  while ((match = fence.exec(source)) !== null) {
    if (match.index > cursor) blocks.push({ type: 'text', value: source.slice(cursor, match.index) })
    blocks.push({ type: 'code', language: match[1].trim(), value: match[2].replace(/\n$/, '') })
    cursor = match.index + match[0].length
  }
  if (cursor < source.length || blocks.length === 0) blocks.push({ type: 'text', value: source.slice(cursor) })

  return <div className={`question-rich-text ${className}`.trim()}>{blocks.map((block, index) => block.type === 'code'
    ? <div className="question-code-block" key={index}>
        {block.language && <span className="question-code-language">{block.language}</span>}
        <pre><code>{block.value}</code></pre>
      </div>
    : block.value && <span className="question-text-block" key={index}><InlineText value={block.value} /></span>)}</div>
}
