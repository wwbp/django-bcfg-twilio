import logging
from django.contrib import admin
from .models import (
    User,
    Group,
    ChatTranscript,
    GroupChatTranscript,
    Prompt,
    Control,
    Summary,
    IndividualPipelineRecord,
    GroupPipelineRecord,
)

log = logging.getLogger(__name__)


class BaseAdmin(admin.ModelAdmin):
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
        if request.user.is_staff and (  # type: ignore
            "Unlock Restricted Content" in request.user.groups.values_list("name", flat=True)  # type: ignore
        ):
            return super().has_change_permission(request, obj)
        else:
            return False


class ReadonlyTabularInline(admin.TabularInline):
    fields = ()
    extra = 0
    ordering = ("timestamp",)
    can_delete = False
    has_add_permission = lambda self, request, obj: False  # type: ignore
    template = "admin/read_only_tabular.html"
    classes = ["collapse", "collapsed"]

    def has_change_permission(self, request, obj=None):
        return False


class UserGroupsInline(ReadonlyTabularInline):
    model = Group.users.through
    fields = ("group", "get_group_is_test")
    readonly_fields = fields
    ordering = ("group__created_at",)

    def get_group_is_test(self, obj):
        return obj.user.is_test


class GroupUsersInline(ReadonlyTabularInline):
    model = User.groups.through
    fields = ("user", "get_user_school_name", "get_user_school_mascot", "get_user_is_test")
    readonly_fields = fields
    ordering = ("user__created_at",)

    def get_user_school_name(self, obj):
        return obj.user.school_name

    def get_user_school_mascot(self, obj):
        return obj.user.school_mascot

    def get_user_is_test(self, obj):
        return obj.user.is_test


class ChatTranscriptInline(ReadonlyTabularInline):
    model = ChatTranscript
    fields = ("role", "content", "created_at")
    readonly_fields = fields
    ordering = ("-created_at",)


class GroupChatTranscriptInline(ReadonlyTabularInline):
    model = GroupChatTranscript
    fields = ("group", "sender", "role", "content", "created_at")
    readonly_fields = fields
    ordering = ("-created_at",)


@admin.register(User)
class UserAdmin(ReadonlyAdmin):
    list_display = ("name", "school_name", "school_mascot", "is_test")
    search_fields = ("name",)
    list_filter = ("is_test", "school_name")

    inlines = [UserGroupsInline, ChatTranscriptInline, GroupChatTranscriptInline]


@admin.register(Group)
class GroupAdmin(ReadonlyAdmin):
    list_display = ("id", "get_user_count", "is_test")
    search_fields = ("id",)
    list_filter = ("is_test",)

    @admin.display(description="User Count")
    def get_user_count(self, obj):
        return obj.users.count()

    inlines = [GroupUsersInline, GroupChatTranscriptInline]


@admin.register(ChatTranscript)
class ChatTranscriptAdmin(ReadonlyAdmin):
    list_display = ("user", "role", "content", "created_at")
    search_fields = ("content",)
    list_filter = ("role",)


@admin.register(GroupChatTranscript)
class GroupChatTranscriptAdmin(ReadonlyAdmin):
    list_display = ("group", "sender", "role", "content", "created_at")
    search_fields = ("content",)
    list_filter = ("role",)


@admin.register(Prompt)
class PromptAdmin(BaseAdmin):
    list_display = ("week", "activity", "type")
    search_fields = ("activity",)
    list_filter = ("week", "type")


@admin.register(Control)
class ControlAdmin(BaseAdmin):
    list_display = ("persona", "system", "default", "moderation", "created_at")
    search_fields = (
        "persona",
        "system",
        "default",
        "moderation",
    )


@admin.register(Summary)
class SummaryAdmin(BaseAdmin):
    list_display = ("school", "type", "summary", "updated_at")
    search_fields = ("summary",)
    list_filter = ("school", "type")


@admin.register(IndividualPipelineRecord)
class IndividualPipelineRecordAdmin(ReadonlyAdmin):
    list_display = ("participant_id", "status", "message", "validated_message", "error_log", "updated_at")
    search_fields = ("message", "validated_message", "error_log")
    list_filter = ("status",)


@admin.register(GroupPipelineRecord)
class GroupPipelineRecordAdmin(ReadonlyAdmin):
    list_display = ("group_id", "get_status", "error_log", "updated_at")
    search_fields = ("error_log",)
    list_filter = ("ingested", "processed", "sent", "failed")

    @admin.display(description="Status")
    def get_status(self, obj):
        if obj.ingested:
            return "Ingested"
        elif obj.processed:
            return "Processed"
        elif obj.sent:
            return "Sent"
        elif obj.failed:
            return "Failed"
        else:
            return "Pending"
