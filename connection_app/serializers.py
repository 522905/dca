from rest_framework import serializers

from connection_app.models import ConnectionApplication, ConnectionApplicationDocuments
from drf_writable_nested.serializers import WritableNestedModelSerializer


class ConnectionApplicationDocumentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectionApplicationDocuments
        fields = '__all__'


class ConnectionApplicationSerializer(WritableNestedModelSerializer):
    documents = ConnectionApplicationDocumentsSerializer(many=True)

    class Meta:
        model = ConnectionApplication
        fields = '__all__'
