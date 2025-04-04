# Generated by Django 5.1.7 on 2025-03-11 17:22

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0008_strategyprompt_who_prompt_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='IndividualPipelineRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('run_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('participant_id', models.CharField(max_length=255)),
                ('ingested', models.BooleanField(default=False)),
                ('processed', models.BooleanField(default=False)),
                ('sent', models.BooleanField(default=False)),
                ('failed', models.BooleanField(default=False)),
                ('error_log', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddField(
            model_name='user',
            name='week_number',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
