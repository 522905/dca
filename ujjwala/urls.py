# Routers provide an easy way of automatically determining the URL conf.
from django.conf.urls import url
from django.urls import path, include
from django.contrib import admin
from email.mime import application
from rest_framework import routers

from connection_app.viewsets import ConnectionApplicationViewSet

from . import views
from .viewsets import UjjwalaApplicationViewSet

router = routers.DefaultRouter()
router.register(r'ujjwala-application', UjjwalaApplicationViewSet)

urlpatterns = [
    path('', views.index),
    path('', include(router.urls))
]
