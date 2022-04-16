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
        name="installation_start"
    ),
    url(
        '^connection-application/(?P<pk>[^/.]+)/reupload/$',
        views.ApplicationReuploadView.as_view(),
        name="application_reupload"
    ),
    url(
        '^installation-gleam-start/$',
        views.installation_upload_process_gleam_entry_gate,
        name="application_installation_gleam_start"
    ),
    url(
        '^installation-gleam-complete/$',
        views.installation_upload_process_gleam_entry_gate_completed,
        name="application_installation_gleam_complete"
    ), 
    path('', include(router.urls))
]
