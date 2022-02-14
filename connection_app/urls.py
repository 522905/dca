# Routers provide an easy way of automatically determining the URL conf.
# from django.urls import path, include
from rest_framework import routers

from connection_app.viewsets import ConnectionApplicationViewSet
from . import views
from django.urls import path, include

router = routers.DefaultRouter()
router.register(r'connection-application', ConnectionApplicationViewSet)


urlpatterns = [
    path('', views.index),
    path('', include(router.urls))
]