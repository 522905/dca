from django.urls import path, include
from rest_framework import routers

from app_utilities.viewsets import ApplicationUtilitiesAPIViewSet

router = routers.DefaultRouter()
router.register(r'application-utilities', ApplicationUtilitiesAPIViewSet, basename='app_utilities')

urlpatterns = [
    path('', include(router.urls)),
]
