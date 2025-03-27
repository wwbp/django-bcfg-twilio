import pytest
from chat.models import User, Control, Prompt
from chat.crud import load_instruction_prompt, INSTRUCTION_PROMPT_TEMPLATE


@pytest.mark.django_db
def test_load_instruction_prompt_with_existing_user_and_prompt():
    """
    When a user exists and a Prompt for the user's week is available,
    the function should use the Prompt's activity.
    """
    # Create a user with a valid week and a non-empty school mascot.
    user = User.objects.create(id="user1", week_number=3, school_mascot="Hawks")
    # Create a Control record.
    control = Control.objects.create(system="System A", persona="Persona A", default="Default Activity A")
    # Create a Prompt for the user's week.
    prompt = Prompt.objects.create(week=3, activity="Custom Activity for Week 3")

    result = load_instruction_prompt("user1")
    expected = INSTRUCTION_PROMPT_TEMPLATE.format(
        system=control.system,
        persona=control.persona,
        assistant_name=user.school_mascot,
        activity=prompt.activity,
    )
    assert result == expected


@pytest.mark.django_db
def test_load_instruction_prompt_with_existing_user_no_prompt():
    """
    When a user exists but there is no matching Prompt for their week,
    the function should fall back to using the Control's default activity.
    """
    user = User.objects.create(id="user2", week_number=2, school_mascot="Lions")
    control = Control.objects.create(system="System B", persona="Persona B", default="Default Activity B")
    # Do not create a Prompt for week 2.

    result = load_instruction_prompt("user2")
    expected = INSTRUCTION_PROMPT_TEMPLATE.format(
        system=control.system,
        persona=control.persona,
        assistant_name=user.school_mascot,
        activity=control.default,
    )
    assert result == expected


@pytest.mark.django_db
def test_load_instruction_prompt_user_does_not_exist():
    """
    When the user does not exist, the function should use the default assistant name
    and the Control's default activity.
    """
    control = Control.objects.create(system="System C", persona="Persona C", default="Default Activity C")
    # No user is created.
    result = load_instruction_prompt("nonexistent_user")
    expected = INSTRUCTION_PROMPT_TEMPLATE.format(
        system=control.system,
        persona=control.persona,
        assistant_name="Assistant",
        activity=control.default,
    )
    assert result == expected


@pytest.mark.django_db
def test_load_instruction_prompt_with_empty_school_mascot():
    """
    When a user has an empty school mascot, the function should fall back to
    the default assistant name ("Assistant") in the prompt.
    """
    user = User.objects.create(id="user3", week_number=1, school_mascot="")  # empty mascot
    control = Control.objects.create(system="System D", persona="Persona D", default="Default Activity D")
    prompt = Prompt.objects.create(week=1, activity="Activity D")

    result = load_instruction_prompt("user3")
    expected = INSTRUCTION_PROMPT_TEMPLATE.format(
        system=control.system,
        persona=control.persona,
        assistant_name="Assistant",  # fallback value
        activity=prompt.activity,
    )
    assert result == expected
