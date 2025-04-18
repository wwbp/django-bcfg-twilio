import os
from django.core.management.base import BaseCommand, CommandError

from chat.models import ControlConfig, IndividualPrompt


class Command(BaseCommand):
    help = "Delete all prompts from your system. Proceed with caution!"

    def handle(self, *args, **options):
        if os.environ.get("DJANGO_ENV") != "dev":
            raise CommandError(
                f"This command can only be run in a development environment. Found '{os.environ.get('DJANGO_ENV')}'"
            )

        confirm = input("Are you sure you want to delete all prompts? This cannot be undone. Type 'yes' to confirm: ")
        if confirm.lower() != "yes":
            raise CommandError("Operation cancelled")

        ControlConfig.objects.all().delete()
        IndividualPrompt.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("Successfully cleared all prompts"))
