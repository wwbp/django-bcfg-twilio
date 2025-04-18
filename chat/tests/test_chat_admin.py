from django.urls import reverse

from chat.models import ControlConfig


def test_view_user_list(admin_client, user_factory):
    users = user_factory.create_batch(2)
    response = admin_client.get(
        reverse("admin:chat_user_changelist"),
    )
    assert response.status_code == 200
    for user in users:
        assert user.name in response.content.decode("utf-8")


def test_view_user_detail(admin_client, user_factory):
    user = user_factory()
    response = admin_client.get(
        reverse("admin:chat_user_change", args=(user.id,)),
    )
    assert response.status_code == 200


def test_view_group_list(admin_client, group_factory, user_factory):
    groups = group_factory.create_batch(2)
    users = user_factory.create_batch(2)
    for group in groups:
        for user in users:
            group.users.add(user)
        group.save()
    response = admin_client.get(
        reverse("admin:chat_group_changelist"),
    )
    assert response.status_code == 200
    for group in groups:
        assert group.id in response.content.decode("utf-8")


def test_view_group_detail(admin_client, group_factory, user_factory):
    group = group_factory()
    users = user_factory.create_batch(2)
    for user in users:
        group.users.add(user)
    group.save()
    response = admin_client.get(
        reverse("admin:chat_group_change", args=(group.id,)),
    )
    assert response.status_code == 200
    assert group.id in response.content.decode("utf-8")
    assert users[0].name in response.content.decode("utf-8")
    assert users[1].name in response.content.decode("utf-8")


def test_view_individualtranscript_list(admin_client, individual_chat_transcript_factory):
    transcripts = individual_chat_transcript_factory.create_batch(2)
    response = admin_client.get(reverse("admin:chat_individualchattranscript_changelist"))
    assert response.status_code == 200
    for transcript in transcripts:
        assert str(transcript.id) in response.content.decode("utf-8")


def test_view_individualtranscript_detail(admin_client, individual_chat_transcript_factory):
    transcript = individual_chat_transcript_factory()
    response = admin_client.get(reverse("admin:chat_individualchattranscript_change", args=(transcript.id,)))
    assert response.status_code == 200


def test_view_group_transcript_list(admin_client, group_chat_transcript_factory):
    transcripts = group_chat_transcript_factory.create_batch(2)
    response = admin_client.get(reverse("admin:chat_groupchattranscript_changelist"))
    assert response.status_code == 200
    for transcript in transcripts:
        assert str(transcript.id) in response.content.decode("utf-8")


def test_view_prompt_list(admin_client, individual_prompt_factory):
    prompts = individual_prompt_factory.create_batch(2)
    response = admin_client.get(reverse("admin:chat_individualprompt_changelist"))
    assert response.status_code == 200
    for prompt in prompts:
        assert str(prompt.id) in response.content.decode("utf-8")


def test_view_control_list(admin_client):
    control1 = ControlConfig.objects.create(key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="test_value")
    control2 = ControlConfig.objects.create(key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT, value="test_value")
    controls = [control1, control2]
    response = admin_client.get(reverse("admin:chat_controlconfig_changelist"))
    assert response.status_code == 200
    for control in controls:
        assert str(control.id) in response.content.decode("utf-8")


def test_view_summary_list(admin_client, summary_factory):
    summaries = summary_factory.create_batch(2)
    response = admin_client.get(reverse("admin:chat_summary_changelist"))
    assert response.status_code == 200
    for summary in summaries:
        assert str(summary.id) in response.content.decode("utf-8")


def test_view_individual_pipeline_list(admin_client, individual_pipeline_record_factory):
    records = individual_pipeline_record_factory.create_batch(2)
    response = admin_client.get(reverse("admin:chat_individualpipelinerecord_changelist"))
    assert response.status_code == 200
    for record in records:
        assert str(record.id) in response.content.decode("utf-8")


def test_view_group_pipeline_list(admin_client, group_pipeline_record_factory):
    records = group_pipeline_record_factory.create_batch(2)
    response = admin_client.get(reverse("admin:chat_grouppipelinerecord_changelist"))
    assert response.status_code == 200
    for record in records:
        assert str(record.id) in response.content.decode("utf-8")
