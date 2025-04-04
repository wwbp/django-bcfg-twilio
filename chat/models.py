import uuid
from django.db import models

from .services.constant import MODERATION_MESSAGE_DEFAULT

class MessageType(models.TextChoices):
    INITIAL = "initial", "Initial"
    REMINDER = "reminder", "Reminder"
    CHECK_IN = "check-in", "Check-in"
    SUMMARY = "summary", "Summary"

class User(models.Model):
    id = models.CharField(primary_key=True, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    school_name = models.CharField(max_length=255, default='')
    school_mascot = models.CharField(max_length=255, default='')
    name = models.CharField(max_length=255, default='')
    initial_message = models.TextField(default='')
    is_test = models.BooleanField(default=False)
    week_number = models.IntegerField(null=True, blank=True)
    message_type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.INITIAL)


class Group(models.Model):
    id = models.CharField(primary_key=True, max_length=255)
    users = models.ManyToManyField(User, related_name="groups")
    created_at = models.DateTimeField(auto_now_add=True)
    is_test = models.BooleanField(default=False)
    week_number = models.IntegerField(null=True, blank=True)
    initial_message = models.TextField(default='')


class ChatTranscript(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
    )
    user = models.ForeignKey(
        User, on_delete=models.DO_NOTHING, related_name='transcripts')
    role = models.CharField(max_length=255, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class GroupChatTranscript(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
    )
    group = models.ForeignKey(
        Group, on_delete=models.DO_NOTHING, related_name='transcripts')
    sender = models.ForeignKey(
        User, on_delete=models.DO_NOTHING, related_name='group_transcripts', null=True)
    role = models.CharField(max_length=255, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Prompt(models.Model):
    week = models.IntegerField()
    activity = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.INITIAL)


class Control(models.Model):
    persona = models.TextField()
    system = models.TextField()
    default = models.TextField()
    moderation = models.TextField(default=MODERATION_MESSAGE_DEFAULT)
    created_at = models.DateTimeField(auto_now_add=True)


class Summary(models.Model):
    TYPE_CHOICES = [
        ('influencer', 'Influencer'),
        ('song', 'Song'),
        ('spot', 'Spot'),
        ('idea', 'Idea'),
        ('pick', 'Pick'),
    ]

    school = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class StrategyPrompt(models.Model):
    name = models.CharField(max_length=255)
    what_prompt = models.TextField(
        help_text="Prompt used to generate a response", default="")
    when_prompt = models.TextField(
        help_text="Conditions or triggers for using this strategy", default="")
    who_prompt = models.TextField(
        help_text="Criteria for selecting the response's addressee", default="")
    is_active = models.BooleanField(default=True, help_text="Soft delete flag")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class IndividualPipelineRecord(models.Model):
    class StageStatus(models.TextChoices):
        INGEST_PASSED = "INGEST_PASSED", "Ingest Passed"
        MODERATION_BLOCKED = "MODERATION_BLOCKED", "Moderation Blocked"
        MODERATION_PASSED = "MODERATION_PASSED", "Moderation Passed"
        PROCESS_PASSED = "PROCESS_PASSED", "Process Passed"
        PROCESS_SKIPPED = "PROCESS_SKIPPED", "Process Skipped"
        VALIDATE_PASSED = "VALIDATE_PASSED", "Validate Passed"
        SEND_PASSED = "SEND_PASSED", "Send Passed"
        FAILED = "FAILED", "Failed"

    run_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    participant_id = models.CharField(max_length=255)
    message = models.TextField(blank=True, null=True)
    response = models.TextField(blank=True, null=True)
    instruction_prompt = models.TextField(blank=True, null=True)
    validated_message = models.TextField(blank=True, null=True)
    error_log = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=50,
        choices=StageStatus.choices,
        default=StageStatus.INGEST_PASSED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"IndividualPipelineRecord({self.participant_id}, {self.run_id})"


class GroupPipelineRecord(models.Model):
    run_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    group_id = models.CharField(max_length=255)
    ingested = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    sent = models.BooleanField(default=False)
    failed = models.BooleanField(default=False)
    error_log = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"GroupPipelineRecord({self.group_id}, {self.run_id})"
