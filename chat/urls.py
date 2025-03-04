from django.urls import path
from .views import HealthCheckView, IngestIndividualView, IngestGroupView, PromptInterface, prompt_edit, prompt_delete

app_name = "chat"

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health-check'),
    path('participant/<str:id>/incoming',
         IngestIndividualView.as_view(), name='ingest-individual'),
    path('participantgroup/<str:id>/incoming',
         IngestGroupView.as_view(), name='ingest-group'),
    path('prompt/', PromptInterface.as_view(), name='prompt_interface'),
    path('prompt/edit/<int:prompt_id>/', prompt_edit, name='prompt_edit'),
    path('prompt/delete/<int:prompt_id>/', prompt_delete, name='prompt_delete'),
]
