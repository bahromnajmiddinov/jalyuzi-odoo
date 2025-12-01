from rest_framework import serializers


class CustomerSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    phone = serializers.CharField(allow_blank=True, required=False)
    street = serializers.CharField(allow_blank=True, required=False)
    street2 = serializers.CharField(allow_blank=True, required=False)
    city = serializers.CharField(allow_blank=True, required=False)
    zip = serializers.CharField(allow_blank=True, required=False)
