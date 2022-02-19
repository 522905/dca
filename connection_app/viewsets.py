from rest_framework import viewsets
from rest_framework.decorators import action

from . import models
from .models import ConnectionApplication
from .serializers import ConnectionApplicationSerializer


class ConnectionApplicationViewSet(viewsets.ModelViewSet):
    queryset = models.ConnectionApplication.objects.all()
    serializer_class = ConnectionApplicationSerializer

    @action(methods=['post'], detail=False, url_path='wf')
    def web_form(self, request, *args, **kwargs):
        request.PERFORM_SUBMIT = True
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        application = serializer.save()
        if getattr(self.request, "PERFORM_SUBMIT", False):
            application.submit()
        return application