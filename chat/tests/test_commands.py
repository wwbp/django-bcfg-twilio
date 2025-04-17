import os
from unittest.mock import patch
from django.core.management import call_command, CommandError
import pytest

from chat.models import ControlConfig, Prompt


def test_clear_all_prompts_works_only_dev(prompt_factory):
    ControlConfig.objects.create(key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="test_value")
    prompt_factory.create_batch(2)
    with patch.dict(os.environ, {"DJANGO_ENV": "prod"}):
        with pytest.raises(CommandError) as e:
            call_command("clear_all_prompts")
    assert Prompt.objects.count() == 2
    assert ControlConfig.objects.count() == 1
    assert "This command can only be run in a development environment." in str(e)


def test_clear_all_prompts(prompt_factory):
    ControlConfig.objects.create(key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="test_value")
    prompt_factory.create_batch(2)
    with patch.dict(os.environ, {"DJANGO_ENV": "dev"}), patch("builtins.input", return_value="yes"):
        call_command("clear_all_prompts")
    assert Prompt.objects.count() == 0
    assert ControlConfig.objects.count() == 0


def test_clear_all_prompts_user_does_not_confirm(prompt_factory):
    ControlConfig.objects.create(key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="test_value")
    prompt_factory.create_batch(2)
    with patch.dict(os.environ, {"DJANGO_ENV": "dev"}), patch("builtins.input", return_value="no"):
        with pytest.raises(CommandError) as e:
            call_command("clear_all_prompts")
    assert Prompt.objects.count() == 2
    assert ControlConfig.objects.count() == 1
    assert "Operation cancelled" in str(e)
