# Generated by Django 5.1.8 on 2025-04-18 12:25

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0039_auto_20250417_2001"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameModel(
            old_name="HistoricalPrompt",
            new_name="HistoricalIndividualPrompt",
        ),
        migrations.RenameModel(
            old_name="Prompt",
            new_name="IndividualPrompt",
        ),
        migrations.AlterModelOptions(
            name="historicalindividualprompt",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "historical individual prompt",
                "verbose_name_plural": "historical Weekly Prompts",
            },
        ),
    ]
