from rest_framework import serializers
from drf_writable_nested.serializers import WritableNestedModelSerializer

from ujjwala.models import UjjwalaApplicationDocuments, UjjwalaV2Application, FamilyMembers


class UjjwalaApplicationDocumentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UjjwalaApplicationDocuments
        fields = '__all__'


class FamilyMembersSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyMembers
        fields = '__all__'


class UjjwalaV2ApplicationSerializer(WritableNestedModelSerializer):
    documents = UjjwalaApplicationDocumentsSerializer(many=True)
    family_members = FamilyMembersSerializer(many=True)

    class Meta:
        model = UjjwalaV2Application
        fields = '__all__'


class SubmitPreInspectionSerializer(serializers.ModelSerializer):
    documents = UjjwalaApplicationDocumentsSerializer(many=True)

    class Meta:
        model = UjjwalaV2Application
        fields = ('latitude', 'longitude', 'accuracy', 'documents',)
