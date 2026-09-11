/**
 * 学生列表排序工具（学生管理 / 成绩统计共用）。
 *
 * 学号在数据库里是字符串（如 '1'、'01'、'10'），直接按字符串排序会得到
 * '1' < '10' < '2' 的错误顺序；这里统一解析成数字比较，无法解析或缺失的
 * 学号排在最后。同学号（跨班）时按 年级 → 班级 → 姓名 兜底，保证顺序稳定。
 */

const GRADE_ORDER = ['七年级', '八年级', '九年级', '高一', '高二', '高三']
const UNKNOWN_GRADE = 99

const collator = new Intl.Collator('zh-Hans-CN', { numeric: true, sensitivity: 'base' })

export function studentNumberValue(value) {
  const text = String(value ?? '').trim()
  if (!text) return null
  const num = Number(text)
  return Number.isFinite(num) ? num : null
}

function gradeRank(grade) {
  const idx = GRADE_ORDER.indexOf(String(grade ?? '').trim())
  return idx === -1 ? UNKNOWN_GRADE : idx
}

function nameOf(student) {
  return String(student?.display_name || student?.username || '')
}

/** 按学号升序比较两个学生（数字优先、缺失置后、再按年级/班级/姓名兜底） */
export function compareStudentNumber(a, b) {
  const va = studentNumberValue(a?.student_number)
  const vb = studentNumberValue(b?.student_number)
  if (va === null && vb === null) return 0
  if (va === null) return 1
  if (vb === null) return -1
  if (va !== vb) return va - vb

  const ga = gradeRank(a?.grade)
  const gb = gradeRank(b?.grade)
  if (ga !== gb) return ga - gb

  const ca = studentNumberValue(a?.class_num) ?? 0
  const cb = studentNumberValue(b?.class_num) ?? 0
  if (ca !== cb) return ca - cb

  return collator.compare(nameOf(a), nameOf(b))
}

/** 按学号排序（order: 'asc' | 'desc'）；无学号的学生始终排在最后 */
export function sortStudentsByNumber(students, order = 'asc') {
  const dir = order === 'desc' ? -1 : 1
  return [...(students || [])].sort((a, b) => {
    const va = studentNumberValue(a?.student_number)
    const vb = studentNumberValue(b?.student_number)
    if (va === null || vb === null) {
      if (va === null && vb === null) return compareStudentNumber(a, b)
      return va === null ? 1 : -1
    }
    if (va !== vb) return (va - vb) * dir
    return compareStudentNumber(a, b)
  })
}

function compareByField(a, b, field) {
  switch (field) {
    case 'student_number':
      return compareStudentNumber(a, b)
    case 'grade': {
      const gap = gradeRank(a?.grade) - gradeRank(b?.grade)
      return gap !== 0 ? gap : compareStudentNumber(a, b)
    }
    case 'class_num': {
      const ca = studentNumberValue(a?.class_num)
      const cb = studentNumberValue(b?.class_num)
      if (ca === null && cb === null) return compareStudentNumber(a, b)
      if (ca === null) return 1
      if (cb === null) return -1
      return ca !== cb ? ca - cb : compareStudentNumber(a, b)
    }
    case 'username':
      return collator.compare(String(a?.username || ''), String(b?.username || ''))
    default:
      return 0
  }
}

/** 通用学生排序：field ∈ student_number | grade | class_num | username */
export function sortStudents(students, field = 'student_number', order = 'asc') {
  if (field === 'student_number') return sortStudentsByNumber(students, order)
  const dir = order === 'desc' ? -1 : 1
  return [...(students || [])].sort((a, b) => compareByField(a, b, field) * dir)
}
