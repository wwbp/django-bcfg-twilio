import uuid
from django.test import TestCase
from django.utils import timezone
from chat.models import ChatTranscript, User
from chat.crud import load_individual_chat_history


class LoadChatHistoryTestCase(TestCase):
    def setUp(self):
        # Create a default user for tests with an explicit unique ID.
        self.user = User.objects.create(
            id=str(uuid.uuid4()),
            name="Alice",
            school_mascot="Lion"
        )
        # Create another user for testing assistant without a mascot.
        self.user_no_mascot = User.objects.create(
            id=str(uuid.uuid4()),
            name="Charlie",
            school_mascot=""
        )

    def test_no_transcripts(self):
        history, latest_message = load_individual_chat_history(self.user.id)
        self.assertEqual(history, [])
        self.assertEqual(latest_message, "")

    def test_single_user_transcript(self):
        now = timezone.now()
        ChatTranscript.objects.create(
            user_id=self.user.id,
            user=self.user,
            role="user",
            content="Hello",
            created_at=now
        )
        history, latest_message = load_individual_chat_history(self.user.id)
        self.assertEqual(history, [])
        self.assertEqual(latest_message, "Hello")

    def test_multiple_transcripts(self):
        now = timezone.now()
        # Create an earlier user transcript.
        ChatTranscript.objects.create(
            user_id=self.user.id,
            user=self.user,
            role="user",
            content="Hello",
            created_at=now
        )
        # Create an assistant transcript.
        ChatTranscript.objects.create(
            user_id=self.user.id,
            user=self.user,
            role="assistant",
            content="Hi, how can I help?",
            created_at=now + timezone.timedelta(seconds=10)
        )
        # Create a later user transcript (latest user message).
        ChatTranscript.objects.create(
            user_id=self.user.id,
            user=self.user,
            role="user",
            content="I need assistance",
            created_at=now + timezone.timedelta(seconds=20)
        )

        history, latest_message = load_individual_chat_history(self.user.id)
        expected_history = [
            {
                "role": "user",
                "content": "Hello",
                "name": self.user.name,
            },
            {
                "role": "assistant",
                "content": "Hi, how can I help?",
                "name": self.user.school_mascot,
            },
        ]
        self.assertEqual(history, expected_history)
        self.assertEqual(latest_message, "I need assistance")

    def test_assistant_without_mascot(self):
        now = timezone.now()
        ChatTranscript.objects.create(
            user_id=self.user_no_mascot.id,
            user=self.user_no_mascot,
            role="assistant",
            content="Welcome",
            created_at=now
        )
        ChatTranscript.objects.create(
            user_id=self.user_no_mascot.id,
            user=self.user_no_mascot,
            role="user",
            content="Thank you",
            created_at=now + timezone.timedelta(seconds=5)
        )
        history, latest_message = load_individual_chat_history(
            self.user_no_mascot.id)
        expected_history = [
            {
                "role": "assistant",
                "content": "Welcome",
                "name": "assistant",  # Fallback when school_mascot is empty.
            },
        ]
        self.assertEqual(history, expected_history)
        self.assertEqual(latest_message, "Thank you")
