from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import IncomingMessageSerializer, GroupIncomingMessageSerializer
from .ingest import ingest_individual, ingest_group_sync
from .background import run_in_background


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
