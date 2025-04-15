import sys
from unittest.mock import MagicMock, patch
from django.test import override_settings
import factory.random
import pytest
import factory
from pytest_factoryboy import register

from chat.models import (
    Group,
    GroupSession,
    IndividualSession,
    MessageType,
    User,
    IndividualChatTranscript,
    GroupChatTranscript,
    Prompt,
    Control,
    Summary,
    StrategyPrompt,
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


class IndividualPipelineMocks:
    def __init__(
        self,
        mock_moderate_message: MagicMock,
        mock_generate_response: MagicMock,
        mock_ensure_within_character_limit: MagicMock,
        mock_send_message_to_participant: MagicMock,
        mock_individual_send_moderation: MagicMock,
    ):
        self.mock_moderate_message = mock_moderate_message
        self.mock_generate_response = mock_generate_response
        self.mock_ensure_within_character_limit = mock_ensure_within_character_limit
        self.mock_send_message_to_participant = mock_send_message_to_participant
        self.mock_individual_send_moderation = mock_individual_send_moderation


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
            "chat.services.individual_pipeline.individual_send_moderation", return_value={"status": "ok"}
        ) as mock_individual_send_moderation,
    ):
        yield IndividualPipelineMocks(
            mock_moderate_message=mock_moderate_message,
            mock_generate_response=mock_generate_response,
            mock_ensure_within_character_limit=mock_ensure_within_character_limit,
            mock_send_message_to_participant=mock_send_message_to_participant,
            mock_individual_send_moderation=mock_individual_send_moderation,
        )


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
    role = factory.Faker("word")
    content = factory.Faker("sentence")


class GroupChatTranscriptFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GroupChatTranscript

    session = factory.SubFactory(GroupSessionFactory)
    sender = factory.SubFactory(UserFactory)
    role = factory.Faker("word")
    content = factory.Faker("sentence")


class PromptFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Prompt

    week = 1
    activity = factory.Faker("sentence")
    type = MessageType.INITIAL


class ControlFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Control

    persona = factory.Faker("sentence")
    system = factory.Faker("sentence")
    default = factory.Faker("sentence")
    moderation = factory.Faker("sentence")


class SummaryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Summary

    school = factory.Faker("word")
    type = Summary.TYPE_CHOICES[0][0]
    summary = factory.Faker("sentence")


class StrategyPromptFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StrategyPrompt

    name = factory.Faker("word")
    what_prompt = factory.Faker("sentence")
    when_prompt = factory.Faker("sentence")
    who_prompt = factory.Faker("sentence")
    is_active = True


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
register(PromptFactory)
register(ControlFactory)
register(SummaryFactory)
register(StrategyPromptFactory)
register(IndividualPipelineRecordFactory)
register(GroupPipelineRecordFactory)
register(IndividualSessionFactory)
