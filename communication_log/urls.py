# Routers provide an easy way of automatically determining the URL conf.
# from django.urls import path, include
from rest_framework import routers
from . import views
from django.urls import path, include

urlpatterns = [
    path('interakt/webhook/', views.interakt_webhook),
    path('dialogflow/webhook/', views.webhook),
    path('whatappflow/webhook/', views.flowhook),
    path('infobip/webhook/', views.infobip_webhook, name='infobip-webhook')
]
