from django.urls import path
from .views import HealthCheckView, IngestIndividualView, IngestGroupView

app_name = "chat"

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health-check'),
    path('participant/<str:id>/incoming',
         IngestIndividualView.as_view(), name='ingest-individual'),
    path('participantgroup/<str:id>/incoming',
         IngestGroupView.as_view(), name='ingest-group'),
]
