import hashlib
import json
import re
import unicodedata

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

from .models import GRADE_LABELS, Language


def is_han_character(character):
    return character == '〇' or unicodedata.name(character, '').startswith((
        'CJK UNIFIED IDEOGRAPH', 'CJK COMPATIBILITY IDEOGRAPH',
    ))


def required_text(record, key, max_length=None):
    value = record.get(key)
    if not isinstance(value, str) or not value.strip() or (max_length and len(value.strip()) > max_length):
        raise ValueError(f'{key} 缺失或格式无效')
    return value.strip()


def normalize_article(record):
    if not isinstance(record, dict):
        raise ValueError('每行必须是一个 JSON 对象')

    grade = record.get('grade')
    if type(grade) is not int or grade not in GRADE_LABELS or record.get('grade_label') != GRADE_LABELS[grade]:
        raise ValueError('grade 与 grade_label 必须对应三至八年级')

    language = record.get('language')
    if language not in Language.values:
        raise ValueError('language 必须是 zh 或 en')

    raw_paragraphs = record.get('paragraphs')
    if not isinstance(raw_paragraphs, list) or not raw_paragraphs:
        raise ValueError('paragraphs 必须是非空的正文段落列表')

    paragraphs = []
    for raw_paragraph in raw_paragraphs:
        if not isinstance(raw_paragraph, str) or not raw_paragraph.strip():
            raise ValueError('正文存在空段落或非文本段落')
        paragraph = unicodedata.normalize('NFC', raw_paragraph.strip())
        if language == Language.ENGLISH and any(not ' ' <= char <= '~' for char in paragraph):
            raise ValueError('英文正文只能使用键盘可直接输入的 ASCII 字符')
        if any(unicodedata.category(char).startswith('C') for char in paragraph):
            raise ValueError('段落内含控制字符')
        paragraphs.append(paragraph)

    body = (' ' if language == Language.ENGLISH else '').join(paragraphs)
    if language == Language.CHINESE and not any(is_han_character(char) for char in body):
        raise ValueError('中文正文至少需要一个汉字')
    if len(body) > 10_000:
        raise ValueError('正文超过 10000 字符')

    metadata = {
        key: required_text(record, key)
        for key in ('semester', 'textbook_series', 'edition', 'unit', 'textbook_title_or_topic',
                    'genre', 'material_type', 'source_title', 'license_or_permission',
                    'edition_check_status')
    }
    if metadata['semester'] not in ('上', '下'):
        raise ValueError('semester 必须是 上 或 下')
    url = required_text(record, 'source_url')
    try:
        URLValidator(schemes=['http', 'https'])(url)
    except ValidationError as exc:
        raise ValueError('source_url 必须是有效的 HTTP 或 HTTPS 链接') from exc
    metadata['source_url'] = url
    lesson_no = record.get('lesson_no')
    if lesson_no not in (None, '', '—'):
        if type(lesson_no) is not int or lesson_no < 0:
            raise ValueError('lesson_no 必须是非负整数或为空；0 表示复习材料')
        metadata['lesson_no'] = lesson_no

    if language == Language.ENGLISH and not any(char.isalpha() for char in body):
        raise ValueError('正文缺少可练习的文字')

    source_id = required_text(record, 'id', 100)
    draft_difficulty = required_text(record, 'difficulty_draft', 30)
    match = re.fullmatch(r'L\d+\s+(易|中|难)', draft_difficulty)
    difficulty = {'易': '基础', '中': '进阶', '难': '挑战'}[match.group(1)] if match else draft_difficulty
    metadata['difficulty_draft'] = draft_difficulty
    for key in ('alignment_level', 'note'):
        if record.get(key):
            metadata[key] = required_text(record, key)

    fields = {
        'grade': grade,
        'language': language,
        'difficulty': difficulty,
        'title': required_text(record, 'title', 200),
        'paragraphs': paragraphs,
        'body_digest': hashlib.sha256(body.encode('utf-8')).hexdigest(),
        'source_metadata': metadata,
    }
    return source_id, fields


def read_bank(path):
    entries = []
    errors = []
    seen_ids = set()
    seen_bodies = set()
    with path.open(encoding='utf-8-sig') as stream:
        for row_no, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                source_id, fields = normalize_article(json.loads(line))
                if source_id in seen_ids:
                    raise ValueError('来源 ID 重复')
                body_key = fields['grade'], fields['language'], fields['body_digest']
                if body_key in seen_bodies:
                    raise ValueError('同年级、同语言的正文重复')
            except ValueError as exc:
                errors.append(f'第 {row_no} 行：{exc}')
                continue
            seen_ids.add(source_id)
            seen_bodies.add(body_key)
            entries.append((source_id, fields))
    return entries, errors
