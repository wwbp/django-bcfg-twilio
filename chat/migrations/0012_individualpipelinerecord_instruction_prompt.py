# Generated by Django 5.1.7 on 2025-03-20 16:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0011_individualpipelinerecord_message_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='individualpipelinerecord',
            name='instruction_prompt',
            field=models.TextField(blank=True, null=True),
        ),
    ]
