# Generated by Django 5.1.8 on 2025-04-14 16:18

from django.db import migrations

def clear_group_data(apps, schema_editor):
    GroupPipelineRecord = apps.get_model("chat", "GroupPipelineRecord")
    GroupChatTranscript = apps.get_model("chat", "GroupChatTranscript")
    Group = apps.get_model("chat", "Group")
    
    GroupPipelineRecord.objects.all().delete()
    GroupChatTranscript.objects.all().delete()
    Group.objects.all().delete()


def reverse_clear_group_data(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0027_chattranscript_moderation_status_and_more"),
    ]

    operations = [
        migrations.RunPython(
            clear_group_data,
            reverse_clear_group_data,
        ),
    ]
