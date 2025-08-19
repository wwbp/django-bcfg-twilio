from djangosaml2.backends import Saml2Backend


class CustomSaml2Backend(Saml2Backend):
    """
    Custom SAML backend that preserves manually set email addresses.
    
    Only updates email if it's currently empty, preventing SAML from
    overwriting emails that were manually set in the admin.
    """
    
    def update_user(self, user, attributes, attribute_mapping, force_save=False):
        """
        Update user with SAML attributes, but preserve manually set emails.
        """
        # Check if we have email attributes and the user has an existing email
        if "mail" in attributes and attributes["mail"]:
            saml_email = attributes["mail"][0]
            current_email = user.email
            
            # Only update email if it's empty
            if current_email and current_email.strip():
                # Remove email from attributes to prevent overwrite
                attributes = {k: v for k, v in attributes.items() if k != "mail"}
        
        # Call parent method with potentially modified attributes
        return super().update_user(user, attributes, attribute_mapping, force_save)
