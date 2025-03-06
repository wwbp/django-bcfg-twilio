from .views import SummaryListView, SummaryCreateView, SummaryUpdateView
from django.urls import path
from .views import HealthCheckView, IngestIndividualView, IngestGroupView, PromptInterface, prompt_edit, prompt_delete, summary_view

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
    path('summary', summary_view, name='summary'),
    path('summary/interface/', SummaryListView.as_view(), name='summary_list'),
    path('summary/create/', SummaryCreateView.as_view(), name='summary_create'),
    path('summary/<int:pk>/edit/',
         SummaryUpdateView.as_view(), name='summary_update'),
]
