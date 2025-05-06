import logging
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count
from django.db.models.query import QuerySet
from django.urls import reverse
from django.utils.html import format_html

from chat.services.summaries import handle_summaries_selected_change
from .models import (
    BaseChatTranscript,
    ControlConfig,
    GroupPrompt,
    GroupSession,
    GroupStrategyPhaseConfig,
    User,
    Group,
    IndividualChatTranscript,
    GroupChatTranscript,
    IndividualPrompt,
    Summary,
    IndividualPipelineRecord,
    GroupPipelineRecord,
    IndividualSession,
)
from admin.models import AuthGroupName
from simple_history.admin import SimpleHistoryAdmin
from import_export.admin import ImportExportModelAdmin
from django.utils.html import format_html

log = logging.getLogger(__name__)


class BaseAdmin(SimpleHistoryAdmin):
    # base admin class that logs all actions
    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        if obj:
            log.info(f"Admin Site: User {request.user} viewed {self.model.__name__} {obj.id}")
        return super().render_change_form(request, context, add, change, form_url, obj)

    def changelist_view(self, request, extra_context=None):
        log.info(f"Admin Site: User {request.user} viewed {self.model.__name__} list")
        return super().changelist_view(request, extra_context)


class ReadonlyAdmin(BaseAdmin):
    # base admin class that is read-omly by default
    def has_change_permission(self, request, obj=None):
        if request.user.is_staff and (
            AuthGroupName.UnlockRestrictedContent.value in request.user.groups.values_list("name", flat=True)
        ):
            return super().has_change_permission(request, obj)
        else:
            return False


class EditableAdmin(BaseAdmin, ImportExportModelAdmin):
    pass


class ReadonlyTabularInline(admin.TabularInline):
    fields: tuple = ()
    extra = 0
    ordering = ("timestamp",)
    can_delete = False
    has_add_permission = lambda self, request, obj: False
    template = "admin/read_only_tabular.html"
    classes = ["collapse", "collapsed"]

    def has_change_permission(self, request, obj=None):
        return False


class IndividualSessionsInline(ReadonlyTabularInline):
    model = IndividualSession
    fields = ("week_number", "message_type")
    readonly_fields = fields
    ordering = ("-created_at",)


class GroupSessionsInline(ReadonlyTabularInline):
    model = GroupSession
    fields = ("week_number", "message_type", "current_strategy_phase")
    readonly_fields = fields
    ordering = ("-created_at",)


class UsersInline(ReadonlyTabularInline):
    model = User
    fields = ("name", "school_name", "school_mascot", "is_test")
    readonly_fields = fields
    ordering = ("created_at",)


class IndividualChatTranscriptInline(ReadonlyTabularInline):
    model = IndividualChatTranscript
    fields = ("role", "content", "moderation_status", "created_at")
    readonly_fields = fields
    ordering = ("-created_at",)


class GroupChatTranscriptInline(ReadonlyTabularInline):
    @admin.display(description="Sender")
    def combined_sender(self, obj):
        if obj.role == BaseChatTranscript.Role.USER:
            return format_html('<a href="/admin/chat/user/{}">{}</a>', obj.sender.id, obj.sender)
        else:
            return obj.get_role_display()

    model = GroupChatTranscript
    fields = ("combined_sender", "assistant_strategy_phase", "content", "moderation_status", "created_at")
    readonly_fields = fields
    ordering = ("-created_at",)


@admin.register(User)
class UserAdmin(ReadonlyAdmin):
    list_display = ("name", "school_name", "school_mascot", "is_test", "group")
    search_fields = ("name",)
    list_filter = ("is_test", "school_name")

    inlines = [IndividualSessionsInline]


@admin.register(Group)
class GroupAdmin(ReadonlyAdmin):
    list_display = ("__str__", "id", "get_user_count", "is_test")
    search_fields = ("id",)
    list_filter = ("is_test",)

    @admin.display(description="User Count")
    def get_user_count(self, obj):
        return obj.users.count()

    inlines = [UsersInline, GroupSessionsInline]


class IndividualPipelineRecordInline(ReadonlyTabularInline):
    model = IndividualPipelineRecord
    fields = ("run_id", "status", "instruction_prompt", "updated_at")
    readonly_fields = fields
    ordering = ("-created_at",)
    extra = 0
    max_num = 1
    can_delete = False


class GroupPipelineRecordInline(ReadonlyTabularInline):
    model = GroupPipelineRecord
    fields = ("run_id", "status", "instruction_prompt", "updated_at")
    readonly_fields = fields
    ordering = ("-created_at",)
    extra = 0
    max_num = 1
    can_delete = False


