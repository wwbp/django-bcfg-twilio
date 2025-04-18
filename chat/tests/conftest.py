import sys
from unittest.mock import MagicMock, patch
from django.test import override_settings
from django.test import Client
import pytest
import factory
from pytest_factoryboy import register

from chat.models import (
    BaseChatTranscript,
    Group,
    GroupPrompt,
    GroupSession,
    GroupStrategyPhase,
    IndividualSession,
    MessageType,
    User,
    IndividualChatTranscript,
    GroupChatTranscript,
    IndividualPrompt,
    Summary,
    IndividualPipelineRecord,
    GroupPipelineRecord,
)


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config):
    if "xdist" not in sys.modules:
        return
    if config.option.file_or_dir and len(config.option.file_or_dir) == 1 and "::" in config.option.file_or_dir[0]:
        # if just running one test then disable xdist as generally this will be faster
        config.option.dist = "no"
        config.option.numprocesses = 0


@pytest.fixture(autouse=True)
def enable_db_access(db):
    pass


@pytest.fixture(autouse=True)
def overwrite_secrets():
    # overwrite secrets to prevent hitting real services while unit testing, just in case
    with override_settings(
        OPENAI_API_KEY="fake-openai-api-key",
        BCFG_API_KEY="fake-bcfg-api-key",
    ):
        yield


