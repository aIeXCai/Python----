from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('info_tech', '0006_quizsession_visible_classes'),
    ]

    operations = [
        migrations.AddField(
            model_name='quizsession',
            name='archived_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='删除归档时间'),
        ),
    ]
