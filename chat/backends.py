import logging
from djangosaml2.backends import Saml2Backend

logger = logging.getLogger(__name__)

class CustomSaml2Backend(Saml2Backend):
    """
    Custom SAML backend that preserves manually set email addresses.
    
    Only updates email if it's currently empty, preventing SAML from
    overwriting emails that were manually set in the admin.
    """
    
    def authenticate(self, request, **credentials):
        """
        Log when our custom backend is being used for authentication.
        """
        logger.info(f"CustomSaml2Backend.authenticate called with credentials: {credentials}")
        result = super().authenticate(request, **credentials)
        if result:
            logger.info(f"CustomSaml2Backend.authenticate successful for user: {result.username}")
        else:
            logger.info("CustomSaml2Backend.authenticate failed")
        return result
    
    def update_user(self, user, attributes, attribute_mapping, force_save=False):
        """
        Update user with SAML attributes, but preserve manually set emails.
        """
        logger.info(f"CustomSaml2Backend.update_user called for user {user.username}")
        logger.info(f"Current email: '{user.email}'")
        logger.info(f"SAML attributes: {attributes}")
        
        # Check if we have email attributes and the user has an existing email
        if "mail" in attributes and attributes["mail"]:
            saml_email = attributes["mail"][0]
            current_email = user.email
            
            logger.info(f"SAML email: '{saml_email}', Current email: '{current_email}'")
            
            # Only update email if it's empty
            if current_email and current_email.strip():
                logger.info(f"Preserving existing email: '{current_email}' (SAML would set: '{saml_email}')")
                # Remove email from attributes to prevent overwrite
                attributes = {k: v for k, v in attributes.items() if k != "mail"}
                logger.info(f"Modified attributes (email removed): {attributes}")
            else:
                logger.info(f"Updating empty email with SAML email: '{saml_email}'")
        else:
            logger.info("No email attributes in SAML response")
        
        # Call parent method with potentially modified attributes
        result = super().update_user(user, attributes, attribute_mapping, force_save)
        
        # Log the final state
        user.refresh_from_db()
        logger.info(f"Final email after update: '{user.email}'")
        
        return result
