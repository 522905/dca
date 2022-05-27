from django.http import JsonResponse
from django.urls import reverse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import models
from .enums import ConnectionApplicationLeadStatus
from .models import ConnectionApplication, ConnectionApplicationDocuments
from .serializers import ConnectionApplicationSerializer


class ConnectionApplicationViewSet(viewsets.ModelViewSet):
    queryset = models.ConnectionApplication.objects.all()
    # serializer_class = ConnectionApplicationSerializer

    @action(methods=['post'], detail=False, url_path='wf')
    def web_form(self, request, *args, **kwargs):
        request.PERFORM_SUBMIT = True
        return super().create(request, *args, **kwargs)

    @action(methods=['post'], detail=True, url_path='reupload_application')
    def reupload_application(self, request, *args, **kwargs):
        instance: ConnectionApplication = self.get_object()

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        for document in request.data.get('documents'):
            instance.documents.filter(type=document['type']).delete()
            instance.documents.create(**document)

        instance.reuploaded_by_customer()
        instance.save()

        return Response({'id': instance.id})

    @action(methods=['get'], detail=False, url_path='check_phone')
    def check_phone(self, request, *args, **kwargs):
        mobile = request.GET.get('mobile')

        application = ConnectionApplication.objects.exclude(
            status=ConnectionApplicationLeadStatus.NOT_INTERESTED
        ).filter(mobile=mobile)

        if application.exists():
            status_url = reverse('application_status', kwargs={'pk': application.first().pk})
            return JsonResponse({
                "status": False,
                "application_url": request.build_absolute_uri(status_url)
            })

        return JsonResponse({
            "status": True
        })

    def perform_create(self, serializer):
        application = serializer.save()
        if getattr(self.request, "PERFORM_SUBMIT", False):
            application.submit()
            application.save()
        return application

    @action(methods=['post'], detail=True, url_path='upload_installation')
    def upload_installation(self, request, *args, **kwargs):
        instance: ConnectionApplication = self.get_object()

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        for document in request.data.get('documents'):
            instance.documents.filter(type=document['type']).delete()
            instance.documents.create(**document)

        instance.upload_installation()
        instance.save()

        return Response({'id': instance.id})
