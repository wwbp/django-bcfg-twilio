from dataclasses import dataclass
from rest_framework_dataclasses.serializers import DataclassSerializer


@dataclass
class _BaseContext:
    school_name: str
    school_mascot: str
    initial_message: str
    week_number: int
    message_type: str


@dataclass
class IndividualContext(_BaseContext):
    name: str


@dataclass
class IndividualIncomingMessage:
    context: IndividualContext
    message: str


@dataclass
class Participant:
    name: str
    id: str


@dataclass
class GroupContext(_BaseContext):
    participants: list[Participant]


@dataclass
class GroupIncomingMessage:
    context: GroupContext
    sender_id: str
    message: str


class IndividualIncomingMessageSerializer(DataclassSerializer):
    class Meta:
        dataclass = IndividualIncomingMessage
        extra_kwargs = {
            "message": {"allow_blank": True},
        }


class GroupIncomingMessageSerializer(DataclassSerializer):
    class Meta:
        dataclass = GroupIncomingMessage
        extra_kwargs = {
            "message": {"allow_blank": True},
        }
