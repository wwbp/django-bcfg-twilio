# tester/models.py
from django.db import models


class ChatResponse(models.Model):
    participant_id = models.CharField(max_length=255)
    # Optionally store original request context if needed.
    request_context = models.JSONField(null=True, blank=True)
    bot_response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Response for {self.participant_id} at {self.created_at}"
