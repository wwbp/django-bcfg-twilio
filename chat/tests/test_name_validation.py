import pytest
import logging
from unittest.mock import patch

from chat.models import User, MessageType
from chat.serializers import IndividualIncomingMessageSerializer, GroupIncomingMessageSerializer
from chat.services.individual_crud import _validate_and_truncate_name as individual_validate_name
from chat.services.group_crud import _validate_and_truncate_name as group_validate_name
from chat.services.individual_crud import ingest_request as individual_ingest_request
from chat.services.group_crud import ingest_request as group_ingest_request


class TestNameValidationFunction:
    """Test the _validate_and_truncate_name function directly"""

    @pytest.mark.parametrize(
        "name,expected_name,should_log_error",
        [
            ("John Doe", "John Doe", False),
            ("A" * 50, "A" * 50, False),  # Exactly at limit
            ("A" * 30, "A" * 30, False),  # Under limit
            ("A" * 60, "A" * 50, True),   # Over limit - should truncate and log error
            ("", "", False),              # Empty name
            ("A" * 100, "A" * 50, True),  # Way over limit
        ],
    )
    def test_validate_and_truncate_name_individual(self, name, expected_name, should_log_error, caplog):
        """Test individual CRUD name validation function"""
        caplog.set_level(logging.ERROR)
        
        result = individual_validate_name(name, "test_participant_123")
        
        assert result == expected_name
        
        if should_log_error:
            assert f"Name for participant test_participant_123 is too long" in caplog.text
        else:
            assert "Name for participant" not in caplog.text

    @pytest.mark.parametrize(
        "name,expected_name,should_log_error",
        [
            ("John Doe", "John Doe", False),
            ("A" * 50, "A" * 50, False),  # Exactly at limit
            ("A" * 30, "A" * 30, False),  # Under limit
            ("A" * 60, "A" * 50, True),   # Over limit - should truncate and log error
            ("", "", False),              # Empty name
            ("A" * 100, "A" * 50, True),  # Way over limit
        ],
    )
    def test_validate_and_truncate_name_group(self, name, expected_name, should_log_error, caplog):
        """Test group CRUD name validation function"""
        caplog.set_level(logging.ERROR)
        
        result = group_validate_name(name, "test_participant_123")
        
        assert result == expected_name
        
        if should_log_error:
            assert f"Name for participant test_participant_123 is too long" in caplog.text
        else:
            assert "Name for participant" not in caplog.text

    def test_validate_name_without_participant_id(self):
        """Test that function works without participant_id parameter"""
        result = individual_validate_name("John Doe")
        assert result == "John Doe"
        
        result = group_validate_name("John Doe")
        assert result == "John Doe"


class TestIndividualIngestWithNameValidation:
    """Test name validation in individual ingest requests"""

    @pytest.fixture
    def base_context(self):
        return {
            "school_name": "Test High",
            "school_mascot": "Tigers",
            "name": "Alice Johnson",
            "initial_message": "Hello, world!",
            "week_number": 1,
            "message_type": MessageType.INITIAL,
        }

    @pytest.fixture
    def make_input_data(self, base_context):
        def _make(overrides=None, message=""):
            ctx = base_context.copy()
            if overrides:
                ctx.update(overrides)
            return {
                "context": ctx,
                "message": message,
            }
        return _make

    def test_individual_ingest_with_normal_name(self, make_input_data):
        """Test that normal names are processed without truncation"""
        participant_id = "user_normal_name"
        input_data = make_input_data(message="Hello there")
        
        serializer = IndividualIncomingMessageSerializer(data=input_data)
        serializer.is_valid(raise_exception=True)
        individual_incoming_message = serializer.validated_data
        
        individual_ingest_request(participant_id, individual_incoming_message)
        
        user = User.objects.get(id=participant_id)
        assert user.name == "Alice Johnson"

    def test_individual_ingest_with_long_name(self, make_input_data, caplog):
        """Test that long names are truncated during individual ingest"""
        caplog.set_level(logging.ERROR)
        
        participant_id = "user_long_name"
        long_name = "A" * 60  # 60 characters, should be truncated to 50
        input_data = make_input_data(
            overrides={"name": long_name},
            message="Hello there"
        )
        
        serializer = IndividualIncomingMessageSerializer(data=input_data)
        serializer.is_valid(raise_exception=True)
        individual_incoming_message = serializer.validated_data
        
        individual_ingest_request(participant_id, individual_incoming_message)
        
        user = User.objects.get(id=participant_id)
        assert user.name == "A" * 50  # Should be truncated to 50 characters
        assert f"Name for participant {participant_id} is too long" in caplog.text

    def test_individual_ingest_with_exactly_50_char_name(self, make_input_data):
        """Test that names exactly 50 characters are not truncated"""
        participant_id = "user_exact_name"
        exact_name = "A" * 50  # Exactly 50 characters
        input_data = make_input_data(
            overrides={"name": exact_name},
            message="Hello there"
        )
        
        serializer = IndividualIncomingMessageSerializer(data=input_data)
        serializer.is_valid(raise_exception=True)
        individual_incoming_message = serializer.validated_data
        
        individual_ingest_request(participant_id, individual_incoming_message)
        
        user = User.objects.get(id=participant_id)
        assert user.name == "A" * 50
        assert len(user.name) == 50

    def test_individual_ingest_updates_existing_user_with_long_name(self, make_input_data, caplog):
        """Test that existing users with long names are updated and truncated"""
        caplog.set_level(logging.ERROR)
        
        participant_id = "existing_user_long_name"
        
        # Create existing user with short name
        existing_user = User.objects.create(
            id=participant_id,
            name="Short Name",
            school_name="Old School",
            school_mascot="Old Mascot"
        )
        
        # Try to update with long name
        long_name = "B" * 60  # 60 characters, should be truncated to 50
        input_data = make_input_data(
            overrides={"name": long_name},
            message="Hello there"
        )
        
        serializer = IndividualIncomingMessageSerializer(data=input_data)
        serializer.is_valid(raise_exception=True)
        individual_incoming_message = serializer.validated_data
        
        individual_ingest_request(participant_id, individual_incoming_message)
        
        # Refresh from database
        existing_user.refresh_from_db()
        assert existing_user.name == "B" * 50  # Should be truncated to 50 characters
        assert f"Name for participant {participant_id} is too long" in caplog.text


