# tester/views.py
from chat.models import ChatTranscript
from django.views.decorators.http import require_POST
from chat.tasks import add
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse
from django.urls import reverse
import requests
from chat.models import User as ChatUser
from tester.models import ChatResponse


class ChatTestInterface(View):
    def get(self, request):
        # Retrieve stored responses to display on the page.
        responses = ChatResponse.objects.order_by('-created_at')
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
        context_data = {"school_name": school_name, "school_mascot": school_mascot,
                        "initial_message": initial_message, "week_number": week_number, "name": name}
        payload = {
            "context": context_data,
            "message": message,
        }

        # Construct the URL to call the chat app's ingest endpoint.
        # Note: Make sure the chat app’s URL patterns have a namespace (e.g. app_name = 'chat')
        url = request.build_absolute_uri(
            reverse("chat:ingest-individual", args=[participant_id])
        )

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


@method_decorator(csrf_exempt, name='dispatch')
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
            bot_response=bot_response
        )
        return JsonResponse({"message": "Bot response received"}, status=200)


def test_celery(request):
    # Dispatch the task asynchronously
    task_result = add.delay(3, 4)
    return JsonResponse({
        'message': 'Task submitted successfully!',
        'task_id': task_result.id
    })


@csrf_exempt
@require_POST
def create_test_case(request):
    data = json.loads(request.body)
    participant_id = data.get("participant_id")
    name = data.get("name")
    school_name = data.get("school_name")
    school_mascot = data.get("school_mascot")
    initial_message = data.get("initial_message")

    if participant_id and name:
        # Create the test user.
        user = ChatUser.objects.create(
            id=participant_id,
            name=name,
            school_name=school_name,
            school_mascot=school_mascot,
            initial_message=initial_message,
            is_test=True
        )
        # Insert the initial message as the first assistant message in the transcript.
        ChatTranscript.objects.create(
            user=user,
            role='assistant',
            content=initial_message
        )
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "error": "Missing required fields"}, status=400)


def chat_transcript(request, test_case_id):
    # Query transcript entries for the given test case (assuming test_case_id corresponds to User.id)
    transcripts = ChatTranscript.objects.filter(
        user__id=test_case_id).order_by('created_at')
    transcript = [{
        "role": t.role,  # 'user' or 'assistant'
        "content": t.content,
        "created_at": t.created_at.strftime('%Y-%m-%d %H:%M:%S'),
    } for t in transcripts]
    return JsonResponse({"transcript": transcript})
