import os
from unittest.mock import patch
from django.core.management import call_command, CommandError
import pytest

from chat.models import Control, Prompt


def test_clear_all_prompts_works_only_dev(control_factory, prompt_factory):
    control_factory()
    prompt_factory.create_batch(2)
    with patch.dict(os.environ, {"DJANGO_ENV": "prod"}):
        with pytest.raises(CommandError) as e:
            call_command("clear_all_prompts")
    assert Prompt.objects.count() == 2
    assert Control.objects.count() == 1
    assert "This command can only be run in a development environment." in str(e)


def test_clear_all_prompts(control_factory, prompt_factory):
    control_factory()
    prompt_factory.create_batch(2)
    with patch.dict(os.environ, {"DJANGO_ENV": "dev"}), patch("builtins.input", return_value="yes"):
        call_command("clear_all_prompts")
    assert Prompt.objects.count() == 0
    assert Control.objects.count() == 0


def test_clear_all_prompts_user_does_not_confirm(control_factory, prompt_factory):
    control_factory()
    prompt_factory.create_batch(2)
    with patch.dict(os.environ, {"DJANGO_ENV": "dev"}), patch("builtins.input", return_value="no"):
        with pytest.raises(CommandError) as e:
            call_command("clear_all_prompts")
    assert Prompt.objects.count() == 2
    assert Control.objects.count() == 1
    assert "Operation cancelled" in str(e)
