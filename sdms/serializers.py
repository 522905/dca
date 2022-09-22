from rest_framework import serializers

from .models import SdmsFamilyMemberRecord


class SdmsFamilyMemberRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SdmsFamilyMemberRecord
        fields = '__all__'
