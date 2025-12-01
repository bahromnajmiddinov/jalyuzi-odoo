from rest_framework import serializers


class DeliveryPersonSerializer(serializers.Serializer):
    pass


class TokenResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()


class DeliveryPersonLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
