from django.http import JsonResponse
from django.urls import reverse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import models
from .models import UjjwalaV2Application
from .serializers import UjjwalaV2ApplicationSerializer


class UjjwalaApplicationViewSet(viewsets.ModelViewSet):
    queryset = models.UjjwalaV2Application.objects.all()
    serializer_class = UjjwalaV2ApplicationSerializer

    @action(methods=['post'], detail=False, url_path='wf')
    def web_form(self, request, *args, **kwargs):
        request.PERFORM_SUBMIT = True
        return super().create(request, *args, **kwargs)

    @action(methods=['get'], detail=False, url_path='check_phone')
    def check_phone(self, request, *args, **kwargs):
        contact_mobile = request.GET.get('contact_mobile')

        application = UjjwalaV2Application.objects.objects().filter(mobile=contact_mobile)

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
            try:
                application.event_submit_channel_whatsapp()
            except:
                pass

        return application
