from django.contrib import admin
import tester.views as tester_views

from django.urls import include, path, reverse

tester_view_definitions = [
    ("individual/", tester_views.ChatTestInterface.as_view(), "chat-test-interface"),
    # This endpoint will receive bot responses from chat app.
    (
        "ai/api/participant/<str:id>/send",
        tester_views.ReceiveParticipantResponseView.as_view(),
        "receive-participant-response",
    ),
    ("create-test-case/", tester_views.create_test_case, "create-test-case"),
    ("chat_transcript/<str:test_case_id>/", tester_views.chat_transcript, "chat-transcript"),
    ("group_chat_transcript/<str:group_id>/", tester_views.group_chat_transcript, "group-chat-transcript"),
    ("create-group-test-case/", tester_views.create_group_test_case, "create-group-test-case"),
    ("group/", tester_views.GroupChatTestInterface.as_view(), "group-chat-test-interface"),
]


class MyAdminSite(admin.AdminSite):
    def get_urls(self):
        # self.admin_view forces authentication but does not check permissions/authorization
        tester_view_urls = [path(url, self.admin_view(view), name=name) for url, view, name in tester_view_definitions]
        self._registry = admin.site._registry
        admin_urls = super().get_urls()
        custom_urls = [
            path("test/", include((tester_view_urls, "tester"))),
        ]
        return custom_urls + admin_urls  # custom urls must be at the beginning

    # override _build_app_dict to add custom link to tester pages
    def _build_app_dict(self, request, label=None):
        app_dict = super()._build_app_dict(request, label)
        try:
            fake_test_model_definitions = [
                {
                    "name": "  Individual Prompt Test",  # leading space to force sorting to the top
                    "admin_url": reverse("admin:tester:chat-test-interface"),
                    "view_only": True,
                },
                {
                    "name": "  Group Prompt Test",  # leading space to force sorting to the top
                    "admin_url": reverse("admin:tester:group-chat-test-interface"),
                    "view_only": True,
                },
            ]
            fake_test_models = [
                {
                    **fake_test_model_definition,
                    # do not allow delete, add or change for fake models
                    "perms": {},
                }
                for fake_test_model_definition in fake_test_model_definitions
            ]

            if "chat" in app_dict and "models" in app_dict["chat"]:
                # add the custom links to the tester pages
                app_dict["chat"]["models"].extend(fake_test_models)
        except Exception:
            # if there is an error, fallback to default behavior
            pass

        return app_dict

    site_header = "WWBP - BCFG - AI Chatbot Admin Site"
