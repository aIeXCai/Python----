from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_courses', '0005_problem_publication'),
    ]

    operations = [
        migrations.AddField(
            model_name='problem',
            name='grade_tag',
            field=models.CharField(
                blank=True,
                choices=[
                    ('七年级', '七年级'),
                    ('八年级', '八年级'),
                    ('九年级', '九年级'),
                    ('高一', '高一'),
                    ('高二', '高二'),
                    ('高三', '高三'),
                ],
                db_index=True,
                default='',
                max_length=10,
                verbose_name='适用年级标签',
            ),
        ),
    ]
