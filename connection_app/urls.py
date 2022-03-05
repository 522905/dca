# Routers provide an easy way of automatically determining the URL conf.
from django.urls import path, include
from django.contrib import admin
from email.mime import application
from rest_framework import routers

from connection_app.viewsets import ConnectionApplicationViewSet

from . import views


router = routers.DefaultRouter()
router.register(r'connection-application', ConnectionApplicationViewSet),


urlpatterns = [
    path('', views.index),
    # path('status/', views.Status, name="status"),
     path('^status/$', views.Status, name="status"),
    path('', include(router.urls))
]