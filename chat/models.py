from datetime import timedelta
import logging
import uuid
from django.db import models
from django.forms import ValidationError
from django.utils import timezone
from django_celery_beat.models import PeriodicTask
from simple_history.models import HistoricalRecords


logger = logging.getLogger(__name__)


class MessageType(models.TextChoices):
    INITIAL = "initial", "Initial"
    REMINDER = "reminder", "Reminder"
    CHECK_IN = "check-in", "Check-in"
    SUMMARY = "summary", "Summary"


class GroupPromptMessageType(models.TextChoices):
    INITIAL = MessageType.INITIAL
    SUMMARY = MessageType.SUMMARY


class GroupStrategyPhase(models.TextChoices):
    # At any point when we're executing the group pipeline, we are in one of these phases
    # When in a SCHEDULED_ACTION state, we are only in a "before" or "after" phase
    # Therefore
    # * A GroupPipelineRecord will only ever be in a before or after phase per the db
    # * A GroupChatTranscript will never be associated with a before or after phase
    BEFORE_AUDIENCE = "before_audience"
    AUDIENCE = "audience"
    AFTER_AUDIENCE = "after_audience"
    REMINDER = "reminder"
    AFTER_REMINDER = "after_reminder"
    FOLLOWUP = "followup"
    AFTER_FOLLOWUP = "after_followup"
    SUMMARY = "summary"
    AFTER_SUMMARY = "after_summary"


class GroupStrategyPhasesThatAllowConfig(models.TextChoices):
    BEFORE_AUDIENCE = GroupStrategyPhase.BEFORE_AUDIENCE
    AFTER_AUDIENCE = GroupStrategyPhase.AFTER_AUDIENCE
    AFTER_REMINDER = GroupStrategyPhase.AFTER_REMINDER
    AFTER_FOLLOWUP = GroupStrategyPhase.AFTER_FOLLOWUP


class GroupStrategyPhasesThatAllowPrompts(models.TextChoices):
    FOLLOWUP = GroupStrategyPhase.FOLLOWUP
    SUMMARY = GroupStrategyPhase.SUMMARY


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
        result = ", ".join([u.name for u in self.users.all()])  # type: ignore
        return result if result else self.id

    class Meta:
        ordering = ["-created_at"]


class User(ModelBase):
    id = models.CharField(primary_key=True, max_length=255)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="users", null=True, blank=True)
    school_name = models.CharField(max_length=255, default="")
    school_mascot = models.CharField(max_length=255, default="")
    name = models.CharField(max_length=255, default="")
    is_test = models.BooleanField(default=False)

    @property
    def current_session(self) -> "IndividualSession | None":
        if self.group:
            return self.group.current_session
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")

    class Meta(BaseSession.Meta):
        unique_together = ["user", "week_number", "message_type"]

    def __str__(self):
        return f"{self.user} - {self.message_type} (wk {self.week_number})"


class GroupSession(BaseSession):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="sessions")
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
        return self.transcripts.filter(assistant_strategy_phase=GroupStrategyPhase.REMINDER).exists()

    @property
    def summary_sent(self) -> bool:
        return self.transcripts.filter(assistant_strategy_phase=GroupStrategyPhase.SUMMARY).exists()

    class Meta(BaseSession.Meta):
        unique_together = ["group", "week_number", "message_type"]

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
    session = models.ForeignKey(IndividualSession, on_delete=models.CASCADE, related_name="transcripts")


class GroupChatTranscript(BaseChatTranscript):
    session = models.ForeignKey(GroupSession, on_delete=models.CASCADE, related_name="transcripts")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="group_transcripts", null=True, blank=True)
    assistant_strategy_phase = models.CharField(max_length=20, choices=GroupStrategyPhase.choices, null=True)


class BasePrompt(ModelBase):
    week = models.IntegerField()
    activity = models.TextField()

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class IndividualPrompt(BasePrompt):
    message_type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.INITIAL)

    class Meta:
        unique_together = ["week", "message_type"]
        verbose_name_plural = "Weekly Individual Prompts"
        ordering = ["week", "message_type", "-created_at"]


class GroupPrompt(BasePrompt):
    message_type = models.CharField(
        max_length=20, choices=GroupPromptMessageType.choices, default=GroupPromptMessageType.INITIAL
    )
    strategy_type = models.CharField(
        max_length=20,
        choices=GroupStrategyPhasesThatAllowPrompts.choices,
        default=GroupStrategyPhasesThatAllowPrompts.FOLLOWUP,
    )

    class Meta:
        unique_together = ["week", "message_type", "strategy_type"]
        verbose_name_plural = "Weekly Group Prompts"
        ordering = ["week", "message_type", "strategy_type"]


class ControlConfig(ModelBaseWithUuidId):
    class ControlConfigKey(models.TextChoices):
        PERSONA_PROMPT = "persona_prompt"
        SYSTEM_PROMPT = "system_prompt"
        GROUP_DIRECT_MESSAGE_PERSONA_PROMPT = "group_direct_message_persona_prompt"
        SCHOOL_SUMMARY_PROMPT = "school_summary_prompt"
        GROUP_AUDIENCE_STRATEGY_PROMPT = "group_audience_strategy_prompt"
        GROUP_REMINDER_STRATEGY_PROMPT = "group_reminder_strategy_prompt"
        GROUP_SUMMARY_PERSONA_PROMPT = "group_summary_persona_prompt"

    key = models.TextField(unique=True, choices=ControlConfigKey.choices)
    value = models.TextField(blank=True, null=True)

    @classmethod
    def retrieve(cls, key: ControlConfigKey | str):
        try:
            return cls.objects.get(key=str(key)).value
        except cls.DoesNotExist:
            logger.warning(f"ControlConfigKey key '{key}' requested but not found.")
            return None

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key


class GroupStrategyPhaseConfig(ModelBaseWithUuidId):
    group_strategy_phase = models.CharField(choices=GroupStrategyPhasesThatAllowConfig.choices, unique=True)
    min_wait_seconds = models.IntegerField()
    max_wait_seconds = models.IntegerField()

    def clean(self):
        super().clean()
        if self.min_wait_seconds < 0:
            raise ValidationError("min_wait_seconds must be greater than or equal to 0")
        if self.max_wait_seconds < 0:
            raise ValidationError("max_wait_seconds must be greater than or equal to 0")
        if self.min_wait_seconds > self.max_wait_seconds:
            raise ValidationError("min_wait_seconds must be less than or equal to max_wait_seconds")

    class Meta:
        ordering = ["group_strategy_phase"]


class Summary(ModelBase):
    school_name = models.CharField(max_length=255)
    week_number = models.IntegerField()
    summary = models.TextField()
    selected = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Summaries"
        ordering = ["-updated_at"]


class BasePipelineRecord(ModelBase):
    run_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    message = models.TextField(blank=True, null=True)
    response = models.TextField(blank=True, null=True)
    instruction_prompt = models.TextField(blank=True, null=True)
    validated_message = models.TextField(blank=True, null=True)
    error_log = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    latency = models.DurationField(default=timedelta(0))
    shorten_count = models.IntegerField(default=0)

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

    # note that we could use a derived property for this, but we would lose history if the user
    # is removed from the group
    is_for_group_direct_messaging = models.BooleanField(default=False)

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
