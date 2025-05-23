import logging

from chat.services.individual_pipeline import individual_pipeline
from chat.models import (
    ControlConfig,
    GroupPipelineRecord,
    IndividualPipelineRecord,
    MessageType,
    IndividualPrompt,
)


def test_individual_pipeline_for_direct_messaging(
    mock_all_individual_external_calls, caplog, group_with_initial_message_interaction, control_config_factory
):
    caplog.set_level(logging.INFO)
    group, _, _, _ = group_with_initial_message_interaction
    user = group.users.first()
    context = {
        "school_name": user.school_name,
        "school_mascot": user.school_mascot,
        "initial_message": "Some initial message",
        "week_number": 1,
        "name": user.name,
        "message_type": MessageType.INITIAL,
    }
    data = {
        "message": "Some message from user",
        "context": context,
    }
    IndividualPrompt.objects.create(
        week=context["week_number"],
        message_type=context["message_type"],
        activity="base activity",
    )
    control_config_factory(
        key=ControlConfig.ControlConfigKey.GROUP_DIRECT_MESSAGE_PERSONA_PROMPT, value="test persona prompt"
    )
    control_config_factory(key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT, value="test system prompt")

    control_config_factory(
        key=ControlConfig.ControlConfigKey.INSTRUCTION_PROMPT_TEMPLATE,
        value="INSTRUCTION_PROMPT_TEMPLATE",
    )
    individual_pipeline.run(user.id, data)

    record = IndividualPipelineRecord.objects.get(user=user)
    assert record.status == IndividualPipelineRecord.StageStatus.SEND_PASSED
    assert record.is_for_group_direct_messaging is True
    assert "using group direct-message strategy" in caplog.text
    assert "Loading chat history for participant and their group for direct-messaging" in caplog.text
    assert "Loading instruction prompt for direct-messaging group participant" in caplog.text
    assert GroupPipelineRecord.objects.count() == 1  # record from fixture only
