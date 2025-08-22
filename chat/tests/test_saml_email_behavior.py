from unittest.mock import patch
from django.contrib.auth.models import User as AuthUser
from djangosaml2.backends import Saml2Backend
from django.conf import settings
from chat.backends import CustomSaml2Backend


def test_saml_email_overwrite_behavior():
    """
    Test that SAML authentication overwrites manually set email addresses.
    """
    auth_user = AuthUser.objects.create_user(
        username="testuser", email="manual@example.com", first_name="Test", last_name="User"
    )

    assert auth_user.email == "manual@example.com"

    saml_attributes = {
        "eduPersonPrincipalName": ["testuser"],
        "mail": ["testuser@upenn.edu"],
        "givenName": ["Test"],
        "sn": ["User"],
    }

    attribute_mapping = settings.SAML_ATTRIBUTE_MAPPING

    backend = Saml2Backend()
    backend._update_user(auth_user, saml_attributes, attribute_mapping, force_save=True)

    auth_user.refresh_from_db()

    assert auth_user.email == "testuser@upenn.edu"
    assert auth_user.email != "manual@example.com"


def test_custom_backend_preserves_existing_email():
    """
    Test that custom backend preserves manually set email addresses.
    """
    auth_user = AuthUser.objects.create_user(
        username="testuser2", email="manual@example.com", first_name="Test", last_name="User"
    )

    assert auth_user.email == "manual@example.com"

    saml_attributes = {
        "eduPersonPrincipalName": ["testuser2"],
        "mail": ["testuser2@upenn.edu"],
        "givenName": ["Test"],
        "sn": ["User"],
    }

    attribute_mapping = settings.SAML_ATTRIBUTE_MAPPING

    backend = CustomSaml2Backend()
    backend.update_user(auth_user, saml_attributes, attribute_mapping, force_save=True)

    auth_user.refresh_from_db()

    # Email should be preserved
    assert auth_user.email == "manual@example.com"
    assert auth_user.email != "testuser2@upenn.edu"


def test_custom_backend_populates_empty_email():
    """
    Test that custom backend populates email when it's empty.
    """
    auth_user = AuthUser.objects.create_user(username="testuser3", email="", first_name="Test", last_name="User")

    assert auth_user.email == ""

    saml_attributes = {
        "eduPersonPrincipalName": ["testuser3"],
        "mail": ["testuser3@upenn.edu"],
        "givenName": ["Test"],
        "sn": ["User"],
    }

    attribute_mapping = settings.SAML_ATTRIBUTE_MAPPING

    backend = CustomSaml2Backend()
    backend._update_user(auth_user, saml_attributes, attribute_mapping, force_save=True)

    auth_user.refresh_from_db()

    # Email should be populated
    assert auth_user.email == "testuser3@upenn.edu"


def test_custom_backend_updates_other_attributes():
    """
    Test that custom backend still updates other attributes correctly.
    """
    auth_user = AuthUser.objects.create_user(
        username="testuser4", email="manual@example.com", first_name="Old", last_name="Name"
    )

    assert auth_user.email == "manual@example.com"
    assert auth_user.first_name == "Old"
    assert auth_user.last_name == "Name"

    saml_attributes = {
        "eduPersonPrincipalName": ["testuser4"],
        "mail": ["testuser4@upenn.edu"],
        "givenName": ["New"],
        "sn": ["Surname"],
    }

    attribute_mapping = settings.SAML_ATTRIBUTE_MAPPING

    backend = CustomSaml2Backend()
    backend.update_user(auth_user, saml_attributes, attribute_mapping, force_save=True)

    auth_user.refresh_from_db()

    # Email should be preserved
    assert auth_user.email == "manual@example.com"
    assert auth_user.email != "testuser4@upenn.edu"

    # Other attributes should be updated
    assert auth_user.first_name == "New"
    assert auth_user.last_name == "Surname"


def test_custom_backend_logging_works():
    """
    Test that our custom backend logging works correctly.
    """
    auth_user = AuthUser.objects.create_user(
        username="logtest", email="manual@example.com", first_name="Test", last_name="User"
    )

    saml_attributes = {
        "eduPersonPrincipalName": ["logtest"],
        "mail": ["logtest@upenn.edu"],
        "givenName": ["Test"],
        "sn": ["User"],
    }

    attribute_mapping = settings.SAML_ATTRIBUTE_MAPPING

    # Capture log output
    with patch("chat.backends.logger") as mock_logger:
        backend = CustomSaml2Backend()
        backend._update_user(auth_user, saml_attributes, attribute_mapping, force_save=True)

        # Verify that logging methods were called
        mock_logger.info.assert_called()
        
        # Get all log calls
        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        
        # Check for key log messages
        assert any("CustomSaml2Backend._update_user called" in call for call in log_calls)
        assert any("Preserving existing email" in call for call in log_calls)

    # Verify the email was actually preserved
    auth_user.refresh_from_db()
    assert auth_user.email == "manual@example.com"


