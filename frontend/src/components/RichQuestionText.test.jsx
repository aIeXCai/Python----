import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import RichQuestionText from './RichQuestionText.jsx'

describe('RichQuestionText', () => {
  it('保留题干代码块的缩进、换行和特殊字符', () => {
    const { container } = render(<RichQuestionText value={'运行：\n```python\nif x < 3:\n    print("<ok> & done")\n```'} />)
    const code = container.querySelector('.question-code-block code')
    expect(code).toHaveTextContent('if x < 3:')
    expect(code.textContent).toBe('if x < 3:\n    print("<ok> & done")')
    expect(container.querySelector('ok')).toBeNull()
    expect(screen.getByText('python')).toBeInTheDocument()
  })

  it('在选项中正确显示行内代码且不执行 HTML', () => {
    const { container } = render(<RichQuestionText value={'选择 `print("<b>x</b>")` 并保留\n换行'} />)
    expect(container.querySelector('.question-inline-code')).toHaveTextContent('print("<b>x</b>")')
    expect(container.querySelector('b')).toBeNull()
    expect(container.querySelector('.question-text-block').textContent).toContain('\n换行')
  })
})
