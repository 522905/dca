# Routers provide an easy way of automatically determining the URL conf.
from django.conf.urls import url
from django.urls import path, include
from django.contrib import admin
from email.mime import application
from rest_framework import routers

from connection_app.viewsets import ConnectionApplicationViewSet

from . import views


router = routers.DefaultRouter()
router.register(r'connection-application', ConnectionApplicationViewSet)


urlpatterns = [
    path('', views.index),
    path('connection-application/start/', views.index),
    url(
        '^connection-application/(?P<pk>[^/.]+)/status/$',
        views.ApplicationStatusView.as_view(),
        name="application_status"
    ),
    url(
        '^connection-application/(?P<pk>[^/.]+)/installation/$',
        views.ApplicationInstallationView.as_view(),
        name="application_status"
    ),
    url(
        '^connection-application/(?P<pk>[^/.]+)/reupload/$',
        views.ApplicationReuploadView.as_view(),
        name="application_status"
    ),
    path('', include(router.urls))
]