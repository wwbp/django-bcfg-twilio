# tester/views.py
from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import IntegrityError, transaction
from chat.models import (
    BaseChatTranscript,
    GroupSession,
    GroupStrategyPhase,
    IndividualChatTranscript,
    GroupChatTranscript,
    IndividualSession,
    User as ChatUser,
    Group,
)
from django.views.decorators.http import require_POST
import json
from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse
from django.urls import reverse
import requests
from tester.models import ChatResponse


class ChatTestInterface(View, PermissionRequiredMixin):
    def get(self, request):
        # Retrieve stored responses to display on the page.
        responses = ChatResponse.objects.order_by("-created_at")
        test_users = ChatUser.objects.filter(is_test=True)

        return render(
            request,
            "tester/chat_interface.html",
            {
                "responses": responses,
                "test_users": test_users,
                "api_key": settings.INBOUND_MESSAGE_API_KEY,
            },
        )

    def post(self, request):
        participant_id = request.POST.get("participant_id")
        name = request.POST.get("name")
        school_name = request.POST.get("school_name")
        school_mascot = request.POST.get("school_mascot")
        initial_message = request.POST.get("initial_message")
        week_number = request.POST.get("week_number")
        message = request.POST.get("message")

        context_data = {
            "school_name": school_name,
            "school_mascot": school_mascot,
            "initial_message": initial_message,
            "week_number": week_number,
            "name": name,
        }
        payload = {
            "context": context_data,
            "message": message,
        }

        url = request.build_absolute_uri(reverse("chat:ingest-individual", args=[participant_id]))

        try:
            response = requests.post(url, json=payload)
            if response.status_code != 202:
                print("Error from chat endpoint:", response.text)
        except Exception as exc:
            print("Error calling chat endpoint:", exc)

        return redirect("tester:chat-test-interface")


class ReceiveParticipantResponseView(View):
    def post(self, request, id):
        try:
            data = json.loads(request.body)
            bot_response = data.get("message")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        ChatResponse.objects.create(
            participant_id=id,
            request_context={},
            bot_response=bot_response,
        )
        return JsonResponse({"message": "Bot response received"}, status=200)


@require_POST
def create_test_case(request):
    data = json.loads(request.body)
    participant_id = data.get("participant_id")
    name = data.get("name")
    school_name = data.get("school_name")
    school_mascot = data.get("school_mascot")
    initial_message = data.get("initial_message")
    week_number = data.get("week_number")
    message_type = data.get("message_type")

    if participant_id and name:
        try:
            with transaction.atomic():
                user = ChatUser.objects.create(
                    id=participant_id,
                    name=name,
                    school_name=school_name,
                    school_mascot=school_mascot,
                    is_test=True,
                )
        except IntegrityError:
            # Notify the user if the participant id already exists.
            return JsonResponse(
                {"success": False, "error": "Participant ID already exists. Please use a unique ID."}, status=400
            )

        session = IndividualSession.objects.create(
            user=user,
            week_number=week_number,
            message_type=message_type,
        )
        # Insert the initial assistant message into the transcript.
        IndividualChatTranscript.objects.create(
            session=session, role=BaseChatTranscript.Role.ASSISTANT, content=initial_message
        )
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "error": "Missing required fields"}, status=400)


def chat_transcript(request, test_case_id):
    transcript = []
    user = ChatUser.objects.get(id=test_case_id)
    if user.group:
        group_sessions = GroupSession.objects.filter(group=user.group).order_by("created_at")
        for gs in group_sessions:
            group_transcripts = (
                GroupChatTranscript.objects.filter(session=gs)
                .exclude(moderation_status=BaseChatTranscript.ModerationStatus.FLAGGED)
                .order_by("created_at")
            )
            for t in group_transcripts:
                transcript.append(
                    {
                        "role": t.role,
                        "content": t.content,
                        "name": t.sender.name if t.role == BaseChatTranscript.Role.USER else "assistant",
                    }
                )
    individual_transcripts = (
        IndividualChatTranscript.objects.filter(session__user_id=test_case_id)
        .exclude(moderation_status=BaseChatTranscript.ModerationStatus.FLAGGED)
        .order_by("created_at")
    )
    for t in individual_transcripts:
        transcript.append(
            {
                "role": t.role,
                "content": t.content,
                "created_at": t.session.user.name | "assistant",
            }
        )
    return JsonResponse({"transcript": transcript})


class GroupChatTestInterface(View):
    def get(self, request):
        test_groups = Group.objects.filter(is_test=True)
        test_groups_data = []
        for group in test_groups:
            participants_str = ", ".join([f"{user.id}:{user.name}" for user in group.users.all()])
            test_groups_data.append(
                {
                    "group": group,
                    "participants": participants_str,
                    "school_name": group.users.first().school_name if group.users.exists() else "",
                    "school_mascot": group.users.first().school_mascot if group.users.exists() else "",
                }
            )
        return render(
            request,
            "tester/group_chat_interface.html",
            {"test_groups_data": test_groups_data, "api_key": settings.INBOUND_MESSAGE_API_KEY, "has_permission": True},
        )


@require_POST
def create_group_test_case(request):
    data = json.loads(request.body)
    group_id = data.get("group_id")
    participants_str = data.get("participants")
    school_name = data.get("school_name")
    school_mascot = data.get("school_mascot")
    initial_message = data.get("initial_message")
    week_number = data.get("week_number")
    message_type = data.get("message_type")

    if group_id and participants_str:
        try:
            group = Group.objects.create(id=group_id, is_test=True)
            for pair in participants_str.split(","):
                if ":" in pair:
                    uid, name = pair.split(":")
                    uid = uid.strip()
                    name = name.strip()
                    ChatUser.objects.create(
                        id=uid,
                        group=group,
                        name=name,
                        school_name=school_name,
                        school_mascot=school_mascot,
                        is_test=True,
                    )
        except IntegrityError:
            # Notify the user if the group ID already exists.
            return JsonResponse(
                {"success": False, "error": "Group ID or User ID already exists. Please use a unique ID."}, status=400
            )
        session = GroupSession.objects.create(
            group=group,
            week_number=week_number,
            message_type=message_type,
        )
        GroupChatTranscript.objects.create(
            session=session,
            role=BaseChatTranscript.Role.ASSISTANT,
            content=initial_message,
            assistant_strategy_phase=GroupStrategyPhase.AUDIENCE,
        )
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "error": "Missing required fields"}, status=400)


def group_chat_transcript(request, group_id):
    group = Group.objects.get(id=group_id)
    transcripts = (
        GroupChatTranscript.objects.filter(session=group.current_session)
        .exclude(moderation_status=BaseChatTranscript.ModerationStatus.FLAGGED)
        .order_by("created_at")
    )
    transcript = [
        {
            "role": t.role,
            "content": t.content,
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "sender": t.sender.name if t.sender else "Assistant",
        }
        for t in transcripts
    ]
    return JsonResponse({"transcript": transcript})
