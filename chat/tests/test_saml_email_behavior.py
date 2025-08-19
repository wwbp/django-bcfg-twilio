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
    backend.update_user(auth_user, saml_attributes, attribute_mapping, force_save=True)

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
    auth_user = AuthUser.objects.create_user(
        username="testuser3", email="", first_name="Test", last_name="User"
    )

    assert auth_user.email == ""

    saml_attributes = {
        "eduPersonPrincipalName": ["testuser3"],
        "mail": ["testuser3@upenn.edu"],
        "givenName": ["Test"],
        "sn": ["User"],
    }

    attribute_mapping = settings.SAML_ATTRIBUTE_MAPPING

    backend = CustomSaml2Backend()
    backend.update_user(auth_user, saml_attributes, attribute_mapping, force_save=True)

    auth_user.refresh_from_db()

    # Email should be populated
    assert auth_user.email == "testuser3@upenn.edu"


def test_custom_backend_updates_other_attributes():
    """
    Test that custom backend still updates other attributes correctly.
    """
    auth_user = AuthUser.objects.create_user(
        username="testuser4", 
        email="manual@example.com", 
        first_name="Old", 
        last_name="Name"
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
