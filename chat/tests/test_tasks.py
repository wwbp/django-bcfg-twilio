from django_celery_beat.models import PeriodicTask
from chat.models import GroupScheduledTaskAssociation

from chat.services.scheduling import schedule_only_message_for_group


def test_schedule_only_message_for_group(group_factory):
    assert PeriodicTask.objects.count() == 0
    assert GroupScheduledTaskAssociation.objects.count() == 0

    # schedule initial task
    group = group_factory()
    schedule_only_message_for_group(group)
    assert PeriodicTask.objects.count() == 1
    first_task_pk = PeriodicTask.objects.first().pk
    assert GroupScheduledTaskAssociation.objects.count() == 1
    assert GroupScheduledTaskAssociation.objects.first().group == group
    assert GroupScheduledTaskAssociation.objects.first().task.pk == first_task_pk

    # reschedule and confirm the task is recreated
    schedule_only_message_for_group(group)
    assert PeriodicTask.objects.count() == 1
    second_task_pk = PeriodicTask.objects.first().pk
    assert second_task_pk != first_task_pk
    assert GroupScheduledTaskAssociation.objects.count() == 1
    assert GroupScheduledTaskAssociation.objects.first().group == group
    assert GroupScheduledTaskAssociation.objects.first().task.pk == second_task_pk
