from django.views import View
from django import forms
from .models import Prompt, Control
from django.shortcuts import render, redirect, get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import IncomingMessageSerializer, GroupIncomingMessageSerializer
from .ingest import ingest_individual, ingest_group_sync
from .background import run_in_background
from django.http import HttpResponse


class HealthCheckView(APIView):
    def get(self, request):
        return Response({"message": "Service is healthy", "status": "ok", "code": 200}, status=status.HTTP_200_OK)


class IngestIndividualView(APIView):
    def post(self, request, id):
        serializer = IncomingMessageSerializer(data=request.data)
        if serializer.is_valid():
            run_in_background(ingest_individual, id, serializer.validated_data)
            return Response({"message": "Data received"}, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class IngestGroupView(APIView):
    def post(self, request, id):
        serializer = GroupIncomingMessageSerializer(data=request.data)
        if serializer.is_valid():
            run_in_background(ingest_group_sync, id, serializer.validated_data)
            return Response({"message": "Data received"}, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PromptForm(forms.ModelForm):
    class Meta:
        model = Prompt
        fields = ['week', 'activity']


class ControlForm(forms.ModelForm):
    class Meta:
        model = Control
        fields = ['persona', 'system', 'default']


class PromptInterface(View):
    def get(self, request):
        prompts = Prompt.objects.all().order_by('-created_at')
        control_instance = Control.objects.last()
        if not control_instance:
            control_instance = Control.objects.create(
                persona='', system='', default='')
        prompt_form = PromptForm()
        control_form = ControlForm(instance=control_instance)
        context = {
            'prompts': prompts,
            'prompt_form': prompt_form,
            'control_form': control_form,
        }
        return render(request, 'chat/prompt_interface.html', context)

    def post(self, request):
        prompts = Prompt.objects.all().order_by('-created_at')
        control_instance = Control.objects.last()
        if 'prompt_submit' in request.POST:
            prompt_form = PromptForm(request.POST)
            if prompt_form.is_valid():
                prompt_form.save()
                return redirect('chat:prompt_interface')
        elif 'control_submit' in request.POST:
            if control_instance:
                control_form = ControlForm(
                    request.POST, instance=control_instance)
            else:
                control_form = ControlForm(request.POST)
            if control_form.is_valid():
                control_form.save()
                return redirect('chat:prompt_interface')
        prompt_form = PromptForm()
        control_form = ControlForm(instance=control_instance)
        context = {
            'prompts': prompts,
            'prompt_form': prompt_form,
            'control_form': control_form,
        }
        return render(request, 'chat/prompt_interface.html', context)


def prompt_edit(request, prompt_id):
    """
    Provides an interface to edit an existing activity prompt.
    """
    prompt = get_object_or_404(Prompt, id=prompt_id)
    if request.method == 'POST':
        form = PromptForm(request.POST, instance=prompt)
        if form.is_valid():
            form.save()
            return redirect('chat:prompt_interface')
    else:
        form = PromptForm(instance=prompt)
    return render(request, 'chat/prompt_edit.html', {'form': form, 'prompt': prompt})


def prompt_delete(request, prompt_id):
    """
    Provides an interface to confirm and delete a prompt.
    """
    prompt = get_object_or_404(Prompt, id=prompt_id)
    if request.method == 'POST':
        prompt.delete()
        return redirect('chat:prompt_interface')
    return render(request, 'chat/prompt_confirm_delete.html', {'prompt': prompt})
