import pytest
from chat.models import (
    ControlConfig,
    MessageType,
    User,
    Group,
    GroupSession,
    GroupStrategyPhase,
    BaseChatTranscript,
)
from chat.services.group_crud import load_instruction_prompt

GROUP_INSTRUCTION_PROMPT_TEMPLATE = (
    "Using the below system prompt as your guide, engage with the group as a participant in a "
    "manner that reflects your assigned persona and follows the conversation stategy instructions"
    "System Prompt: {system}\n\n"
    "Assigned Persona: {persona}\n\n"
    "Assistant Name: {assistant_name}\n\n"
    "Group's School: {school_name}\n\n"
    "Strategy: {strategy}\n\n"
)


def test_load_group_instruction_prompt_with_existing_user_and_prompt(group_prompt_factory, control_config_factory):
    """
    When a group has at least one user and there is a matching Prompt
    (week + strategy phase + is_for_group),
    _load_instruction_prompt should return the correctly formatted string.
    """
    group = Group.objects.create(id="group1")
    user = User.objects.create(
        name="Alice",
        school_mascot="Panthers",
        school_name="River High",
        group=group,
    )
    session = GroupSession.objects.create(
        group=group,
        week_number=5,
        message_type=MessageType.INITIAL,
    )

    # latest Control via factory
    control_config_factory(key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="Persona Y")
    control_config_factory(key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT, value="System X")
    instruction_prompt = control_config_factory(
        key=ControlConfig.ControlConfigKey.GROUP_INSTRUCTION_PROMPT_TEMPLATE,
        value=GROUP_INSTRUCTION_PROMPT_TEMPLATE,
    )

    # matching Prompt via factory

    control_config_factory(
        key=ControlConfig.ControlConfigKey.GROUP_AUDIENCE_STRATEGY_PROMPT,
        value="Discuss your goals for this week.",
    )

    result = load_instruction_prompt(session, GroupStrategyPhase.AUDIENCE)
    expected = instruction_prompt.value.format(
        system="System X",
        persona="Persona Y",
        assistant_name=user.school_mascot,
        school_name=user.school_name,
        strategy="Discuss your goals for this week.",
    )
    assert result == expected


def test_load_group_instruction_prompt_raises_when_no_prompt(control_config_factory):
    """
    If there is no Prompt matching the session’s week and given phase,
    _load_instruction_prompt must raise ValueError.
    """
    group = Group.objects.create()
    User.objects.create(
        name="Bob",
        school_mascot="Bears",
        school_name="Hillview",
        group=group,
    )
    session = GroupSession.objects.create(
        group=group,
        week_number=2,
        message_type=MessageType.INITIAL,
    )

    control_config_factory(key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="P")
    control_config_factory(key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT, value="S")
    instruction_prompt = control_config_factory(
        key=ControlConfig.ControlConfigKey.GROUP_INSTRUCTION_PROMPT_TEMPLATE,
        value=GROUP_INSTRUCTION_PROMPT_TEMPLATE,
    )

    with pytest.raises(ValueError) as exc:
        load_instruction_prompt(session, GroupStrategyPhase.AUDIENCE)

    assert "GROUP_AUDIENCE_STRATEGY_PROMPT not found in ControlConfig" in str(exc.value)


def test_load_group_instruction_prompt_falls_back_to_assistant_name_when_no_user(
    group_prompt_factory, control_config_factory
):
    """
    If the group has no users at all, assistant_name should fall back
    to BaseChatTranscript.Role.ASSISTANT.
    """
    group = Group.objects.create()
    session = GroupSession.objects.create(
        group=group,
        week_number=1,
        message_type=MessageType.INITIAL,
    )

    control_config_factory(key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT, value="Sys1")
    control_config_factory(key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="Pers1")
    instruction_prompt = control_config_factory(
        key=ControlConfig.ControlConfigKey.GROUP_INSTRUCTION_PROMPT_TEMPLATE,
        value=GROUP_INSTRUCTION_PROMPT_TEMPLATE,
    )

    group_prompt_factory(
        week=1,
        strategy_type=GroupStrategyPhase.FOLLOWUP,
        activity="Reflect on your wins.",
    )

    result = load_instruction_prompt(session, GroupStrategyPhase.FOLLOWUP)
    expected = instruction_prompt.value.format(
        system="Sys1",
        persona="Pers1",
        assistant_name=BaseChatTranscript.Role.ASSISTANT,
        school_name="",
        strategy="Reflect on your wins.",
    )
    assert result == expected
