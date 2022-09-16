from django.http import HttpRequest, HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action

from ujjwala.models import UjjwalaV2Application
from ujjwala.serializers import UjjwalaV2ApplicationSerializer


class UjjwalaApplicationRoboExecutionErrorAPIViewSet(viewsets.ModelViewSet):
    queryset = UjjwalaV2Application.objects.all()
    serializer_class = UjjwalaV2ApplicationSerializer

    @action(methods=['get'], detail=True, url_path='update_robo_execution_failed_count')
    def update_robo_execution_failed_count(self, request: HttpRequest, *args, **kwargs):
        application: UjjwalaV2Application = self.get_object()
        application.robo_execution_failed_count = application.robo_execution_failed_count + 1
        application.save()
        return HttpResponse('OK')
