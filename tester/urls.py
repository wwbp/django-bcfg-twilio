# tester/urls.py
from django.urls import path
from .views import (
    ChatTestInterface,
    GroupChatTestInterface,
    ReceiveParticipantResponseView,
    chat_transcript,
    create_group_test_case,
    create_test_case,
    group_chat_transcript,
)

app_name = "tester"

urlpatterns = [
    path("individual/", ChatTestInterface.as_view(), name="chat-test-interface"),
    # This endpoint will receive bot responses from chat app.
    path(
        "ai/api/participant/<str:id>/send",
        ReceiveParticipantResponseView.as_view(),
        name="receive-participant-response",
    ),
    path("create-test-case/", create_test_case, name="create-test-case"),
    path("chat_transcript/<str:test_case_id>/", chat_transcript, name="chat-transcript"),
    path("group_chat_transcript/<str:group_id>/", group_chat_transcript, name="group-chat-transcript"),
    path("create-group-test-case/", create_group_test_case, name="create-group-test-case"),
    path("group/", GroupChatTestInterface.as_view(), name="group-chat-test-interface"),
]
