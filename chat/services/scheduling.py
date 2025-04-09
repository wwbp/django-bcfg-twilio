import json
from chat.models import Group, GroupScheduledTaskAssociation
from django.utils import timezone
from django_celery_beat.models import PeriodicTask, ClockedSchedule
from django.db import transaction


def schedule_only_message_for_group(group: Group):
    with transaction.atomic():
        # delete existing tasks
        GroupScheduledTaskAssociation.objects.filter(group=group).delete()

        # create new associations and tasks
        one_minute_in_future = timezone.now() + timezone.timedelta(minutes=1)
        interval, _ = ClockedSchedule.objects.get_or_create(clocked_time=one_minute_in_future)
        task = PeriodicTask.objects.create(
            name=f"PoC task for {group.id}",
            task="chat.tasks.proof_of_concept_task",
            clocked=interval,
            kwargs=json.dumps({"group_id": str(group.id), "some_other_kwarg": True}),
            one_off=True,
        )
        GroupScheduledTaskAssociation.objects.create(group=group, task=task)
