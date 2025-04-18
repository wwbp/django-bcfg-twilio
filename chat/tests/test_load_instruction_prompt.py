import pytest
from chat.models import ControlConfig, MessageType, User, IndividualPrompt, IndividualSession
from chat.services.individual_crud import load_instruction_prompt, INSTRUCTION_PROMPT_TEMPLATE


def test_load_instruction_prompt_with_existing_user_and_prompt():
    """
    When a user exists and a Prompt for the user's week is available,
    the function should use the Prompt's activity.
    """
    # Create a user with a valid week and a non-empty school mascot.
    user = User.objects.create(school_mascot="Hawks")
    session = IndividualSession.objects.create(
        user=user,
        week_number=3,
        message_type=MessageType.INITIAL,
    )
    # Create ControlConfig records
    persona = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="test persona prompt"
    )
    system = ControlConfig.objects.create(key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT, value="test system prompt")
    # Create a Prompt for the user's week.
    prompt = IndividualPrompt.objects.create(
        week=3, message_type=MessageType.INITIAL, activity="Custom Activity for Week 3"
    )

    result = load_instruction_prompt(user)
    expected = INSTRUCTION_PROMPT_TEMPLATE.format(
        system=system.value,
        persona=persona.value,
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
    user = User.objects.create(school_mascot="Hawks")
    session = IndividualSession.objects.create(
        user=user,
        week_number=3,
        message_type=MessageType.SUMMARY,
    )
    # Create ControlConfig records
    ControlConfig.objects.create(key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="test persona prompt")
    ControlConfig.objects.create(key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT, value="test system prompt")

    # Create a Prompt for the user's week.
    IndividualPrompt.objects.create(week=3, message_type=MessageType.INITIAL, activity="Custom Activity for Week 3")

    with pytest.raises(IndividualPrompt.DoesNotExist):
        load_instruction_prompt(user)


def test_load_instruction_prompt_with_existing_user_no_prompt():
    """
    When a user exists but there is no matching Prompt for their week,
    the function should fall back to using the ControlConfig's default activity.
    """
    user = User.objects.create(school_mascot="Lions")
    session = IndividualSession.objects.create(
        user=user,
        week_number=2,
        message_type=MessageType.INITIAL,
    )
    ControlConfig.objects.create(key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="test persona prompt")
    ControlConfig.objects.create(key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT, value="test system prompt")
    # Do not create a Prompt for week 2.

    with pytest.raises(IndividualPrompt.DoesNotExist):
        load_instruction_prompt(user)


def test_load_instruction_prompt_with_empty_school_mascot():
    """
    When a user has an empty school mascot, the function should fall back to
    the default assistant name ("Assistant") in the prompt.
    """
    user = User.objects.create(school_mascot="")
    session = IndividualSession.objects.create(
        user=user,
        week_number=1,
        message_type=MessageType.INITIAL,
    )
    persona = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="test persona prompt"
    )
    system = ControlConfig.objects.create(key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT, value="test system prompt")
    prompt = IndividualPrompt.objects.create(week=1, message_type=MessageType.INITIAL, activity="Activity D")

    result = load_instruction_prompt(user)
    expected = INSTRUCTION_PROMPT_TEMPLATE.format(
        system=system.value,
        persona=persona.value,
        assistant_name="Assistant",  # fallback value
        activity=prompt.activity,
    )
    assert result == expected
