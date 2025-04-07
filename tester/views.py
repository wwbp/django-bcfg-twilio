# tester/views.py
from chat.models import ChatTranscript, GroupChatTranscript, User as ChatUser, Group
from django.views.decorators.http import require_POST
import json
from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse
from django.urls import reverse
import requests
from tester.models import ChatResponse


class ChatTestInterface(View):
    def get(self, request):
        # Retrieve stored responses to display on the page.
        responses = ChatResponse.objects.order_by("-created_at")
        # responses = [
        #     "Hello, how can I help you?",
        #     "I am a bot, I can help you with your queries.",
        #     "Please provide me with more information.",
        # ]
        test_users = ChatUser.objects.filter(is_test=True)
        return render(request, "tester/chat_interface.html", {"responses": responses, "test_users": test_users})

    def post(self, request):
        # Extract data from the submitted form.
        participant_id = request.POST.get("participant_id")
        name = request.POST.get("name")
        school_name = request.POST.get("school_name")
        school_mascot = request.POST.get("school_mascot")
        initial_message = request.POST.get("initial_message")
        week_number = request.POST.get("week_number")
        message = request.POST.get("message")

        # Build the context as required by the chat app's serializer.
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

        # Construct the URL to call the chat app's ingest endpoint.
        # Note: Make sure the chat app’s URL patterns have a namespace (e.g. app_name = 'chat')
        url = request.build_absolute_uri(reverse("chat:ingest-individual", args=[participant_id]))

        # Make the POST request (synchronously) to the chat app endpoint.
        try:
            response = requests.post(url, json=payload)
            if response.status_code != 202:
                # Optionally, handle errors.
                print("Error from chat endpoint:", response.text)
        except Exception as exc:
            print("Error calling chat endpoint:", exc)

        # Redirect back to the interface (could also pass a status message)
        return redirect("tester:chat-test-interface")


class ReceiveParticipantResponseView(View):
    def post(self, request, id):
        # Parse the incoming JSON payload
        try:
            data = json.loads(request.body)
            bot_response = data.get("message")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # Save the response to the database.
        ChatResponse.objects.create(
            participant_id=id,
            request_context={},  # You could store extra context if available.
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
    message_type = data.get("message_type")

    if participant_id and name:
        # Create the test user.
        user = ChatUser.objects.create(
            id=participant_id,
            name=name,
            school_name=school_name,
            school_mascot=school_mascot,
            initial_message=initial_message,
            is_test=True,
            message_type=message_type,
        )
        # Insert the initial message as the first assistant message in the transcript.
        ChatTranscript.objects.create(user=user, role="assistant", content=initial_message)
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "error": "Missing required fields"}, status=400)


def chat_transcript(request, test_case_id):
    # Query transcript entries for the given test case (assuming test_case_id corresponds to User.id)
    transcripts = ChatTranscript.objects.filter(user__id=test_case_id).order_by("created_at")
    transcript = [
        {
            "role": t.role,  # 'user' or 'assistant'
            "content": t.content,
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for t in transcripts
    ]
    return JsonResponse({"transcript": transcript})


class GroupChatTestInterface(View):
    def get(self, request):
        test_groups = Group.objects.filter(is_test=True)
        groups_data = []
        for group in test_groups:
            # Build a simple string representation for participants as "id:name" pairs.
            participants_str = ", ".join([f"{user.id}:{user.name}" for user in group.users.all()])
            groups_data.append(
                {
                    "id": group.id,
                    "participants": participants_str,
                    "school_name": group.users.first().school_name if group.users.exists() else "",
                    "school_mascot": group.users.first().school_mascot if group.users.exists() else "",
                    "initial_message": group.users.first().initial_message if group.users.exists() else "",
                }
            )
        return render(request, "tester/group_chat_interface.html", {"test_groups": groups_data})


@require_POST
def create_group_test_case(request):
    data = json.loads(request.body)
    group_id = data.get("group_id")
    participants_str = data.get("participants")
    school_name = data.get("school_name")
    school_mascot = data.get("school_mascot")
    initial_message = data.get("initial_message")

    if group_id and participants_str:
        # Create or get the group.
        group, created = Group.objects.get_or_create(id=group_id, defaults={"is_test": True})
        if created:
            group.initial_message = initial_message
            group.save()
        # Process participants (expected format: "id1:name1, id2:name2")
        for pair in participants_str.split(","):
            if ":" in pair:
                uid, name = pair.split(":")
                uid = uid.strip()
                name = name.strip()
                # Create or get the ChatUser.
                user, _ = ChatUser.objects.get_or_create(
                    id=uid,
                    defaults={
                        "name": name,
                        "school_name": school_name,
                        "school_mascot": school_mascot,
                        "initial_message": initial_message,
                        "is_test": True,
                    },
                )
                group.users.add(user)
        # Optionally, add an initial message to the group transcript.
        if initial_message:
            GroupChatTranscript.objects.create(
                group=group,
                sender=None,  # Could be used as a system/assistant message.
                role="assistant",
                content=initial_message,
            )
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "error": "Missing required fields"}, status=400)


def group_chat_transcript(request, group_id):
    # Query group chat transcript entries for the given group.
    transcripts = GroupChatTranscript.objects.filter(group__id=group_id).order_by("created_at")
    transcript = [
        {
            "role": t.role,  # 'user' or 'assistant'
            "content": t.content,
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "sender": t.sender.name if t.sender else "Assistant",
        }
        for t in transcripts
    ]
    return JsonResponse({"transcript": transcript})
