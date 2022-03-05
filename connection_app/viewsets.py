from django.http import JsonResponse
from django.urls import reverse
from rest_framework import viewsets
from rest_framework.decorators import action

from . import models
from .enums import ConnectionApplicationLeadStatus
from .models import ConnectionApplication
from .serializers import ConnectionApplicationSerializer


class ConnectionApplicationViewSet(viewsets.ModelViewSet):
    queryset = models.ConnectionApplication.objects.all()
    serializer_class = ConnectionApplicationSerializer

    @action(methods=['post'], detail=False, url_path='wf')
    def web_form(self, request, *args, **kwargs):
        request.PERFORM_SUBMIT = True
        return super().create(request, *args, **kwargs)

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