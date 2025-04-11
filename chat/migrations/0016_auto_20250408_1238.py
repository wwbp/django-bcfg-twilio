from django.db import migrations
from django.contrib.auth.models import Group
from admin.models import AuthGroupName

def create_groups(apps, schema_editor):
    # Get models through apps registry
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    # Create groups
    standard_user = Group.objects.create(name=AuthGroupName.StandardUser.value)
    user_manager = Group.objects.create(name=AuthGroupName.UserManager.value)
    unlock_restricted = Group.objects.create(name=AuthGroupName.UnlockRestrictedContent.value)
    
    # User Manager permissions
    user_manager_perms = Permission.objects.filter(
        codename__in=['add_user', 'change_user', 'delete_user', 'view_user'],
        content_type__app_label='auth'
    )
    user_manager.permissions.add(*user_manager_perms)

    # Standard User - explicit model permissions
    standard_perm_models = [
        "user",
        "group",
        "chattranscript",
        "groupchattranscript",
        "prompt",
        "control",
        "summary",
    ]

    # Get all CRUD permissions for allowed models
    standard_perms = Permission.objects.filter(
        codename__regex=rf'^(add|change|delete|view)_({"|".join(standard_perm_models)})$',
        content_type__app_label='chat'
    )

    # Still exclude any historical variants
    standard_perms = standard_perms.exclude(codename__contains='historical')
    standard_user.permissions.add(*standard_perms)    

def remove_groups(apps, schema_editor):
    Group.objects.filter(
        name__in=[
            AuthGroupName.StandardUser.value,
            AuthGroupName.UserManager.value,
            AuthGroupName.UnlockRestrictedContent.value
        ]
    ).delete()

class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0015_remove_individualpipelinerecord_failed_and_more"),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]