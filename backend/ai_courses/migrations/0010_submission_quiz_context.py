# Generated for AI mixed quiz Step 5.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ai_courses', '0009_ai_quiz_attempt'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='counts_for_quiz',
            field=models.BooleanField(default=True, verbose_name='计入小测成绩'),
        ),
        migrations.AddField(
            model_name='submission',
            name='quiz_attempt',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='code_submissions', to='ai_courses.aiquizattempt', verbose_name='所属小测作答'),
        ),
        migrations.AddField(
            model_name='submission',
            name='quiz_item_id',
            field=models.CharField(blank=True, db_index=True, max_length=36, verbose_name='小测题目标识'),
        ),
        migrations.AddField(
            model_name='submission',
            name='regrade_of',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='regrades', to='ai_courses.submission', verbose_name='重评来源'),
        ),
        migrations.AddConstraint(
            model_name='submission',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(('quiz_attempt__isnull', True), ('quiz_item_id', '')),
                    models.Q(('quiz_attempt__isnull', False), models.Q(('quiz_item_id', ''), _negated=True)),
                    _connector='OR',
                ),
                name='ai_submission_quiz_context_pair',
            ),
        ),
        migrations.AddIndex(
            model_name='submission',
            index=models.Index(fields=['quiz_attempt', 'quiz_item_id'], name='ai_submission_quiz_item_idx'),
        ),
    ]
