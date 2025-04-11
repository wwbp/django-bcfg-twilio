import sys
from django.test import override_settings
import factory.random
import pytest
import factory
from pytest_factoryboy import register

from chat.models import (
    Group,
    IndividualSession,
    MessageType,
    User,
    ChatTranscript,
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


class ChatTranscriptFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ChatTranscript

    session = factory.SubFactory(IndividualSessionFactory)
    role = factory.Faker("word")
    content = factory.Faker("sentence")


class GroupChatTranscriptFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GroupChatTranscript

    group = factory.SubFactory(GroupFactory)
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
    status = IndividualPipelineRecord.StageStatus.VALIDATE_PASSED


class GroupPipelineRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GroupPipelineRecord

    group = factory.SubFactory(GroupFactory)
    ingested = True


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