class TestGroupIngestWithNameValidation:
    """Test name validation in group ingest requests"""

    @pytest.fixture
    def base_group_payload(self):
        return {
            "message": "Hello group!",
            "sender_id": "alice123",
            "context": {
                "school_name": "Test High School",
                "school_mascot": "Eagles",
                "week_number": 1,
                "message_type": MessageType.INITIAL,
                "participants": [
                    {
                        "name": "Alice Johnson",
                        "id": "alice123",
                    },
                    {
                        "name": "Bob Smith",
                        "id": "bob456",
                    },
                ],
            },
        }

    @pytest.fixture
    def make_group_input_data(self, base_group_payload):
        def _make(overrides=None):
            payload = base_group_payload.copy()
            if overrides:
                # Handle nested updates for context
                if "context" in overrides:
                    payload["context"].update(overrides["context"])
                    del overrides["context"]
                payload.update(overrides)
            return payload
        return _make

    def test_group_ingest_with_normal_names(self, make_group_input_data):
        """Test that normal names are processed without truncation"""
        group_id = "test_group_normal_names"
        # The base payload already has sender_id="alice123" and participants with id="alice123", so this should work
        input_data = make_group_input_data()
        
        serializer = GroupIncomingMessageSerializer(data=input_data)
        serializer.is_valid(raise_exception=True)
        group_incoming_message = serializer.validated_data
        
        group_ingest_request(group_id, group_incoming_message)
        
        # Check that users were created with correct names
        users = User.objects.filter(group_id=group_id).order_by("id")
        assert users.count() == 2
        assert users[0].name == "Alice Johnson"
        assert users[1].name == "Bob Smith"

    def test_group_ingest_with_long_names(self, make_group_input_data, caplog):
        """Test that long names are truncated during group ingest"""
        caplog.set_level(logging.ERROR)
        
        group_id = "test_group_long_names"
        long_name = "C" * 60  # 60 characters, should be truncated to 50
        
        input_data = make_group_input_data({
            "sender_id": "user_long_name",  # Make sender match the participant
            "context": {
                "participants": [
                    {
                        "name": long_name,
                        "id": "user_long_name",
                    },
                ],
            }
        })
        
        serializer = GroupIncomingMessageSerializer(data=input_data)
        serializer.is_valid(raise_exception=True)
        group_incoming_message = serializer.validated_data
        
        group_ingest_request(group_id, group_incoming_message)
        
        # Check that user was created with truncated name
        user = User.objects.get(id="user_long_name")
        assert user.name == "C" * 50  # Should be truncated to 50 characters
        assert f"Name for participant user_long_name is too long" in caplog.text

    def test_group_ingest_with_mixed_name_lengths(self, make_group_input_data, caplog):
        """Test group ingest with mix of normal and long names"""
        caplog.set_level(logging.ERROR)
        
        group_id = "test_group_mixed_names"
        long_name = "D" * 60  # 60 characters, should be truncated to 50
        
        input_data = make_group_input_data({
            "sender_id": "user_normal",  # Make sender match one of the participants
            "context": {
                "participants": [
                    {
                        "name": "Normal Name",
                        "id": "user_normal",
                    },
                    {
                        "name": long_name,
                        "id": "user_long",
                    },
                ],
            }
        })
        
        serializer = GroupIncomingMessageSerializer(data=input_data)
        serializer.is_valid(raise_exception=True)
        group_incoming_message = serializer.validated_data
        
        group_ingest_request(group_id, group_incoming_message)
        
        # Check both users
        normal_user = User.objects.get(id="user_normal")
        long_user = User.objects.get(id="user_long")
        
        assert normal_user.name == "Normal Name"
        assert long_user.name == "D" * 50  # Should be truncated to 50 characters
        assert f"Name for participant user_long is too long" in caplog.text

    def test_group_ingest_updates_existing_users_with_long_names(self, make_group_input_data, caplog):
        """Test that existing group users with long names are updated and truncated"""
        caplog.set_level(logging.ERROR)
        
        group_id = "test_group_existing_long_names"
        
        # Create existing group and user
        from chat.models import Group
        existing_group = Group.objects.create(id=group_id)
        existing_user = User.objects.create(
            id="existing_user_long",
            name="Old Short Name",
            school_name="Old School",
            school_mascot="Old Mascot",
            group=existing_group
        )
        
        # Try to update with long name
        long_name = "E" * 60  # 60 characters, should be truncated to 50
        
        input_data = make_group_input_data({
            "sender_id": "existing_user_long",
            "context": {
                "participants": [
                    {
                        "name": long_name,
                        "id": "existing_user_long",
                    },
                ],
            }
        })
        
        serializer = GroupIncomingMessageSerializer(data=input_data)
        serializer.is_valid(raise_exception=True)
        group_incoming_message = serializer.validated_data
        
        group_ingest_request(group_id, group_incoming_message)
        
        # Refresh from database
        existing_user.refresh_from_db()
        assert existing_user.name == "E" * 50  # Should be truncated to 50 characters
        assert f"Name for participant existing_user_long is too long" in caplog.text

    def test_group_ingest_with_exactly_50_char_names(self, make_group_input_data):
        """Test that names exactly 50 characters are not truncated"""
        group_id = "test_group_exact_names"
        exact_name = "F" * 50  # Exactly 50 characters
        
        input_data = make_group_input_data({
            "sender_id": "user_exact",  # Make sender match the participant
            "context": {
                "participants": [
                    {
                        "name": exact_name,
                        "id": "user_exact",
                    },
                ],
            }
        })
        
        serializer = GroupIncomingMessageSerializer(data=input_data)
        serializer.is_valid(raise_exception=True)
        group_incoming_message = serializer.validated_data
        
        group_ingest_request(group_id, group_incoming_message)
        
        # Check that user was created with exact name
        user = User.objects.get(id="user_exact")
        assert user.name == "F" * 50
        assert len(user.name) == 50


