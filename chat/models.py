import uuid
from django.db import models
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from .services.constant import MODERATION_MESSAGE_DEFAULT


class MessageType(models.TextChoices):
    INITIAL = "initial", "Initial"
    REMINDER = "reminder", "Reminder"
    CHECK_IN = "check-in", "Check-in"
    SUMMARY = "summary", "Summary"


class TranscriptRole(models.TextChoices):
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"


class ModelBase(models.Model):
    """Base class for all models"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        abstract = True


class User(models.Model):
    id = models.CharField(primary_key=True, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    school_name = models.CharField(max_length=255, default="")
    school_mascot = models.CharField(max_length=255, default="")
    name = models.CharField(max_length=255, default="")
    is_test = models.BooleanField(default=False)

    @property
    def current_session(self) -> "IndividualSession | None":
        return self.sessions.order_by("-created_at").first()

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]


class IndividualSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name="sessions")
    created_at = models.DateTimeField(auto_now_add=True)
    initial_message = models.TextField()
    week_number = models.IntegerField()
    message_type = models.CharField(max_length=20, choices=MessageType.choices)

    def __str__(self):
        return f"{self.user} - {self.message_type} ({self.week_number})"

    class Meta:
        ordering = ["-created_at"]


class Group(models.Model):
    id = models.CharField(primary_key=True, max_length=255)
    users = models.ManyToManyField(User, related_name="groups")
    created_at = models.DateTimeField(auto_now_add=True)
    is_test = models.BooleanField(default=False)
    week_number = models.IntegerField(null=True, blank=True)
    initial_message = models.TextField(default="")

    def __str__(self):
        member_count = self.users.count()
        return f"{self.id} ({member_count} member{'s' if member_count != 1 else ''})"

    class Meta:
        ordering = ["-created_at"]


class ChatTranscript(models.Model):
    session = models.ForeignKey(IndividualSession, on_delete=models.DO_NOTHING, related_name="transcripts")
    role = models.CharField(max_length=255, choices=TranscriptRole.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class GroupChatTranscript(models.Model):
    group = models.ForeignKey(Group, on_delete=models.DO_NOTHING, related_name="transcripts")
    sender = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name="group_transcripts", null=True)
    role = models.CharField(max_length=255, choices=TranscriptRole.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Prompt(models.Model):
    week = models.IntegerField()
    activity = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.INITIAL)

    class Meta:
        verbose_name_plural = "Weekly Prompts"
        ordering = ["week", "type", "-created_at"]


class Control(models.Model):
    persona = models.TextField()
    system = models.TextField()
    default = models.TextField()
    moderation = models.TextField(default=MODERATION_MESSAGE_DEFAULT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Control Prompts"
        ordering = ["-created_at"]


class Summary(models.Model):
    TYPE_CHOICES = [
        ("influencer", "Influencer"),
        ("song", "Song"),
        ("spot", "Spot"),
        ("idea", "Idea"),
        ("pick", "Pick"),
    ]

    school = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Summaries"
        ordering = ["-updated_at"]


class StrategyPrompt(models.Model):
    name = models.CharField(max_length=255)
    what_prompt = models.TextField(help_text="Prompt used to generate a response", default="")
    when_prompt = models.TextField(help_text="Conditions or triggers for using this strategy", default="")
    who_prompt = models.TextField(help_text="Criteria for selecting the response's addressee", default="")
    is_active = models.BooleanField(default=True, help_text="Soft delete flag")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["is_active", "name"]


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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pipeline_records")
    message = models.TextField(blank=True, null=True)
    response = models.TextField(blank=True, null=True)
    instruction_prompt = models.TextField(blank=True, null=True)
    validated_message = models.TextField(blank=True, null=True)
    error_log = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=StageStatus.choices, default=StageStatus.INGEST_PASSED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"IndividualPipelineRecord({self.user}, {self.run_id})"

    class Meta:
        ordering = ["-created_at"]


class GroupPipelineRecord(models.Model):
    run_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="pipeline_records")
    ingested = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    sent = models.BooleanField(default=False)
    failed = models.BooleanField(default=False)
    error_log = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"GroupPipelineRecord({self.group}, {self.run_id})"

    class Meta:
        ordering = ["-created_at"]


class ScheduledTaskAssociation(ModelBase):
    """Base class used to relate scheduled tasks to their related model objects"""

    task = models.ForeignKey(PeriodicTask, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class GroupScheduledTaskAssociation(ScheduledTaskAssociation):
    """A scheduled task related to a group"""

    group = models.ForeignKey(Group, on_delete=models.CASCADE)
