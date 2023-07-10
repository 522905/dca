from rest_framework import serializers

from drf_writable_nested.serializers import WritableNestedModelSerializer

from retail_customers.models import RetailCustomerDocuments, RetailCustomerAddress, RetailCustomer


class RetailCustomerDocumentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetailCustomerDocuments
        fields = '__all__'


class RetailCustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetailCustomerAddress
        fields = '__all__'


class RetailCustomerSerializer(WritableNestedModelSerializer):
    documents = RetailCustomerDocumentsSerializer(many=True)
    addresses = RetailCustomerAddressSerializer(many=True)

    class Meta:
        model = RetailCustomer
        fields = '__all__'
