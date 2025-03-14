from django.contrib import admin
from .models import User, Group, ChatTranscript, GroupChatTranscript, Prompt, Control, Summary, StrategyPrompt, IndividualPipelineRecord, GroupPipelineRecord

admin.site.register(User)
admin.site.register(Group)
admin.site.register(ChatTranscript)
admin.site.register(GroupChatTranscript)
admin.site.register(Prompt)
admin.site.register(Control)
admin.site.register(Summary)
admin.site.register(StrategyPrompt)
admin.site.register(IndividualPipelineRecord)
admin.site.register(GroupPipelineRecord)
