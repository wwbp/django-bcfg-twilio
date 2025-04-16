import uuid
from django.db import models
from django.utils import timezone
from django_celery_beat.models import PeriodicTask
from simple_history.models import HistoricalRecords

from .services.constant import MODERATION_MESSAGE_DEFAULT


class MessageType(models.TextChoices):
    INITIAL = "initial", "Initial"
    REMINDER = "reminder", "Reminder"
    CHECK_IN = "check-in", "Check-in"
    SUMMARY = "summary", "Summary"


class GroupStrategyPhase(models.TextChoices):
    BEFORE_AUDIENCE = "before_audience"
    AFTER_AUDIENCE = "after_audience"
    AFTER_REMINDER = "after_reminder"
    AFTER_FOLLOWUP = "after_followup"
    AFTER_SUMMARY = "after_summary"


class ModelBase(models.Model):
    history = HistoricalRecords(inherit=True, excluded_fields=["created_at"])

    # created_at is duplicated in the HistoricalModel, but is useful for sorting. We don't
    # want to depend on the HistoricalModel for anything besides an audit log.
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        abstract = True


class ModelBaseWithUuidId(ModelBase):
    """Base class for all models"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class Group(ModelBase):
    id = models.CharField(primary_key=True, max_length=255)
    is_test = models.BooleanField(default=False)

    @property
    def current_session(self) -> "IndividualSession | None":
        return self.sessions.order_by("-created_at").first()

    def __str__(self):
        member_count = self.users.count()
        return f"{self.id} ({member_count} member{'s' if member_count != 1 else ''})"

    class Meta:
        ordering = ["-created_at"]


class User(ModelBase):
    id = models.CharField(primary_key=True, max_length=255)
    group = models.ForeignKey(Group, on_delete=models.DO_NOTHING, related_name="users", null=True, blank=True)
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


class BaseSession(ModelBase):
    week_number = models.IntegerField()
    message_type = models.CharField(max_length=20, choices=MessageType.choices)

    @property
    def initial_message(self) -> str:
        return self.transcripts.order_by("created_at").first().content

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class IndividualSession(BaseSession):
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name="sessions")

    def __str__(self):
        return f"{self.user} - {self.message_type} (wk {self.week_number})"


class GroupSession(BaseSession):
    group = models.ForeignKey(Group, on_delete=models.DO_NOTHING, related_name="sessions")
    current_strategy_phase = models.CharField(
        max_length=20, choices=GroupStrategyPhase.choices, default=GroupStrategyPhase.BEFORE_AUDIENCE
    )

    @property
    def all_participants_responded(self) -> bool:
        # note that participants can be added or removed from groups (e.g. if a participant leaves the study)
        # so we need to check if all participants have responded who are still in the group
        user_ids_responded = [
            u["sender_id"]
            for u in list(self.transcripts.filter(role=BaseChatTranscript.Role.USER).values("sender_id").distinct())
        ]
        group_user_ids = [u["id"] for u in list(self.group.users.values("id").all())]
        return set(group_user_ids) - set(user_ids_responded) == set()

    @property
    def fewer_than_three_participants_responded(self) -> bool:
        user_ids_responded = {
            u["sender_id"]
            for u in self.transcripts.filter(role=BaseChatTranscript.Role.USER).values("sender_id").distinct()
        }
        return len(user_ids_responded) < 3

    @property
    def reminder_sent(self) -> bool:
        return self.transcripts.filter(assistant_strategy_phase=GroupStrategyPhase.AFTER_REMINDER).exists()

    @property
    def summary_sent(self) -> bool:
        return self.transcripts.filter(assistant_strategy_phase=GroupStrategyPhase.AFTER_SUMMARY).exists()

    def __str__(self):
        return f"{self.group} - {self.message_type} (wk {self.week_number})"


class BaseChatTranscript(ModelBase):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    class ModerationStatus(models.TextChoices):
        NOT_EVALUATED = "not_evaluated"
        FLAGGED = "flagged"
        NOT_FLAGGED = "not_flagged"

    role = models.CharField(max_length=255, choices=Role.choices)
    content = models.TextField()
    moderation_status = models.CharField(
        max_length=15, choices=ModerationStatus.choices, default=ModerationStatus.NOT_EVALUATED
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class IndividualChatTranscript(BaseChatTranscript):
    session = models.ForeignKey(IndividualSession, on_delete=models.DO_NOTHING, related_name="transcripts")


class GroupChatTranscript(BaseChatTranscript):
    session = models.ForeignKey(GroupSession, on_delete=models.DO_NOTHING, related_name="transcripts")
    sender = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name="group_transcripts", null=True)
    assistant_strategy_phase = models.CharField(max_length=20, choices=GroupStrategyPhase.choices, null=True)


class Prompt(ModelBase):
    is_for_group = models.BooleanField(default=False)
    week = models.IntegerField()
    activity = models.TextField()
    type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.INITIAL)

    def clean(self):
        super().clean()
        if self.is_for_group and self.type == MessageType.CHECK_IN:
            raise ValueError(f"Group prompts cannot be of type {MessageType.CHECK_IN}")

    class Meta:
        verbose_name_plural = "Weekly Prompts"
        ordering = ["week", "type", "-created_at"]


class Control(ModelBase):
    persona = models.TextField()
    system = models.TextField()
    default = models.TextField()
    moderation = models.TextField(default=MODERATION_MESSAGE_DEFAULT)

    class Meta:
        verbose_name_plural = "Control Prompts"
        ordering = ["-created_at"]


class Summary(ModelBase):
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
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Summaries"
        ordering = ["-updated_at"]


class StrategyPrompt(ModelBase):
    name = models.CharField(max_length=255)
    what_prompt = models.TextField(help_text="Prompt used to generate a response", default="")
    when_prompt = models.TextField(help_text="Conditions or triggers for using this strategy", default="")
    who_prompt = models.TextField(help_text="Criteria for selecting the response's addressee", default="")
    is_active = models.BooleanField(default=True, help_text="Soft delete flag")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["is_active", "name"]


class BasePipelineRecord(ModelBase):
    run_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    message = models.TextField(blank=True, null=True)
    response = models.TextField(blank=True, null=True)
    instruction_prompt = models.TextField(blank=True, null=True)
    validated_message = models.TextField(blank=True, null=True)
    error_log = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class IndividualPipelineRecord(BasePipelineRecord):
    class StageStatus(models.TextChoices):
        INGEST_PASSED = "INGEST_PASSED", "Ingest Passed"
        MODERATION_BLOCKED = "MODERATION_BLOCKED", "Moderation Blocked"
        MODERATION_PASSED = "MODERATION_PASSED", "Moderation Passed"
        PROCESS_PASSED = "PROCESS_PASSED", "Process Passed"
        PROCESS_SKIPPED = "PROCESS_SKIPPED", "Process Skipped"
        VALIDATE_PASSED = "VALIDATE_PASSED", "Validate Passed"
        SEND_PASSED = "SEND_PASSED", "Send Passed"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="individual_pipeline_records")
    status = models.CharField(max_length=50, choices=StageStatus.choices, default=StageStatus.INGEST_PASSED)

    def __str__(self):
        return f"IndividualPipelineRecord({self.user}, {self.run_id})"


class GroupPipelineRecord(BasePipelineRecord):
    class StageStatus(models.TextChoices):
        INGEST_PASSED = "INGEST_PASSED", "Ingest Passed"
        MODERATION_BLOCKED = "MODERATION_BLOCKED", "Moderation Blocked"
        MODERATION_PASSED = "MODERATION_PASSED", "Moderation Passed"
        PROCESS_PASSED = "PROCESS_PASSED", "Process Passed"
        PROCESS_SKIPPED = "PROCESS_SKIPPED", "Process Skipped"
        PROCESS_NOTHING_TO_DO = "PROCESS_NOTHING_TO_DO", "Process Nothing To Do"
        SEND_PASSED = "SEND_PASSED", "Send Passed"
        SCHEDULED_ACTION = "SCHEDULED_ACTION", "Scheduled Action"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="group_pipeline_records")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="group_pipeline_records")
    status = models.CharField(max_length=50, choices=StageStatus.choices, default=StageStatus.INGEST_PASSED)

    @property
    def is_test(self):
        return self.user.is_test or self.group.is_test

    def __str__(self):
        return f"GroupPipelineRecord({self.user}, {self.run_id})"


class ScheduledTaskAssociation(ModelBaseWithUuidId):
    """Base class used to relate scheduled tasks to their related model objects"""

    task = models.ForeignKey(PeriodicTask, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class GroupScheduledTaskAssociation(ScheduledTaskAssociation):
    """A scheduled task related to a group"""

    group = models.ForeignKey(Group, on_delete=models.CASCADE)
