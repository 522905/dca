from rest_framework import serializers

from connection_app.models import SalesOrder


class SalesOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesOrder
        fields = '__all__'
