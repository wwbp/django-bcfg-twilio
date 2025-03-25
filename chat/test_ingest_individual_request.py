from django.test import TestCase
from chat.models import User, ChatTranscript
from chat.crud import ingest_individual_request


class IngestIndividualRequestTests(TestCase):
    """
    Tests for the ingest_individual_request function which handles the processing
    of incoming data for a participant. This suite verifies both the creation of a
    new user (and associated transcripts) as well as updates to existing users.
    """

    def test_new_user_creation(self):
        """
        When a user is not found, a new record should be created using context data,
        and two ChatTranscript records should be generated (one for assistant, one for user).
        """
        participant_id = "new_user_1"
        input_data = {
            "context": {
                "school_name": "Test High",
                "school_mascot": "Tigers",
                "name": "Alice",
                "initial_message": "Hello, world!",
                "week_number": 1,
            },
            "message": "I would like to enroll.",
        }
        # Call the function under test
        ingest_individual_request(participant_id, input_data)

        # Assert that the user was created with correct attributes
        user = User.objects.get(id=participant_id)
        self.assertEqual(user.school_name, "Test High")
        self.assertEqual(user.school_mascot, "Tigers")
        self.assertEqual(user.name, "Alice")
        self.assertEqual(user.initial_message, "Hello, world!")
        self.assertEqual(user.week_number, 1)

        # Assert that two transcripts were created: one assistant and one user
        transcripts = ChatTranscript.objects.filter(user=user).order_by('id')
        self.assertEqual(transcripts.count(), 2)
        self.assertEqual(transcripts[0].role, "assistant")
        self.assertEqual(transcripts[0].content, "Hello, world!")
        self.assertEqual(transcripts[1].role, "user")
        self.assertEqual(transcripts[1].content, "I would like to enroll.")

    def test_existing_user_update_week_number(self):
        """
        When an existing user sends data with a changed week_number,
        the user record should update and a new user transcript entry should be added.
        """
        participant_id = "existing_week_update"
        # Create initial user record
        user = User.objects.create(
            id=participant_id,
            school_name="Old School",
            school_mascot="Lions",
            name="Bob",
            initial_message="Initial Hello",
            week_number=1,
        )
        # Create an initial transcript to simulate previous ingestion
        ChatTranscript.objects.create(
            user=user, role="assistant", content="Initial Hello")

        # Define input with updated week number
        input_data = {
            "context": {
                "week_number": 2,  # changed week
                # No change in initial_message
            },
            "message": "User message for week 2",
        }
        ingest_individual_request(participant_id, input_data)

        # Refresh user from db and verify week_number updated
        user.refresh_from_db()
        self.assertEqual(user.week_number, 2)
        # initial_message should remain unchanged
        self.assertEqual(user.initial_message, "Initial Hello")

        # Check that a new transcript for the user role has been added.
        transcripts = ChatTranscript.objects.filter(user=user).order_by('id')
        # Expecting: one initial assistant transcript + one new user transcript = 2 total
        self.assertEqual(transcripts.count(), 2)
        self.assertEqual(transcripts.last().role, "user")
        self.assertEqual(transcripts.last().content, "User message for week 2")

    def test_existing_user_update_initial_message(self):
        """
        When an existing user sends a new initial message in the context,
        the user record should update the initial_message, and a new assistant transcript
        should be created reflecting the updated message.
        """
        participant_id = "existing_initial_update"
        # Create initial user record
        user = User.objects.create(
            id=participant_id,
            school_name="Test School",
            school_mascot="Eagles",
            name="Carol",
            initial_message="Old greeting",
            week_number=1,
        )
        # Create an initial transcript for the existing initial message
        ChatTranscript.objects.create(
            user=user, role="assistant", content="Old greeting")

        # Define input with an updated initial message
        input_data = {
            "context": {
                "initial_message": "New greeting",  # new initial message
                # week_number remains the same
            },
            "message": "Follow up message",
        }
        ingest_individual_request(participant_id, input_data)

        # Refresh user from db and verify initial_message updated
        user.refresh_from_db()
        self.assertEqual(user.initial_message, "New greeting")

        # Verify that two new transcripts have been created: one assistant (for the new initial message)
        # and one user (for the new message). Total count should be previous count + 2.
        transcripts = ChatTranscript.objects.filter(user=user).order_by('id')
        # Initially one transcript existed, then two more are added = total of 3.
        self.assertEqual(transcripts.count(), 3)
        # The newly added assistant transcript is the second record
        self.assertEqual(transcripts[1].role, "assistant")
        self.assertEqual(transcripts[1].content, "New greeting")
        # The last transcript is for the user
        self.assertEqual(transcripts.last().role, "user")
        self.assertEqual(transcripts.last().content, "Follow up message")

    def test_existing_user_no_update(self):
        """
        When an existing user sends data with context values identical to what is stored,
        only a new user transcript entry should be created without any user field updates.
        """
        participant_id = "existing_no_update"
        # Create initial user record with specific values
        user = User.objects.create(
            id=participant_id,
            school_name="Same School",
            school_mascot="Bears",
            name="Dave",
            initial_message="Static message",
            week_number=1,
        )
        # Create an initial transcript
        ChatTranscript.objects.create(
            user=user, role="assistant", content="Static message")

        # Define input that does not change week_number or initial_message
        input_data = {
            "context": {
                "week_number": 1,  # same as before
                "initial_message": "Static message",  # same as before
            },
            "message": "Just another message",
        }
        ingest_individual_request(participant_id, input_data)

        # Refresh user from db; no fields should be updated.
        user.refresh_from_db()
        self.assertEqual(user.week_number, 1)
        self.assertEqual(user.initial_message, "Static message")

        # Check that a new transcript for the user role has been added.
        transcripts = ChatTranscript.objects.filter(user=user).order_by('id')
        # Initially one transcript exists, and now one more transcript for the user is added.
        self.assertEqual(transcripts.count(), 2)
        self.assertEqual(transcripts.last().role, "user")
        self.assertEqual(transcripts.last().content, "Just another message")
