from rest_framework import routers

from vicidial.viewsets import ViciDialViewSet

router = routers.DefaultRouter()
router.register(r'vicidial', ViciDialViewSet, basename="vicidial_api")

urlpatterns = [] + router.urls
