import pytest
from chat.models import ControlConfig, MessageType, User, IndividualPrompt, IndividualSession
from chat.services.individual_crud import (
    load_instruction_prompt,
    load_instruction_prompt_for_direct_messaging,
)

INSTRUCTION_PROMPT_TEMPLATE = (
    "Using the below system prompt as your guide, engage with the user in a "
    "manner that reflects your assigned persona and follows the activity instructions"
    "System Prompt: {system}\n\n"
    "Assigned Persona: {persona}\n\n"
    "Assistant Name: {assistant_name}\n\n"
    "User's School: {school_name}\n\n"
    "Activity: {activity}\n\n"
)


def test_load_instruction_prompt_with_existing_user_and_prompt(control_config_factory):
    """
    When a user exists and a Prompt for the user's week is available,
    the function should use the Prompt's activity.
    """
    # Create a user with a valid week and a non-empty school mascot.
    user = User.objects.create(school_mascot="Hawks", school_name="Nest")
    session = IndividualSession.objects.create(
        user=user,
        week_number=3,
        message_type=MessageType.INITIAL,
    )
    # Create ControlConfig records
    persona = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.PERSONA_PROMPT,
        value="test persona prompt",
    )
    system = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT,
        value="test system prompt",
    )
    instruction_prompt = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.INSTRUCTION_PROMPT_TEMPLATE,
        value=INSTRUCTION_PROMPT_TEMPLATE,
    )
    # Create a Prompt for the user's week.
    prompt = IndividualPrompt.objects.create(
        week=3,
        message_type=MessageType.INITIAL,
        activity="Custom Activity for Week 3",
    )

    result = load_instruction_prompt(user)
    expected = instruction_prompt.value.format(
        system=system.value,
        persona=persona.value,
        assistant_name=user.school_mascot,
        school_name=user.school_name,
        activity=prompt.activity,
    )
    assert result == expected


def test_load_instruction_prompt_with_existing_user_and_no_matching_type_prompt(control_config_factory):
    """
    When a user exists and a Prompt for the user's session is unavailable,
    the function should raise a DoesNotExist.
    """
    user = User.objects.create(school_mascot="Hawks", school_name="Nest")
    session = IndividualSession.objects.create(
        user=user,
        week_number=3,
        message_type=MessageType.SUMMARY,
    )
    control_config_factory(key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="test persona prompt")
    control_config_factory(key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT, value="test system prompt")
    instruction_prompt = control_config_factory(
        key=ControlConfig.ControlConfigKey.INSTRUCTION_PROMPT_TEMPLATE,
        value=INSTRUCTION_PROMPT_TEMPLATE,
    )

    IndividualPrompt.objects.create(
        week=3,
        message_type=MessageType.INITIAL,
        activity="Custom Activity for Week 3",
    )

    with pytest.raises(IndividualPrompt.DoesNotExist):
        load_instruction_prompt(user)


def test_load_instruction_prompt_with_existing_user_no_prompt(control_config_factory):
    """
    When a user exists but there is no matching Prompt for their week,
    the function should raise DoesNotExist.
    """
    user = User.objects.create(school_mascot="Lions", school_name="Nest")
    session = IndividualSession.objects.create(
        user=user,
        week_number=2,
        message_type=MessageType.INITIAL,
    )
    control_config_factory(key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="test persona prompt")
    control_config_factory(key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT, value="test system prompt")
    instruction_prompt = control_config_factory(
        key=ControlConfig.ControlConfigKey.INSTRUCTION_PROMPT_TEMPLATE,
        value=INSTRUCTION_PROMPT_TEMPLATE,
    )

    with pytest.raises(IndividualPrompt.DoesNotExist):
        load_instruction_prompt(user)


def test_load_instruction_prompt_with_empty_school_mascot(control_config_factory):
    """
    When a user has an empty school mascot, the function should fall back to
    the default assistant name ("Assistant") in the prompt.
    """
    user = User.objects.create(school_mascot="", school_name="Nest")
    session = IndividualSession.objects.create(
        user=user,
        week_number=1,
        message_type=MessageType.INITIAL,
    )
    persona = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.PERSONA_PROMPT,
        value="test persona prompt",
    )
    system = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT,
        value="test system prompt",
    )
    instruction_prompt = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.INSTRUCTION_PROMPT_TEMPLATE,
        value=INSTRUCTION_PROMPT_TEMPLATE,
    )
    prompt = IndividualPrompt.objects.create(
        week=1,
        message_type=MessageType.INITIAL,
        activity="Activity D",
    )

    result = load_instruction_prompt(user)
    expected = instruction_prompt.value.format(
        system=system.value,
        persona=persona.value,
        assistant_name="Assistant",
        school_name=user.school_name,
        activity=prompt.activity,
    )
    assert result == expected


