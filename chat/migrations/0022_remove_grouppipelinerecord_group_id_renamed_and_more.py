# Generated by Django 5.1.8 on 2025-04-09 20:48

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0021_rename_group_id_grouppipelinerecord_group_id_renamed_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="grouppipelinerecord",
            name="group_id_renamed",
        ),
        migrations.RemoveField(
            model_name="individualpipelinerecord",
            name="participant_id",
        ),
        
        # make the following non-nullable
        migrations.AlterField(
            model_name="grouppipelinerecord",
            name="group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pipeline_records",
                to="chat.group",
            ),
        ),
        migrations.AlterField(
            model_name="individualpipelinerecord",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pipeline_records",
                to="chat.user",
            ),
        ),
    ]
