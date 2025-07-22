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


def test_view_individualtranscript_list_filters(admin_client, individual_chat_transcript_factory):
    filtered_in_transcripts = individual_chat_transcript_factory.create_batch(
        2, session__week_number=1, session__user__school_name="test-school"
    )
    filtered_out_transcripts1 = individual_chat_transcript_factory.create_batch(
        2, session__week_number=2, session__user__school_name="test-school"
    )
    filtered_out_transcripts2 = individual_chat_transcript_factory.create_batch(
        2, session__week_number=1, session__user__school_name="other-school"
    )
    url = f"{reverse('admin:chat_individualchattranscript_changelist')}?week_number=1&school_name=test-school"
    response = admin_client.get(url)
    assert response.status_code == 200
    for transcript in filtered_in_transcripts:
        assert f"/admin/chat/individualchattranscript/{transcript.id}" in response.content.decode("utf-8")
    for transcript in [*filtered_out_transcripts1, *filtered_out_transcripts2]:
        assert f"/admin/chat/individualchattranscript/{transcript.id}" not in response.content.decode("utf-8")


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


def test_view_group_transcript_list_filters(admin_client, group_chat_transcript_factory, user_factory):
    filtered_in_transcripts = group_chat_transcript_factory.create_batch(2, session__week_number=1)
    for transcript in filtered_in_transcripts:
        user_factory.create_batch(2, group=transcript.session.group, school_name="test-school")
    filtered_out_transcripts1 = group_chat_transcript_factory.create_batch(2, session__week_number=2)
    for transcript in filtered_in_transcripts:
        user_factory.create_batch(2, group=transcript.session.group, school_name="test-school")
    filtered_out_transcripts2 = group_chat_transcript_factory.create_batch(2, session__week_number=1)
    for transcript in filtered_in_transcripts:
        user_factory.create_batch(2, group=transcript.session.group, school_name="other-school")

    url = f"{reverse('admin:chat_groupchattranscript_changelist')}?week_number=1&school_name=test-school"
    response = admin_client.get(url)
    assert response.status_code == 200
    for transcript in filtered_in_transcripts:
        assert f"/admin/chat/groupchattranscript/{transcript.id}" in response.content.decode("utf-8")
    for transcript in [*filtered_out_transcripts1, *filtered_out_transcripts2]:
        assert f"/admin/chat/groupchattranscript/{transcript.id}" not in response.content.decode("utf-8")


def test_view_prompt_list(admin_client, individual_prompt_factory):
    prompts = individual_prompt_factory.create_batch(2)
    response = admin_client.get(reverse("admin:chat_individualprompt_changelist"))
    assert response.status_code == 200
    for prompt in prompts:
        assert str(prompt.id) in response.content.decode("utf-8")


def test_view_control_list(admin_client, control_config_factory):
    control1 = control_config_factory(key=ControlConfig.ControlConfigKey.PERSONA_PROMPT, value="test_value")
    control2 = control_config_factory(key=ControlConfig.ControlConfigKey.SYSTEM_PROMPT, value="test_value")
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
