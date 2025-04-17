import logging
from django.contrib import admin
from .models import (
    ControlConfig,
    GroupSession,
    User,
    Group,
    IndividualChatTranscript,
    GroupChatTranscript,
    Prompt,
    Summary,
    IndividualPipelineRecord,
    GroupPipelineRecord,
    IndividualSession,
)
from admin.models import AuthGroupName
from simple_history.admin import SimpleHistoryAdmin

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
    fields = ("week_number", "message_type")
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
    model = GroupChatTranscript
    fields = ("sender", "role", "content", "moderation_status", "created_at")
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
    list_display = ("id", "get_user_count", "is_test")
    search_fields = ("id",)
    list_filter = ("is_test",)

    @admin.display(description="User Count")
    def get_user_count(self, obj):
        return obj.users.count()

    inlines = [UsersInline, GroupSessionsInline]


@admin.register(IndividualChatTranscript)
class IndividualChatTranscriptAdmin(ReadonlyAdmin):
    list_display = ("session", "session__user", "role", "content", "moderation_status", "created_at")
    search_fields = ("content",)
    list_filter = ("role",)


@admin.register(GroupChatTranscript)
class GroupChatTranscriptAdmin(ReadonlyAdmin):
    list_display = ("session", "session__group", "sender", "role", "content", "moderation_status", "created_at")
    search_fields = ("content",)
    list_filter = ("role",)


@admin.register(Prompt)
class PromptAdmin(BaseAdmin):
    list_display = ("week", "activity", "type")
    search_fields = ("activity",)
    list_filter = ("week", "type")


@admin.register(ControlConfig)
class ControlConfigAdmin(BaseAdmin):
    list_display = ("key", "value", "created_at")


@admin.register(Summary)
class SummaryAdmin(BaseAdmin):
    list_display = ("school", "type", "summary", "updated_at")
    search_fields = ("summary",)
    list_filter = ("school", "type")


@admin.register(IndividualPipelineRecord)
class IndividualPipelineRecordAdmin(ReadonlyAdmin):
    list_display = (
        "user",
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
    list_display = ("user", "status", "message", "validated_message", "error_log", "updated_at")
    search_fields = ("message", "validated_message", "error_log")
    list_filter = ("status",)


@admin.register(IndividualSession)
class IndividualSessionAdmin(ReadonlyAdmin):
    list_display = ("user", "week_number", "message_type")
    list_filter = ("week_number", "message_type")

    inlines = [IndividualChatTranscriptInline]


@admin.register(GroupSession)
class GroupSessionAdmin(ReadonlyAdmin):
    list_display = ("group", "week_number", "message_type")
    list_filter = ("week_number", "message_type")

    inlines = [GroupChatTranscriptInline]
