from typing import Callable
from django.db.models.signals import post_delete, post_save, ModelSignal
from django.apps import apps
from django.db import models

from chat.models import ScheduledTaskAssociation, ControlConfig


def connect_signal_to_child_models(abstract_model: models.Model, signal: ModelSignal, receiver_function: Callable):
    """Connects a signal to all concrete subclasses of an abstract model."""
    for model in apps.get_models():
        if issubclass(model, abstract_model) and not model._meta.abstract:
            signal.connect(receiver_function, sender=model)


def on_delete_scheduled_task_associations(sender, instance: ScheduledTaskAssociation, **kwargs):  # noqa: F821
    """Delete ScheduledTask when we delete ScheduledTaskAssociation"""
    instance.task.delete()


connect_signal_to_child_models(ScheduledTaskAssociation, post_delete, on_delete_scheduled_task_associations)


def clear_control_config_cache(sender, instance: ControlConfig, **kwargs):
    """Clear cache when ControlConfig is updated or deleted"""
    from chat.services.cache import prompt_cache
    cache_key = f"control_config:{instance.key}"
    prompt_cache.delete(cache_key)
    print(f"Cache cleared for key: {cache_key}")


# Connect signals for ControlConfig cache invalidation
post_save.connect(clear_control_config_cache, sender=ControlConfig)
post_delete.connect(clear_control_config_cache, sender=ControlConfig)
