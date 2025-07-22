from rest_framework import routers

from lpg_dealer_association.viewsets import ViciDialViewSet

router = routers.DefaultRouter()
router.register(r'vicidial', ViciDialViewSet, basename="vicidial_api")

urlpatterns = [] + router.urls