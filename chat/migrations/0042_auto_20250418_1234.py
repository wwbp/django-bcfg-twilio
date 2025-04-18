# Generated by Django 5.1.8 on 2025-04-18 12:34

from django.db import migrations

from admin.models import AuthGroupName


def update_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    standard_user, _ = Group.objects.get_or_create(name=AuthGroupName.StandardUser.value)

    standard_perm_models = [
        "user",
        "group",
        "individualchattranscript",
        "groupchattranscript",
        "individualsession",
        "groupsession",
        "individualprompt",
        "groupprompt",
        "controlconfig",
        "summary",
        "groupstrategyphaseconfig",
        "individualpipelinerecord",
        "grouppipelinerecord"
    ]

    # Get all CRUD permissions for allowed models
    standard_perms = Permission.objects.filter(
        codename__regex=rf'^(add|change|delete|view)_({"|".join(standard_perm_models)})$',
        content_type__app_label='chat'
    )

    # Still exclude any historical variants
    standard_perms = standard_perms.exclude(codename__contains='historical')
    standard_user.permissions.add(*standard_perms)    

def reverse_update_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(
        name__in=[
            AuthGroupName.StandardUser.value,
        ]
    ).delete()

class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0041_alter_historicalindividualprompt_options_and_more"),
    ]

    operations = [
        migrations.RunPython(update_group, reverse_update_group),
    ]
