from uuid import uuid4
from django import template
from django.urls import reverse, NoReverseMatch

register = template.Library()


@register.filter
def check_reverse_with_id(
    view_name,
):
    try:
        # Attempt to reverse the URL with a random UUID
        # This is a placeholder to check if the URL can be reversed
        reverse(view_name, args=[uuid4()])
        return True
    except NoReverseMatch:
        return False
