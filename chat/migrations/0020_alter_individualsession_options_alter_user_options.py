# Generated by Django 5.1.8 on 2025-04-09 19:51

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0019_alter_user_options_remove_user_initial_message_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="individualsession",
            options={"ordering": ["-created_at"]},
        ),
        migrations.AlterModelOptions(
            name="user",
            options={"ordering": ["-created_at"]},
        ),
    ]
