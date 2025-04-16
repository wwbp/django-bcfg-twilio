# Generated by Django 5.1.8 on 2025-04-16 14:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0032_groupsession_current_strategy_phase_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="groupchattranscript",
            name="assistant_strategy_phase",
            field=models.CharField(
                choices=[
                    ("before_audience", "Before Audience"),
                    ("after_audience", "After Audience"),
                    ("after_reminder", "After Reminder"),
                    ("after_followup", "After Followup"),
                    ("after_summary", "After Summary"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="historicalgroupchattranscript",
            name="assistant_strategy_phase",
            field=models.CharField(
                choices=[
                    ("before_audience", "Before Audience"),
                    ("after_audience", "After Audience"),
                    ("after_reminder", "After Reminder"),
                    ("after_followup", "After Followup"),
                    ("after_summary", "After Summary"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="grouppipelinerecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("INGEST_PASSED", "Ingest Passed"),
                    ("MODERATION_BLOCKED", "Moderation Blocked"),
                    ("MODERATION_PASSED", "Moderation Passed"),
                    ("PROCESS_PASSED", "Process Passed"),
                    ("PROCESS_SKIPPED", "Process Skipped"),
                    ("PROCESS_NOTHING_TO_DO", "Process Nothing To Do"),
                    ("SEND_PASSED", "Send Passed"),
                    ("SCHEDULED_ACTION", "Scheduled Action"),
                    ("FAILED", "Failed"),
                ],
                default="INGEST_PASSED",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="historicalgrouppipelinerecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("INGEST_PASSED", "Ingest Passed"),
                    ("MODERATION_BLOCKED", "Moderation Blocked"),
                    ("MODERATION_PASSED", "Moderation Passed"),
                    ("PROCESS_PASSED", "Process Passed"),
                    ("PROCESS_SKIPPED", "Process Skipped"),
                    ("PROCESS_NOTHING_TO_DO", "Process Nothing To Do"),
                    ("SEND_PASSED", "Send Passed"),
                    ("SCHEDULED_ACTION", "Scheduled Action"),
                    ("FAILED", "Failed"),
                ],
                default="INGEST_PASSED",
                max_length=50,
            ),
        ),
    ]
