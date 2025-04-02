# Generated by Django 5.1.7 on 2025-04-02 19:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0014_prompt_type_user_message_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="prompt",
            name="type",
            field=models.CharField(
                choices=[
                    ("initial", "Initial"),
                    ("reminder", "Reminder"),
                    ("check-in", "Check-in"),
                    ("summary", "Summary"),
                ],
                default="initial",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="message_type",
            field=models.CharField(
                choices=[
                    ("initial", "Initial"),
                    ("reminder", "Reminder"),
                    ("check-in", "Check-in"),
                    ("summary", "Summary"),
                ],
                default="initial",
                max_length=20,
            ),
        ),
    ]
