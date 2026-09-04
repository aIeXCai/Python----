from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('info_tech', '0005_remove_quizsession_is_visible'),
    ]

    operations = [
        migrations.AddField(
            model_name='quizsession',
            name='visible_classes',
            field=models.JSONField(default=list, verbose_name='可见班级'),
        ),
    ]
