from django.db import migrations, models


GRADES = ('七年级', '八年级', '九年级', '高一', '高二', '高三')
ALIASES = {'初一': '七年级', '初二': '八年级', '初三': '九年级'}


def canonical(value, *, blank=False):
    text = '' if value is None else str(value).strip()
    if not text and blank:
        return ''
    result = ALIASES.get(text, text)
    if result not in GRADES:
        raise RuntimeError(f'未知年级: {text!r}')
    return result


def forwards(apps, schema_editor):
    Unit = apps.get_model('info_tech', 'Unit')
    Session = apps.get_model('info_tech', 'QuizSession')
    Submission = apps.get_model('info_tech', 'QuizSubmission')
    for unit in Unit.objects.all().iterator():
        unit.grade = canonical(unit.grade)
        unit.save(update_fields=['grade'])
    for session in Session.objects.all().iterator():
        values = session.visible_grades or []
        normalized = []
        for value in values:
            grade = canonical(value)
            if grade not in normalized:
                normalized.append(grade)
        session.visible_grades = normalized
        session.save(update_fields=['visible_grades'])
    for submission in Submission.objects.all().iterator():
        submission.grade = canonical(submission.grade, blank=True)
        submission.class_num_snapshot = (submission.class_num_snapshot or '').strip()
        submission.student_number_snapshot = (submission.student_number_snapshot or '').strip()
        submission.save(update_fields=[
            'grade', 'class_num_snapshot', 'student_number_snapshot',
        ])


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0008_normalize_grade_and_identity'),
        ('info_tech', '0007_quizsession_archived_at'),
    ]
    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='unit', name='grade',
            field=models.CharField(
                choices=[(grade, grade) for grade in GRADES],
                default='七年级', max_length=20, verbose_name='年级',
            ),
        ),
    ]
