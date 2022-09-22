from django.conf.urls import url
from django.urls import path, include

from django.views.generic import TemplateView
from rest_framework import routers

from .viewsets import FamilyMemberAPIViewSet

router = routers.DefaultRouter()
router.register(r'fm', FamilyMemberAPIViewSet, basename='sdms_fm')

urlpatterns = [
    path('', include(router.urls)),
]
