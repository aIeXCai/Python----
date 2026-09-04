"""Canonical grade and student-identity normalization rules."""

import unicodedata

from django.core.exceptions import ValidationError


CANONICAL_GRADES = (
    '七年级', '八年级', '九年级', '高一', '高二', '高三',
)
GRADE_CHOICES = tuple((grade, grade) for grade in CANONICAL_GRADES)
GRADE_ALIASES = {
    '初一': '七年级',
    '初二': '八年级',
    '初三': '九年级',
}


def normalize_grade(value, *, allow_blank=False):
    if value is None or str(value).strip() == '':
        if allow_blank:
            return None
        raise ValidationError('年级不能为空。')
    normalized = GRADE_ALIASES.get(str(value).strip(), str(value).strip())
    if normalized not in CANONICAL_GRADES:
        raise ValidationError('年级不在允许范围内。')
    return normalized


def normalize_student_identifier(value, *, label='学生标识', max_length=20):
    if value is None:
        raise ValidationError(f'{label}不能为空。')
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f'{label}不能为空。')
    if len(normalized) > max_length:
        raise ValidationError(f'{label}不能超过 {max_length} 个字符。')
    if any(unicodedata.category(char).startswith('C') for char in normalized):
        raise ValidationError(f'{label}不能包含控制字符。')
    return normalized
