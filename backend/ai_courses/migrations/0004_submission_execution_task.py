import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_courses', '0003_problem_template_code'),
        ('execution', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='execution_task',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='submission', to='execution.executiontask'),
        ),
        migrations.AlterField(
            model_name='submission',
            name='score',
            field=models.FloatField(blank=True, default=0, null=True, verbose_name='得分'),
        ),
    ]
