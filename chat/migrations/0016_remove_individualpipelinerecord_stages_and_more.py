# Generated by Django 5.2 on 2025-04-03 20:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0015_remove_individualpipelinerecord_failed_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="individualpipelinerecord",
            name="stages",
        ),
        migrations.AddField(
            model_name="individualpipelinerecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("INGEST_PASSED", "Ingest Passed"),
                    ("INGEST_FAILED", "Ingest Failed"),
                    ("MODERATION_BLOCKED", "Moderation Blocked"),
                    ("MODERATION_PASSED", "Moderation Passed"),
                    ("MODERATION_FAILED", "Moderation Failed"),
                    ("PROCESS_PASSED", "Process Passed"),
                    ("PROCESS_SKIPPED", "Process Skipped"),
                    ("PROCESS_FAILED", "Process Failed"),
                    ("VALIDATE_CHARACTER_LIMIT_HIT", "Validate Character Limit Hit"),
                    ("VALIDATE_PASSED", "Validate Passed"),
                    ("VALIDATE_FAILED", "Validate Failed"),
                    ("SEND_PASSED", "Send Passed"),
                    ("SEND_FAILED", "Send Failed"),
                ],
                default="INGEST_PASSED",
                max_length=50,
            ),
        ),
    ]