# Tests for load_instruction_prompt_for_direct_messaging


def test_load_instruction_prompt_for_direct_messaging_with_existing_user_and_prompt(control_config_factory):
    """
    When a user exists and a Prompt for direct messaging is available,
    the function should use the GROUP_DIRECT_MESSAGE_PERSONA_PROMPT config.
    """
    # Create a user with a valid week and a non-empty school mascot.
    user = User.objects.create(school_mascot="Falcons", school_name="Nest")
    session = IndividualSession.objects.create(
        user=user,
        week_number=5,
        message_type=MessageType.INITIAL,
    )
    # Create ControlConfig records for direct messaging persona and system
    persona = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.GROUP_DIRECT_MESSAGE_PERSONA_PROMPT,
        value="dm persona prompt",
    )
    system = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT,
        value="dm system prompt",
    )
    instruction_prompt = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.INSTRUCTION_PROMPT_TEMPLATE,
        value=INSTRUCTION_PROMPT_TEMPLATE,
    )
    # Create a Prompt for the user's week and type
    prompt = IndividualPrompt.objects.create(
        week=5,
        message_type=MessageType.INITIAL,
        activity="DM Activity for Week 5",
    )

    result = load_instruction_prompt_for_direct_messaging(user)
    expected = instruction_prompt.value.format(
        system=system.value,
        persona=persona.value,
        assistant_name=user.school_mascot,
        school_name=user.school_name,
        activity=prompt.activity,
    )
    assert result == expected


def test_load_instruction_prompt_for_direct_messaging_missing_control_config(control_config_factory):
    """
    When persona or system config is missing, the function should raise ValueError.
    """
    user = User.objects.create(school_mascot="Falcons", school_name="Nest")
    session = IndividualSession.objects.create(
        user=user,
        week_number=5,
        message_type=MessageType.INITIAL,
    )
    # Only create one of the required ControlConfig
    ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.GROUP_DIRECT_MESSAGE_PERSONA_PROMPT,
        value="dm persona prompt",
    )
    instruction_prompt = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.INSTRUCTION_PROMPT_TEMPLATE,
        value=INSTRUCTION_PROMPT_TEMPLATE,
    )
    # Missing SYSTEM_PROMPT

    with pytest.raises(ValueError) as excinfo:
        load_instruction_prompt_for_direct_messaging(user)
    assert "System or Persona prompt not found" in str(excinfo.value)


def test_load_instruction_prompt_for_direct_messaging_with_no_prompt(control_config_factory):
    """
    When there is no IndividualPrompt for the user's session, the function should raise DoesNotExist.
    """
    user = User.objects.create(school_mascot="Falcons", school_name="Nest")
    session = IndividualSession.objects.create(
        user=user,
        week_number=6,
        message_type=MessageType.SUMMARY,
    )
    ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.GROUP_DIRECT_MESSAGE_PERSONA_PROMPT,
        value="dm persona prompt",
    )
    ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT,
        value="dm system prompt",
    )
    instruction_prompt = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.INSTRUCTION_PROMPT_TEMPLATE,
        value=INSTRUCTION_PROMPT_TEMPLATE,
    )
    # No IndividualPrompt for week 6 and SUMMARY

    with pytest.raises(IndividualPrompt.DoesNotExist):
        load_instruction_prompt_for_direct_messaging(user)


def test_load_instruction_prompt_for_direct_messaging_with_empty_school_mascot(control_config_factory):
    """
    When a user has an empty school mascot, the function should fall back to
    the default assistant name ("Assistant") in the direct messaging prompt.
    """
    user = User.objects.create(school_mascot="", school_name="Nest")
    session = IndividualSession.objects.create(
        user=user,
        week_number=2,
        message_type=MessageType.INITIAL,
    )
    persona = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.GROUP_DIRECT_MESSAGE_PERSONA_PROMPT,
        value="dm persona prompt",
    )
    system = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT,
        value="dm system prompt",
    )
    instruction_prompt = ControlConfig.objects.create(
        key=ControlConfig.ControlConfigKey.INSTRUCTION_PROMPT_TEMPLATE,
        value=INSTRUCTION_PROMPT_TEMPLATE,
    )
    prompt = IndividualPrompt.objects.create(
        week=2,
        message_type=MessageType.INITIAL,
        activity="DM Activity for Week 2",
    )

    result = load_instruction_prompt_for_direct_messaging(user)
    expected = instruction_prompt.value.format(
        system=system.value,
        persona=persona.value,
        assistant_name="Assistant",
        school_name=user.school_name,
        activity=prompt.activity,
    )
    assert result == expected
