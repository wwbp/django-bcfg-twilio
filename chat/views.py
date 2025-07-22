from dataclasses import asdict
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .services.group_pipeline import handle_inbound_group_initial_message, handle_inbound_group_message
from .services.individual_pipeline import handle_inbound_individual_initial_message, individual_pipeline
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import (
    GroupIncomingMessageSerializer,
    IndividualIncomingMessageSerializer,
    IndividualIncomingInitialMessageSerializer,
    GroupIncomingInitialMessageSerializer,
)


class HealthCheckView(APIView):
    def get(self, request):
        return Response({"message": "Service is healthy", "status": "ok", "code": 200}, status=status.HTTP_200_OK)


class BaseIngestView(APIView):
    def dispatch(self, request, *args, **kwargs):
        # Check API key
        auth_header = request.headers.get("Authorization")
        if not auth_header or auth_header != f"Bearer {settings.INBOUND_MESSAGE_API_KEY}":
            raise PermissionDenied("Invalid API key")
        return super().dispatch(request, *args, **kwargs)


class IngestIndividualView(BaseIngestView):
    def post(self, request, id):
        serializer = IndividualIncomingMessageSerializer(data=request.data)
        if serializer.is_valid():
            individual_pipeline.delay(id, asdict(serializer.validated_data), request_recieved_at=timezone.now())
            return Response({"message": "Data received"}, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class IngestGroupView(BaseIngestView):
    def post(self, request, id):
        serializer = GroupIncomingMessageSerializer(data=request.data)
        if serializer.is_valid():
            handle_inbound_group_message.delay(
                id, asdict(serializer.validated_data), request_recieved_at=timezone.now()
            )
            return Response({"message": "Data received"}, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class IngestIndividualInitialMessageView(BaseIngestView):
    def post(self, request, id):
        serializer = IndividualIncomingInitialMessageSerializer(data=request.data)
        if serializer.is_valid():
            handle_inbound_individual_initial_message.delay(id, asdict(serializer.validated_data))
            return Response({"message": "Data received"}, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class IngestGroupInitialMessageView(BaseIngestView):
    def post(self, request, id):
        serializer = GroupIncomingInitialMessageSerializer(data=request.data)
        if serializer.is_valid():
            handle_inbound_group_initial_message.delay(id, asdict(serializer.validated_data))
            return Response({"message": "Data received"}, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
