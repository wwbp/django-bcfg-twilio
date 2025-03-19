# Generated by Django 5.1.7 on 2025-03-19 18:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0010_grouppipelinerecord_group_initial_message_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='individualpipelinerecord',
            name='message',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='individualpipelinerecord',
            name='moderated',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='individualpipelinerecord',
            name='response',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='individualpipelinerecord',
            name='shortened',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='individualpipelinerecord',
            name='validated_message',
            field=models.TextField(blank=True, null=True),
        ),
    ]
