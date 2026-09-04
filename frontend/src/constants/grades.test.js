import { describe, expect, it } from 'vitest'

import { GRADES, gradeOptions } from './grades.js'

describe('标准年级选项', () => {
  it('仅对外提供六个标准年级', () => {
    expect(GRADES).toEqual([
      '七年级', '八年级', '九年级', '高一', '高二', '高三',
    ])
    expect(GRADES).not.toContain('初一')
  })

  it('显示文案与传给后端的值一致', () => {
    expect(gradeOptions).toEqual(
      GRADES.map((value) => ({ value, label: value })),
    )
  })
})
