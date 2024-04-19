
from django.urls import path, include
from rest_framework import routers

from connection_app.views import CustomerProfileSearchView
from domestic import views
from domestic.views import DomesticApplicationWebFormView, DomesticApplicationIframeWebFormView


router = routers.DefaultRouter()

urlpatterns = [
    path('', CustomerProfileSearchView.as_view(), name="index"),
    path('', include(router.urls)),
    path('portal/web-form/', DomesticApplicationWebFormView.as_view(), name="web_form"),
    path('portal/i-web-form/', DomesticApplicationIframeWebFormView.as_view(), name="i_web_form"),
]
