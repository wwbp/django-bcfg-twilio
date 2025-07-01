from django.urls import path
from .views import (
    HealthCheckView,
    IngestGroupInitialMessageView,
    IngestIndividualView,
    IngestGroupView,
    IngestIndividualInitialMessageView,
)

app_name = "chat"

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("participant/<str:id>/incoming", IngestIndividualView.as_view(), name="ingest-individual"),
    path(
        "participant/<str:id>/initial", IngestIndividualInitialMessageView.as_view(), name="ingest-individual-initial"
    ),
    path("participantgroup/<str:id>/incoming", IngestGroupView.as_view(), name="ingest-group"),
    path("participantgroup/<str:id>/initial", IngestGroupInitialMessageView.as_view(), name="ingest-group-initial"),
]
