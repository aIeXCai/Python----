from django.db import migrations, models


GRADES = ('七年级', '八年级', '九年级', '高一', '高二', '高三')
ALIASES = {'初一': '七年级', '初二': '八年级', '初三': '九年级'}


def canonical(value, *, blank=False):
    text = '' if value is None else str(value).strip()
    if not text and blank:
        return None
    result = ALIASES.get(text, text)
    if result not in GRADES:
        raise RuntimeError(f'未知年级: {text!r}')
    return result


def forwards(apps, schema_editor):
    User = apps.get_model('users', 'CustomUser')
    seen = {}
    updates = []
    for user in User.objects.all().iterator():
        if user.role == 'student' and not user.is_superuser:
            grade = canonical(user.grade)
            class_num = '' if user.class_num is None else str(user.class_num).strip()
            student_number = '' if user.student_number is None else str(user.student_number).strip()
            if not class_num or not student_number:
                raise RuntimeError(f'学生 {user.pk} 的班级或学号为空')
            key = (grade, class_num, student_number)
            if key in seen:
                raise RuntimeError(f'规范化后学生身份冲突: {seen[key]} 与 {user.pk}')
            seen[key] = user.pk
            user.grade, user.class_num, user.student_number = key
        elif user.role == 'teacher':
            user.grade = user.class_num = user.student_number = None
            user.managed_grade = canonical(user.managed_grade, blank=True)
        updates.append(user)
    if updates:
        User.objects.bulk_update(
            updates, ['grade', 'class_num', 'student_number', 'managed_grade'],
        )


class Migration(migrations.Migration):
    dependencies = [('users', '0007_remove_plain_password')]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='customuser', name='grade',
            field=models.CharField(
                blank=True,
                choices=[(grade, grade) for grade in GRADES],
                max_length=10, null=True, verbose_name='年级',
            ),
        ),
        migrations.AlterField(
            model_name='customuser', name='managed_grade',
            field=models.CharField(
                blank=True,
                choices=[(grade, grade) for grade in GRADES],
                max_length=10, null=True, verbose_name='管理年级',
            ),
        ),
        migrations.AddConstraint(
            model_name='customuser',
            constraint=models.UniqueConstraint(
                fields=('grade', 'class_num', 'student_number'),
                name='users_unique_student_identity',
            ),
        ),
        migrations.AddConstraint(
            model_name='customuser',
            constraint=models.CheckConstraint(
                condition=(
                    ~models.Q(role='student')
                    | models.Q(is_superuser=True)
                    | (
                        models.Q(grade__isnull=False) & ~models.Q(grade='')
                        & models.Q(class_num__isnull=False) & ~models.Q(class_num='')
                        & models.Q(student_number__isnull=False) & ~models.Q(student_number='')
                    )
                ),
                name='users_student_identity_required',
            ),
        ),
        migrations.AddConstraint(
            model_name='customuser',
            constraint=models.CheckConstraint(
                condition=(
                    ~models.Q(role='teacher')
                    | (
                        models.Q(grade__isnull=True)
                        & models.Q(class_num__isnull=True)
                        & models.Q(student_number__isnull=True)
                    )
                ),
                name='users_teacher_identity_is_null',
            ),
        ),
    ]
