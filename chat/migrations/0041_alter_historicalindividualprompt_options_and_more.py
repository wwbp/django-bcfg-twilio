# Generated by Django 5.1.8 on 2025-04-18 12:26

import django.db.models.deletion
import django.utils.timezone
import simple_history.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0040_rename_historicalprompt_historicalindividualprompt_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="historicalindividualprompt",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "historical individual prompt",
                "verbose_name_plural": "historical Weekly Individual Prompts",
            },
        ),
        migrations.AlterModelOptions(
            name="individualprompt",
            options={
                "ordering": ["week", "message_type", "-created_at"],
                "verbose_name_plural": "Weekly Individual Prompts",
            },
        ),
        migrations.RenameField(
            model_name="historicalindividualprompt",
            old_name="type",
            new_name="message_type",
        ),
        migrations.RenameField(
            model_name="individualprompt",
            old_name="type",
            new_name="message_type",
        ),
        migrations.RemoveField(
            model_name="historicalindividualprompt",
            name="is_for_group",
        ),
        migrations.AlterUniqueTogether(
            name="individualprompt",
            unique_together={("week", "message_type")},
        ),
        migrations.CreateModel(
            name="GroupPrompt",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now, editable=False
                    ),
                ),
                ("week", models.IntegerField()),
                ("activity", models.TextField()),
                (
                    "strategy_type",
                    models.CharField(
                        choices=[
                            ("before_audience", "Before Audience"),
                            ("audience", "Audience"),
                            ("after_audience", "After Audience"),
                            ("reminder", "Reminder"),
                            ("after_reminder", "After Reminder"),
                            ("followup", "Followup"),
                            ("after_followup", "After Followup"),
                            ("summary", "Summary"),
                            ("after_summary", "After Summary"),
                        ],
                        default="audience",
                        max_length=20,
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Weekly Group Prompts",
                "ordering": ["week", "strategy_type", "-created_at"],
                "unique_together": {("week", "strategy_type")},
            },
        ),
        migrations.CreateModel(
            name="HistoricalGroupPrompt",
            fields=[
                (
                    "id",
                    models.BigIntegerField(
                        auto_created=True, blank=True, db_index=True, verbose_name="ID"
                    ),
                ),
                ("week", models.IntegerField()),
                ("activity", models.TextField()),
                (
                    "strategy_type",
                    models.CharField(
                        choices=[
                            ("before_audience", "Before Audience"),
                            ("audience", "Audience"),
                            ("after_audience", "After Audience"),
                            ("reminder", "Reminder"),
                            ("after_reminder", "After Reminder"),
                            ("followup", "Followup"),
                            ("after_followup", "After Followup"),
                            ("summary", "Summary"),
                            ("after_summary", "After Summary"),
                        ],
                        default="audience",
                        max_length=20,
                    ),
                ),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                (
                    "history_type",
                    models.CharField(
                        choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                        max_length=1,
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "historical group prompt",
                "verbose_name_plural": "historical Weekly Group Prompts",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.RemoveField(
            model_name="individualprompt",
            name="is_for_group",
        ),
    ]
