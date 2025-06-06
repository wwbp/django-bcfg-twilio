# Generated by Django 5.1.8 on 2025-04-08 17:56

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0017_alter_chattranscript_options_alter_control_options_and_more"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupScheduledTaskAssociation",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now, editable=False
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="chat.group"
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="django_celery_beat.periodictask",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
