from rest_framework import serializers


class DeliveryPersonSerializer(serializers.Serializer):
    pass


class TokenResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    user = serializers.DictField(
        help_text="User information",
        child=serializers.CharField()
    )
    warning = serializers.CharField(
        required=False,
        help_text="Optional warning message if Odoo session expired"
    )


class TokenRefreshSerializer(serializers.Serializer):
    """Serializer for token refresh request"""
    refresh = serializers.CharField(
        required=True,
        help_text="Refresh token obtained during login"
    )


class DeliveryPersonLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