class TestNameValidationEdgeCases:
    """Test edge cases for name validation"""

    def test_unicode_names(self):
        """Test that unicode names are handled correctly"""
        unicode_name = "José María García López"  # 25 characters
        result = individual_validate_name(unicode_name, "unicode_user")
        assert result == unicode_name
        
        # Test unicode name that's too long
        long_unicode_name = "José María García López " * 3  # 75 characters
        result = individual_validate_name(long_unicode_name, "unicode_user_long")
        assert result == long_unicode_name[:50]
        assert len(result) == 50

    def test_names_with_special_characters(self):
        """Test names with special characters"""
        special_name = "O'Connor-Smith Jr. III"
        result = individual_validate_name(special_name, "special_user")
        assert result == special_name
        
        # Test special name that's too long
        long_special_name = "O'Connor-Smith Jr. III " * 4  # 80 characters
        result = individual_validate_name(long_special_name, "special_user_long")
        assert result == long_special_name[:50]
        assert len(result) == 50

    def test_empty_and_whitespace_names(self):
        """Test empty and whitespace-only names"""
        # Empty name
        result = individual_validate_name("", "empty_user")
        assert result == ""
        
        # Whitespace-only name
        result = individual_validate_name("   ", "whitespace_user")
        assert result == "   "
        
        # Very long whitespace name
        long_whitespace = " " * 60
        result = individual_validate_name(long_whitespace, "long_whitespace_user")
        assert result == " " * 50
        assert len(result) == 50

    def test_consistency_between_individual_and_group_validation(self):
        """Test that both validation functions behave identically"""
        test_cases = [
            "Normal Name",
            "A" * 60,  # Long name
            "A" * 50,  # Exactly at limit
            "A" * 30,  # Short name
            "",        # Empty
            "José María",  # Unicode
        ]
        
        for name in test_cases:
            individual_result = individual_validate_name(name, "test_user")
            group_result = group_validate_name(name, "test_user")
            assert individual_result == group_result, f"Results differ for name: {name}" 