# Generated by Django 5.1.8 on 2025-04-09 21:09

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0023_chattranscript_session"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="chattranscript",
            name="user",
        ),
        
        # make the following non-nullable
        migrations.AlterField(
            model_name="chattranscript",
            name="session",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="transcripts",
                to="chat.individualsession",
            ),
        ),
    ]
