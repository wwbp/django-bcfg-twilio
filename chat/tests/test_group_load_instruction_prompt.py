import pytest
from chat.models import (
    ControlConfig,
    MessageType,
    GroupPrompt,
    User,
    Group,
    GroupSession,
    GroupStrategyPhase,
    BaseChatTranscript,
)
from chat.services.group_crud import load_instruction_prompt, GROUP_INSTRUCTION_PROMPT_TEMPLATE


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

    # matching Prompt via factory
    prompt = group_prompt_factory(
        week=5,
        strategy_type=GroupStrategyPhase.AUDIENCE,
        activity="Discuss your goals for this week.",
    )

    result = load_instruction_prompt(session, GroupStrategyPhase.AUDIENCE)
    expected = GROUP_INSTRUCTION_PROMPT_TEMPLATE.format(
        system="System X",
        persona="Persona Y",
        assistant_name=user.school_mascot,
        strategy=prompt.activity,
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

    with pytest.raises(GroupPrompt.DoesNotExist) as exc:
        load_instruction_prompt(session, GroupStrategyPhase.AUDIENCE)

    assert "Prompt matching query does not exist." in str(exc.value)


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

    group_prompt_factory(
        week=1,
        strategy_type=GroupStrategyPhase.FOLLOWUP,
        activity="Reflect on your wins.",
    )

    result = load_instruction_prompt(session, GroupStrategyPhase.FOLLOWUP)
    expected = GROUP_INSTRUCTION_PROMPT_TEMPLATE.format(
        system="Sys1",
        persona="Pers1",
        assistant_name=BaseChatTranscript.Role.ASSISTANT,
        strategy="Reflect on your wins.",
    )
    assert result == expected
