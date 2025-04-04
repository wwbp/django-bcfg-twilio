import pytest
from chat.models import MessageType, User, Control, Prompt
from chat.services.crud import load_instruction_prompt, INSTRUCTION_PROMPT_TEMPLATE


def test_load_instruction_prompt_with_existing_user_and_prompt():
    """
    When a user exists and a Prompt for the user's week is available,
    the function should use the Prompt's activity.
    """
    # Create a user with a valid week and a non-empty school mascot.
    user = User.objects.create(id="user1", week_number=3, school_mascot="Hawks", message_type=MessageType.INITIAL)
    # Create a Control record.
    control = Control.objects.create(system="System A", persona="Persona A", default="Default Activity A")
    # Create a Prompt for the user's week.
    prompt = Prompt.objects.create(week=3, type=MessageType.INITIAL, activity="Custom Activity for Week 3")

    result = load_instruction_prompt("user1")
    expected = INSTRUCTION_PROMPT_TEMPLATE.format(
        system=control.system,
        persona=control.persona,
        assistant_name=user.school_mascot,
        activity=prompt.activity,
    )
    assert result == expected


def test_load_instruction_prompt_with_existing_user_and_no_matching_type_prompt():
    """
    When a user exists and a Prompt for the user's seesion is unavailable,
    the function should raise a ValueError.
    """
    # Create a user with a valid week and a non-empty school mascot.
    user = User.objects.create(id="user1", week_number=3, school_mascot="Hawks", message_type=MessageType.SUMMARY)
    # Create a Control record.
    control = Control.objects.create(system="System A", persona="Persona A", default="Default Activity A")
    # Create a Prompt for the user's week.
    prompt = Prompt.objects.create(week=3, type=MessageType.INITIAL, activity="Custom Activity for Week 3")

    with pytest.raises(ValueError):
        load_instruction_prompt("user1")
    
    


def test_load_instruction_prompt_with_existing_user_no_prompt():
    """
    When a user exists but there is no matching Prompt for their week,
    the function should fall back to using the Control's default activity.
    """
    user = User.objects.create(id="user2", week_number=2, school_mascot="Lions", message_type=MessageType.INITIAL)
    control = Control.objects.create(system="System B", persona="Persona B", default="Default Activity B")
    # Do not create a Prompt for week 2.

    with pytest.raises(ValueError):
        load_instruction_prompt("user2")


def test_load_instruction_prompt_with_empty_school_mascot():
    """
    When a user has an empty school mascot, the function should fall back to
    the default assistant name ("Assistant") in the prompt.
    """
    user = User.objects.create(
        id="user3", week_number=1, school_mascot="", message_type=MessageType.INITIAL
    )  # empty mascot
    control = Control.objects.create(system="System D", persona="Persona D", default="Default Activity D")
    prompt = Prompt.objects.create(week=1, type="initial", activity="Activity D")

    result = load_instruction_prompt("user3")
    expected = INSTRUCTION_PROMPT_TEMPLATE.format(
        system=control.system,
        persona=control.persona,
        assistant_name="Assistant",  # fallback value
        activity=prompt.activity,
    )
    assert result == expected
