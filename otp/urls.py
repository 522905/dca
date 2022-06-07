from django.urls import path
from rest_framework.routers import DefaultRouter

from otp.views import OtpViewSet, GetNumbersViewSet

router = DefaultRouter()
router.register(r'delivery/otp', OtpViewSet, basename='delivery_otp')


urlpatterns = [
    path(r'numbers/', GetNumbersViewSet.as_view(), name='numbers'),
] + router.urls