@pytest.fixture
def celery_task_always_eager(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    yield
    settings.CELERY_TASK_ALWAYS_EAGER = False


@pytest.fixture
def message_client():
    api_key = "valid-api-key"
    with override_settings(INBOUND_MESSAGE_API_KEY=api_key):
        yield Client(headers={"Authorization": f"Bearer {api_key}"})


def test_view_with_custom_header(client_with_headers):
    response = client_with_headers.get("/your-url/")
    assert response.status_code == 200
    # Additional assertions based on the header


class IndividualPipelineMocks:
    def __init__(
        self,
        mock_moderate_message: MagicMock,
        mock_generate_response: MagicMock,
        mock_ensure_within_character_limit: MagicMock,
        mock_send_message_to_participant: MagicMock,
        mock_send_moderation_message: MagicMock,
    ):
        self.mock_moderate_message = mock_moderate_message
        self.mock_generate_response = mock_generate_response
        self.mock_ensure_within_character_limit = mock_ensure_within_character_limit
        self.mock_send_message_to_participant = mock_send_message_to_participant
        self.mock_send_moderation_message = mock_send_moderation_message


@pytest.fixture
def mock_all_individual_external_calls():
    # default mocks to make entire pipeline run but return values or
    # general mocking behavior can be overriden via returned object

    # Note that these mocks don't actually extend all the way to the external interfaces
    # and could be taken further to mock only http requests (or libraries) but for now
    # other unit tests capture that coverage
    with (
        patch("chat.services.individual_pipeline.moderate_message", return_value="") as mock_moderate_message,
        patch(
            "chat.services.individual_pipeline.generate_response", return_value="Some LLM response"
        ) as mock_generate_response,
        patch(
            "chat.services.individual_pipeline.ensure_within_character_limit",
            return_value="Some shortened LLM response",
        ) as mock_ensure_within_character_limit,
        patch(
            "chat.services.individual_pipeline.send_message_to_participant", return_value={"status": "ok"}
        ) as mock_send_message_to_participant,
        patch(
            "chat.services.individual_pipeline.send_moderation_message", return_value={"status": "ok"}
        ) as mock_send_moderation_message,
    ):
        yield IndividualPipelineMocks(
            mock_moderate_message=mock_moderate_message,
            mock_generate_response=mock_generate_response,
            mock_ensure_within_character_limit=mock_ensure_within_character_limit,
            mock_send_message_to_participant=mock_send_message_to_participant,
            mock_send_moderation_message=mock_send_moderation_message,
        )


@pytest.fixture
def group_with_initial_message_interaction(
    group_factory,
    user_factory,
    group_session_factory,
    group_chat_transcript_factory,
    faker,
    group_pipeline_record_factory,
):
    initial_message = "some initial LLM message"
    user_message = "some message from user"

    school_mascot = faker.word()
    school_name = faker.word()
    group = group_factory()
    users = user_factory.create_batch(6, group=group, school_mascot=school_mascot, school_name=school_name)
    session = group_session_factory(group=group, week_number=1, message_type=MessageType.INITIAL)
    group_chat_transcript_factory(session=session, role=BaseChatTranscript.Role.ASSISTANT, content=initial_message)
    group_chat_transcript_factory(
        session=session, role=BaseChatTranscript.Role.USER, content=user_message, sender=users[0]
    )
    group_chat_transcript_factory(session=session, role=BaseChatTranscript.Role.ASSISTANT, content="some LLM response")
    group_pipeline_record = group_pipeline_record_factory(
        group=group,
        user=users[0],
        status=GroupPipelineRecord.StageStatus.MODERATION_PASSED,
        message=user_message,
        response=None,
        instruction_prompt=None,
        validated_message=None,
        error_log=None,
    )
    example_message_context = {
        "school_name": school_name,
        "school_mascot": school_mascot,
        "initial_message": initial_message,
        "week_number": 1,
        "message_type": MessageType.INITIAL,
        "participants": [
            {
                "id": user.id,
                "name": user.name,
            }
            for user in users
        ],
    }
    yield group, session, group_pipeline_record, example_message_context


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    id = factory.Faker("uuid4")
    name = factory.Faker("first_name")
    school_mascot = factory.Faker("word")


class IndividualSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IndividualSession

    user = factory.SubFactory(UserFactory)
    week_number = 1
    message_type = MessageType.INITIAL


class GroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Group

    id = factory.Faker("uuid4")


class GroupSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GroupSession

    group = factory.SubFactory(GroupFactory)
    week_number = 1
    message_type = MessageType.INITIAL


class ChatTranscriptFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IndividualChatTranscript

    session = factory.SubFactory(IndividualSessionFactory)
    role = BaseChatTranscript.Role.ASSISTANT
    content = factory.Faker("sentence")


class GroupChatTranscriptFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GroupChatTranscript

    session = factory.SubFactory(GroupSessionFactory)
    sender = None
    role = BaseChatTranscript.Role.ASSISTANT
    content = factory.Faker("sentence")


class IndividualPromptFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IndividualPrompt

    week = factory.Faker("random_int")
    activity = factory.Faker("sentence")
    message_type = MessageType.INITIAL


class GroupPromptFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GroupPrompt

    week = factory.Faker("random_int")
    activity = factory.Faker("sentence")
    strategy_type = GroupStrategyPhase.AUDIENCE


class SummaryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Summary

    school = factory.Faker("word")
    type = Summary.TYPE_CHOICES[0][0]
    summary = factory.Faker("sentence")


class IndividualPipelineRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IndividualPipelineRecord

    user = factory.SubFactory(UserFactory)
    message = factory.Faker("sentence")
    response = factory.Faker("sentence")
    instruction_prompt = factory.Faker("sentence")
    validated_message = factory.Faker("sentence")
    status = IndividualPipelineRecord.StageStatus.INGEST_PASSED


class GroupPipelineRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GroupPipelineRecord

    run_id = factory.Faker("uuid4")
    user = factory.SubFactory(UserFactory)
    group = factory.SubFactory(GroupFactory)
    message = factory.Faker("sentence")
    response = factory.Faker("sentence")
    instruction_prompt = factory.Faker("sentence")
    validated_message = factory.Faker("sentence")
    status = GroupPipelineRecord.StageStatus.INGEST_PASSED


# register factories as fixtures
register(UserFactory)
register(GroupFactory)
register(ChatTranscriptFactory)
register(GroupChatTranscriptFactory)
register(GroupPromptFactory)
register(IndividualPromptFactory)
register(SummaryFactory)
register(IndividualPipelineRecordFactory)
register(GroupPipelineRecordFactory)
register(IndividualSessionFactory)
register(GroupSessionFactory)
