from rest_framework import viewsets
from . import models
from .models import ConnectionApplication
from .serializers import ConnectionApplicationSerializer


class ConnectionApplicationViewSet(viewsets.ModelViewSet):
    queryset = models.ConnectionApplication.objects.all()
    serializer_class = ConnectionApplicationSerializer
