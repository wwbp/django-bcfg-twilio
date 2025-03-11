from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView
from django.http import JsonResponse
from django.views import View
from django import forms

from .pipeline import individual_pipeline_ingest_task
from .models import Prompt, Control, StrategyPrompt, Summary
from django.shortcuts import render, redirect, get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import IncomingMessageSerializer, GroupIncomingMessageSerializer
from .tasks import ingest_group_task


class HealthCheckView(APIView):
    def get(self, request):
        return Response({"message": "Service is healthy", "status": "ok", "code": 200}, status=status.HTTP_200_OK)


class IngestIndividualView(APIView):
    def post(self, request, id):
        serializer = IncomingMessageSerializer(data=request.data)
        if serializer.is_valid():
            individual_pipeline_ingest_task.delay(
                id, serializer.validated_data)
            return Response({"message": "Data received"}, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class IngestGroupView(APIView):
    def post(self, request, id):
        serializer = GroupIncomingMessageSerializer(data=request.data)
        if serializer.is_valid():
            ingest_group_task.delay(id, serializer.validated_data)
            return Response({"message": "Data received"}, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PromptForm(forms.ModelForm):
    class Meta:
        model = Prompt
        fields = ['week', 'activity']


class ControlForm(forms.ModelForm):
    class Meta:
        model = Control
        fields = ['persona', 'system', 'default', 'moderation']


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


SUMMARY_ALLOWED_TYPES = ['influencer', 'song', 'spot', 'idea', 'pick']


def summary_view(request):
    school = request.GET.get('school')
    type_param = request.GET.get('type')

    # Validate query parameters
    if not school:
        return JsonResponse({"error": "Missing school parameter."}, status=400)
    if not type_param:
        return JsonResponse({"error": "Missing type parameter."}, status=400)
    if type_param not in SUMMARY_ALLOWED_TYPES:
        return JsonResponse(
            {"error": f"Invalid type parameter. Allowed values: {', '.join(SUMMARY_ALLOWED_TYPES)}."},
            status=400
        )

    # Check if the school exists in any summary record
    if not Summary.objects.filter(school=school).exists():
        return JsonResponse({"error": "School not found."}, status=404)

    # Retrieve the most recently updated summary for the given school and type
    summary = Summary.objects.filter(
        school=school, type=type_param).order_by('-updated_at').first()

    if not summary:
        return JsonResponse({"error": f"No summary found for {school} with type {type_param}."}, status=404)

    data = summary.summary

    return JsonResponse({"summary": data}, status=200)


class SummaryForm(forms.ModelForm):
    class Meta:
        model = Summary
        fields = ['school', 'type', 'summary']


class SummaryListView(ListView):
    model = Summary
    template_name = 'chat/summary_list.html'
    context_object_name = 'summaries'


class SummaryCreateView(CreateView):
    model = Summary
    form_class = SummaryForm
    template_name = 'chat/summary_form.html'
    success_url = reverse_lazy('chat:summary_list')


class SummaryUpdateView(UpdateView):
    model = Summary
    form_class = SummaryForm
    template_name = 'chat/summary_form.html'
    success_url = reverse_lazy('chat:summary_list')


class StrategyPromptForm(forms.ModelForm):
    class Meta:
        model = StrategyPrompt
        fields = ['name', 'what_prompt',
                  'when_prompt', 'who_prompt', 'is_active']


def strategy_list(request):
    """List all active strategy prompts."""
    strategies = StrategyPrompt.objects.filter(is_active=True)
    return render(request, "chat/strategy_list.html", {"strategies": strategies})


def strategy_create(request):
    """Create a new strategy prompt."""
    if request.method == "POST":
        form = StrategyPromptForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("chat:strategy_list")
    else:
        form = StrategyPromptForm()
    return render(request, "chat/strategy_form.html", {"form": form, "action": "Create"})


def strategy_edit(request, pk):
    """Edit an existing strategy prompt."""
    strategy = get_object_or_404(StrategyPrompt, pk=pk)
    if request.method == "POST":
        form = StrategyPromptForm(request.POST, instance=strategy)
        if form.is_valid():
            form.save()
            return redirect("chat:strategy_list")
    else:
        form = StrategyPromptForm(instance=strategy)
    return render(request, "chat/strategy_form.html", {"form": form, "action": "Edit"})


def strategy_delete(request, pk):
    """Soft delete a strategy prompt by marking it inactive."""
    strategy = get_object_or_404(StrategyPrompt, pk=pk)
    # Soft delete: mark as inactive
    strategy.is_active = False
    strategy.save()
    return redirect("chat:strategy_list")
