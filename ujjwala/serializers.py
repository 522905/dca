import math

from django.core.signing import Signer
from rest_framework import serializers
from drf_writable_nested.serializers import WritableNestedModelSerializer

from ujjwala.models import UjjwalaApplicationDocuments, UjjwalaV2Application, FamilyMembers
from ujjwala.ujjwala_functions import valid_file_uploaded


class UjjwalaApplicationDocumentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UjjwalaApplicationDocuments
        fields = '__all__'

    def validate(self, attrs):
        is_valid_file_size, file_size = valid_file_uploaded(attrs.get('link'))
        if is_valid_file_size:
            attrs['file_size'] = math.ceil(file_size/1024)
            return attrs
        raise serializers.ValidationError("Ujjwala Application Invalid Documents Size")


class FamilyMembersSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyMembers
        fields = '__all__'

    def validate(self, attrs):
        is_valid_file_size, file_size = valid_file_uploaded(attrs.get('uid_front_link'))
        if is_valid_file_size:
            attrs['uid_front_file_size'] = math.ceil(file_size / 1024)
            is_valid_file_size, file_size = valid_file_uploaded(attrs.get('uid_back_link'))
            if is_valid_file_size:
                attrs['uid_back_file_size'] = math.ceil(file_size / 1024)
                return attrs
        raise serializers.ValidationError("Family Member Documents Invalid Size")


class UjjwalaV2ApplicationSerializer(WritableNestedModelSerializer):
    documents = UjjwalaApplicationDocumentsSerializer(many=True)
    family_members = FamilyMembersSerializer(many=True)

    class Meta:
        model = UjjwalaV2Application
        fields = '__all__'
        extra_kwargs = {
            'contact_mobile': {
                "max_length": 200
            }
        }

    def validate_contact_mobile(self, value):
        try:
            signer = Signer()
            original_value = signer.unsign(value)
            return original_value
        except:
            return original_value
            # raise serializers.ValidationError(detail="Contact Mobile Value Tampered")

class SubmitPreInspectionSerializer(serializers.ModelSerializer):
    documents = UjjwalaApplicationDocumentsSerializer(many=True)

    class Meta:
        model = UjjwalaV2Application
        fields = ('latitude', 'longitude', 'accuracy', 'documents',)
