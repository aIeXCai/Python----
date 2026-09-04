# Generated manually for the Stage 5 Runner private protocol.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('execution', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RunnerRequestReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('runner_id', models.CharField(max_length=100)),
                ('request_id', models.UUIDField()),
                ('endpoint', models.CharField(max_length=200)),
                ('request_hash', models.CharField(max_length=64)),
                ('response_status', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('response_body', models.JSONField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'indexes': [models.Index(fields=['created_at'], name='runner_receipt_created_idx')],
                'constraints': [models.UniqueConstraint(fields=('runner_id', 'request_id'), name='runner_request_unique_id')],
            },
        ),
    ]
