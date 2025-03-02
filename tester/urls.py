# tester/urls.py
from django.urls import path
from .views import ChatTestInterface, ReceiveParticipantResponseView

app_name = "tester"

urlpatterns = [
    path("chat/", ChatTestInterface.as_view(), name="chat-test-interface"),
    # This endpoint will receive bot responses from chat app.
    path("ai/api/participant/<str:id>/send",
         ReceiveParticipantResponseView.as_view(), name="receive-participant-response"),
]
