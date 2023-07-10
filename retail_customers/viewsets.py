from rest_framework import viewsets
from rest_framework.decorators import action

from retail_customers.models import RetailCustomer
from retail_customers.serializers import RetailCustomerSerializer


class RetailCustomersViewSet(viewsets.ModelViewSet):
    queryset = RetailCustomer.objects.all()
    serializer_class = RetailCustomerSerializer

    @action(methods=['post'], detail=False, url_path='wf')
    def web_form(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        retail_customer = serializer.save()
        retail_customer.save()
        return retail_customer
