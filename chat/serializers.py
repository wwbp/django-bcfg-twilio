from rest_framework import serializers


class ContextSerializer(serializers.Serializer):
    school_name = serializers.CharField()
    school_mascot = serializers.CharField()
    initial_message = serializers.CharField()
    week_number = serializers.IntegerField()
    name = serializers.CharField()


class IncomingMessageSerializer(serializers.Serializer):
    context = ContextSerializer()
    message = serializers.CharField()


class ParticipantSerializer(serializers.Serializer):
    name = serializers.CharField()
    id = serializers.CharField()


class GroupContextSerializer(serializers.Serializer):
    school_name = serializers.CharField()
    school_mascot = serializers.CharField()
    initial_message = serializers.CharField()
    week_number = serializers.IntegerField()
    participants = ParticipantSerializer(many=True)


class GroupIncomingMessageSerializer(serializers.Serializer):
    context = GroupContextSerializer()
    sender_id = serializers.CharField()
    message = serializers.CharField()