@admin.register(IndividualChatTranscript)
class IndividualChatTranscriptAdmin(ReadonlyAdmin):
    list_display = (
        "session",
        "session__user",
        "role",
        "content",
        "moderation_status",
        "created_at",
        "pipeline_record_link",
    )
    search_fields = ("content",)
    list_filter = ("role",)
    inlines = [IndividualPipelineRecordInline]

    def pipeline_record_link(self, obj):
        rec = obj.pipeline_records.first()
        if not rec:
            return "-"
        url = reverse("admin:chat_individualpipelinerecord_change", args=[rec.id])
        return format_html('<a href="{}">{}</a>', url, rec.run_id)


@admin.register(GroupChatTranscript)
class GroupChatTranscriptAdmin(ReadonlyAdmin):
    @admin.display(description="Sender")
    def combined_sender(self, obj):
        if obj.role == BaseChatTranscript.Role.USER:
            return format_html('<a href="/admin/chat/user/{}">{}</a>', obj.sender.id, obj.sender)
        else:
            return obj.get_role_display()

    list_display = (
        "session",
        "combined_sender",
        "assistant_strategy_phase",
        "content",
        "moderation_status",
        "created_at",
        "pipeline_record_link",
    )
    search_fields = ("content",)
    list_filter = ("role",)
    inlines = [GroupPipelineRecordInline]

    def pipeline_record_link(self, obj):
        rec = obj.pipeline_records.first()
        if not rec:
            return "-"
        url = reverse("admin:chat_grouppipelinerecord_change", args=[rec.id])
        return format_html('<a href="{}">{}</a>', url, rec.run_id)


@admin.register(IndividualPrompt)
class IndividualPromptAdmin(EditableAdmin):
    list_display = ("week", "activity", "message_type")
    search_fields = ("activity",)
    list_filter = ("week", "message_type")


@admin.register(GroupPrompt)
class GroupPromptAdmin(EditableAdmin):
    list_display = ("week", "activity", "message_type", "strategy_type")
    search_fields = ("activity",)
    list_filter = ("week", "message_type", "strategy_type")


@admin.register(ControlConfig)
class ControlConfigAdmin(EditableAdmin):
    list_display = ("key", "value", "created_at")


@admin.register(Summary)
class SummaryAdmin(BaseAdmin):
    list_display = ("school_name", "week_number", "summary", "selected", "updated_at")
    search_fields = ("summary",)
    list_filter = ("school_name", "week_number", "selected")

    @admin.action(description="Add selections to summary messages")
    def select_summaries(self, request, queryset: QuerySet[Summary]):
        max_allowed_selected_summaries_per_school = 3
        try:
            with transaction.atomic():
                for s in queryset:
                    s.selected = True
                    s.save()
                schools_with_more_than_three_selected_summaries = list(
                    Summary.objects.filter(selected=True)
                    .values("school_name", "week_number")
                    .annotate(selected_count=Count("id"))
                    .filter(selected_count__gt=max_allowed_selected_summaries_per_school)
                )
                if schools_with_more_than_three_selected_summaries:
                    raise ValueError(
                        "Selecting these options would result in the following schools having "
                        f"more than {max_allowed_selected_summaries_per_school} for a given week: "
                        f"summaries: {schools_with_more_than_three_selected_summaries}"
                    )
            handle_summaries_selected_change.delay([str(s.id) for s in queryset])
        except ValueError as e:
            self.message_user(
                request,
                str(e),
                messages.ERROR,
            )

    @admin.action(description="Remove selections from summary messages")
    def deselect_summaries(self, request, queryset: QuerySet[Summary]):
        with transaction.atomic():
            for s in queryset:
                s.selected = False
                s.save()
        handle_summaries_selected_change.delay([str(s.id) for s in queryset])

    actions = [
        "select_summaries",
        "deselect_summaries",
    ]


@admin.register(GroupStrategyPhaseConfig)
class GroupStrategyPhaseConfigAdmin(EditableAdmin):
    list_display = ("group_strategy_phase", "min_wait_seconds", "max_wait_seconds")


@admin.register(IndividualPipelineRecord)
class IndividualPipelineRecordAdmin(ReadonlyAdmin):
    list_display = (
        "user",
        "transcript",
        "status",
        "is_for_group_direct_messaging",
        "message",
        "validated_message",
        "error_log",
        "updated_at",
    )
    search_fields = ("message", "validated_message", "error_log")
    list_filter = ("status",)


@admin.register(GroupPipelineRecord)
class GroupPipelineRecordAdmin(ReadonlyAdmin):
    list_display = ("user", "transcript", "status", "message", "validated_message", "error_log", "updated_at")
    search_fields = ("message", "validated_message", "error_log")
    list_filter = ("status",)


@admin.register(IndividualSession)
class IndividualSessionAdmin(ReadonlyAdmin):
    list_display = ("user", "week_number", "message_type")
    list_filter = ("week_number", "message_type")

    inlines = [IndividualChatTranscriptInline]


@admin.register(GroupSession)
class GroupSessionAdmin(ReadonlyAdmin):
    list_display = ("group", "week_number", "message_type", "current_strategy_phase")
    list_filter = ("week_number", "message_type")

    inlines = [GroupChatTranscriptInline]
