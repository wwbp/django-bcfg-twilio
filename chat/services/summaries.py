import datetime
import logging
import json
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from chat.models import (
    BaseChatTranscript,
    GroupChatTranscript,
    IndividualChatTranscript,
    Summary,
    SundaySummaryPrompt,
    User,
)
from chat.services.send import send_school_summaries_to_hub_for_week
from chat.services.completion import generate_response

logger = logging.getLogger(__name__)


def _get_chat_datetime_filter_to_determine_week_number() -> datetime.datetime:
    # We use this filter to figure out the week number from the current chats
    # We don't have each school's timezone, and we don't want to include chats
    # before the first interaction goes out on Monday
    # Each interaciton starts at 11am local timezone and the latest timezone is PST
    # so we filter here assuming the worst case of UTC-8 and give a 30 minute buffer
    # for all chats to be sent
    # The downside is that if ALL participants at a school ONLY chat before this filter,
    # we won't get a summary for that school, but that is very unlikely
    today = datetime.date.today()
    day_of_week = today.weekday()
    monday_delta = datetime.timedelta(days=day_of_week)
    most_recent_monday = today - monday_delta
    most_recent_monday_1930_utc = datetime.datetime.combine(most_recent_monday, datetime.time(19, 30, 0))
    return timezone.make_aware(most_recent_monday_1930_utc)


def _get_week_number_for_school(school_name: str, filter_chats_since: datetime.datetime) -> int | None:
    most_recent_individual_chat = (
        IndividualChatTranscript.objects.filter(
            session__user__school_name=school_name,
            session__user__is_test=False,
            created_at__gte=filter_chats_since,
        )
        .order_by("-created_at")
        .first()
    )
    if most_recent_individual_chat:
        return most_recent_individual_chat.session.week_number
    most_recent_group_chat = (
        GroupChatTranscript.objects.filter(
            session__group__users__school_name=school_name,
            session__group__is_test=False,
            created_at__gte=filter_chats_since,
        )
        .order_by("-created_at")
        .first()
    )
    if most_recent_group_chat:
        return most_recent_group_chat.session.week_number
    return None


def _get_all_chats_for_school(
    school_name: str, school_week_number: int
) -> tuple[list[IndividualChatTranscript], list[GroupChatTranscript]]:
    all_individual_school_chats = list(
        IndividualChatTranscript.objects.filter(
            session__week_number=school_week_number,
            session__user__school_name=school_name,
            session__user__is_test=False,
        )
        .order_by("-created_at")
        .distinct("created_at", "id")
    )
    all_group_school_chats = list(
        GroupChatTranscript.objects.filter(
            session__week_number=school_week_number,
            session__group__users__school_name=school_name,
            session__group__is_test=False,
        )
        .order_by("-created_at")
        .distinct("created_at", "id")
    )
    return all_individual_school_chats, all_group_school_chats


def _parse_top_10_summaries(response: str) -> list[str]:
    """
    Parse an LLM response into exactly 10 summary strings.
    Fallbacks: return the entire response as a single‐element list.
    """
    resp = response.strip()
    try:
        items = json.loads(resp)
        # If it parsed but isn’t a list, treat as non-JSON
        if not isinstance(items, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        return [response]
    return items


def _generate_top_10_summaries_for_school(
    school_name: str,
    school_week_number: int,
    all_individual_school_chats: list[IndividualChatTranscript],
    all_group_school_chats: list[GroupChatTranscript],
) -> list[str]:
    """
    Generate top 10 summaries for a given school via an LLM.
    """
    # assemble prompt
    try:
        instructions = SundaySummaryPrompt.objects.get(week=school_week_number).activity
    except SundaySummaryPrompt.DoesNotExist as err:
        logger.error(f"Error retrieving Sunday Summary Prompt for week '{school_week_number}': {err}")
        raise
    transcript: list[dict] = []
    for t in all_group_school_chats:
        transcript.append(
            {
                "role": t.role,
                "content": t.content,
                "name": t.sender.name if t.role == BaseChatTranscript.Role.USER else "assistant",
            }
        )
    for t in all_individual_school_chats:
        transcript.append(
            {
                "role": t.role,
                "content": t.content,
                "name": t.session.user.name if t.role == BaseChatTranscript.Role.USER else "assistant",
            }
        )
    # call LLM
    response = generate_response(transcript, instructions, "")
    # validate response
    summaries = _parse_top_10_summaries(response)
    return summaries


def _persist_summaries(school_name: str, week_number: int, summaries: list[str]):
    """
    Persist summaries to the database.
    """
    with transaction.atomic():
        Summary.objects.filter(school_name=school_name, week_number=week_number).all().delete()
        for summary in summaries:
            Summary.objects.create(
                school_name=school_name,
                week_number=week_number,
                summary=summary,
            )


@shared_task
def generate_weekly_summaries():
    """
    Generate weekly summaries for all schools.
    """
    all_unique_school_names = list(
        User.objects.values_list("school_name", flat=True).distinct().order_by("school_name")
    )
    for school_name in all_unique_school_names:
        filter_chats_since = _get_chat_datetime_filter_to_determine_week_number()
        school_week_number = _get_week_number_for_school(school_name, filter_chats_since)
        if school_week_number is None:
            logger.warning(
                f"No chats found for {school_name} this week (since {filter_chats_since.isoformat()}), skipping."
            )
            continue
        all_individual_school_chats, all_group_school_chats = _get_all_chats_for_school(school_name, school_week_number)

        summaries = _generate_top_10_summaries_for_school(
            school_name, school_week_number, all_individual_school_chats, all_group_school_chats
        )
        _persist_summaries(school_name, school_week_number, summaries)


@shared_task
def handle_summaries_selected_change(changed_summary_ids: list[str]):
    """
    Handle the change in selected summaries by sending all selected summaries
    to the BCFG endpoint for any schools and weeks involed in the change.
    """
    changed_summaries = list(Summary.objects.filter(id__in=changed_summary_ids))
    schools_and_weeks_included = {(s.school_name, s.week_number) for s in changed_summaries}
    for school_name, week_number in schools_and_weeks_included:
        summaries = list(Summary.objects.filter(school_name=school_name, week_number=week_number, selected=True))
        send_school_summaries_to_hub_for_week(school_name, week_number, [s.summary for s in summaries])
