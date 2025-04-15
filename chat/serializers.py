from rest_framework import serializers


class BaseContextSerializer(serializers.Serializer):
    school_name = serializers.CharField()
    school_mascot = serializers.CharField()
    initial_message = serializers.CharField()
    week_number = serializers.IntegerField()
    message_type = serializers.CharField()


class IndividualContextSerializer(BaseContextSerializer):
    name = serializers.CharField()


class IndividualIncomingMessageSerializer(serializers.Serializer):
    context = IndividualContextSerializer()
    message = serializers.CharField()


class ParticipantSerializer(serializers.Serializer):
    name = serializers.CharField()
    id = serializers.CharField()


class GroupContextSerializer(BaseContextSerializer):
    participants = ParticipantSerializer(many=True)


class GroupIncomingMessageSerializer(serializers.Serializer):
    context = GroupContextSerializer()
    sender_id = serializers.CharField()
    message = serializers.CharField()
