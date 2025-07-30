from typing import Callable
from django.db.models.signals import post_delete, ModelSignal
from django.apps import apps
from django.db import models

from chat.models import ScheduledTaskAssociation


def connect_signal_to_child_models(abstract_model: models.Model, signal: ModelSignal, receiver_function: Callable):
    """Connects a signal to all concrete subclasses of an abstract model."""
    for model in apps.get_models():
        if issubclass(model, abstract_model) and not model._meta.abstract:
            signal.connect(receiver_function, sender=model)


def on_delete_scheduled_task_associations(sender, instance: ScheduledTaskAssociation, **kwargs):  # noqa: F821
    """Delete ScheduledTask when we delete ScheduledTaskAssociation"""
    instance.task.delete()


connect_signal_to_child_models(ScheduledTaskAssociation, post_delete, on_delete_scheduled_task_associations)