def test_debug_saml_flow_issues():
    """
    Debug why custom backend might not be working in staging.
    """
    print("=== DEBUGGING SAML FLOW ISSUES ===")

    # Test 1: Check if our custom backend is actually being used
    print(f"1. AUTHENTICATION_BACKENDS: {settings.AUTHENTICATION_BACKENDS}")
    print(f"2. REQUIRE_SAML_AUTHENTICATION: {settings.REQUIRE_SAML_AUTHENTICATION}")

    # Test 2: Check what happens when we call the parent method directly
    auth_user = AuthUser.objects.create_user(
        username="debug_parent", email="debug_parent@example.com", first_name="Debug", last_name="Parent"
    )

    print(f"3. Created user: {auth_user.username}, email: {auth_user.email}")

    saml_attributes = {
        "eduPersonPrincipalName": ["debug_parent"],
        "mail": ["debug_parent@upenn.edu"],
        "givenName": ["NewDebug"],
        "sn": ["NewParent"],
    }

    attribute_mapping = settings.SAML_ATTRIBUTE_MAPPING
    print(f"4. SAML_ATTRIBUTE_MAPPING: {attribute_mapping}")
    print(f"5. SAML attributes: {saml_attributes}")

    # Test 3: Call parent method directly to see what it does
    parent_backend = Saml2Backend()
    print("6. Calling parent Saml2Backend._update_user...")
    parent_backend._update_user(auth_user, saml_attributes, attribute_mapping, force_save=True)

    auth_user.refresh_from_db()
    print(f"7. After parent update: email='{auth_user.email}', first_name='{auth_user.first_name}'")

    # Test 4: Now test our custom backend
    auth_user2 = AuthUser.objects.create_user(
        username="debug_custom", email="debug_custom@example.com", first_name="Debug", last_name="Custom"
    )

    print(f"8. Created user2: {auth_user2.username}, email: {auth_user2.email}")

    custom_backend = CustomSaml2Backend()
    print("9. Calling CustomSaml2Backend._update_user...")
    custom_backend._update_user(auth_user2, saml_attributes, attribute_mapping, force_save=True)

    auth_user2.refresh_from_db()
    print(f"10. After custom update: email='{auth_user2.email}', first_name='{auth_user2.first_name}'")

    # Test 5: Check if the issue is with the deprecated method
    print(f"11. Parent method overwrote email: {auth_user.email == 'debug_parent@upenn.edu'}")
    print(f"12. Custom method preserved email: {auth_user2.email == 'debug_custom@example.com'}")

    print("=== END DEBUGGING ===")


def test_custom_backend_import_and_instantiation():
    """
    Test that the custom backend can be imported and instantiated.
    This helps debug deployment issues in staging.
    """
    print("=== TESTING CUSTOM BACKEND IMPORT ===")

    try:
        # Test 1: Can we import the custom backend?
        from chat.backends import CustomSaml2Backend

        print("✓ CustomSaml2Backend imported successfully")

        # Test 2: Can we instantiate it?
        backend = CustomSaml2Backend()
        print("✓ CustomSaml2Backend instantiated successfully")

        # Test 3: Check if it's in the authentication backends
        print(f"Current AUTHENTICATION_BACKENDS: {settings.AUTHENTICATION_BACKENDS}")
        custom_backend_path = "chat.backends.CustomSaml2Backend"
        if custom_backend_path in settings.AUTHENTICATION_BACKENDS:
            print(f"✓ {custom_backend_path} is in AUTHENTICATION_BACKENDS")
        else:
            print(f"✗ {custom_backend_path} is NOT in AUTHENTICATION_BACKENDS")

        # Test 4: Check the actual backend class
        print(f"Backend class: {type(backend)}")
        print(f"Backend module: {backend.__class__.__module__}")

        print("=== IMPORT TEST PASSED ===")

    except ImportError as e:
        print(f"✗ ImportError: {e}")
        print("This would cause issues in staging deployment")
    except Exception as e:
        print(f"✗ Exception: {e}")
        print("This would cause issues in staging deployment")
