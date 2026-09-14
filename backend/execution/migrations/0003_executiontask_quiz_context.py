# Generated for AI mixed quiz Step 5.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ai_courses', '0010_submission_quiz_context'),
        ('execution', '0002_runnerrequestreceipt'),
    ]

    operations = [
        migrations.AddField(
            model_name='executiontask',
            name='quiz_attempt',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='execution_tasks', to='ai_courses.aiquizattempt'),
        ),
        migrations.AddField(
            model_name='executiontask',
            name='quiz_item_id',
            field=models.CharField(blank=True, db_index=True, max_length=36),
        ),
        migrations.AddConstraint(
            model_name='executiontask',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(('quiz_attempt__isnull', True), ('quiz_item_id', '')),
                    models.Q(('quiz_attempt__isnull', False), models.Q(('quiz_item_id', ''), _negated=True)),
                    _connector='OR',
                ),
                name='execution_quiz_context_pair',
            ),
        ),
        migrations.AddIndex(
            model_name='executiontask',
            index=models.Index(fields=['quiz_attempt', 'quiz_item_id'], name='exec_quiz_item_idx'),
        ),
    ]
