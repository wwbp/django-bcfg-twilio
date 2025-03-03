# tester/views.py
from chat.tasks import add
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
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
        responses = ChatResponse.objects.order_by('-created_at')
        # responses = [
        #     "Hello, how can I help you?",
        #     "I am a bot, I can help you with your queries.",
        #     "Please provide me with more information.",
        # ]
        return render(request, "tester/chat_interface.html", {"responses": responses})

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
