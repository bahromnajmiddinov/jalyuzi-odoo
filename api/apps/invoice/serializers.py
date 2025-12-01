from rest_framework import serializers
from rest_framework.exceptions import ValidationError

import base64


class PaymentJournalSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class PaymentMethodSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class PaymentRegisterSerializer(serializers.Serializer):
    amount = serializers.FloatField()
    journal_id = serializers.IntegerField()
    payment_date = serializers.DateField()


class InvoiceSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True, required=False)
    amount_total = serializers.FloatField(read_only=True)
    amount_residual = serializers.FloatField(read_only=True)
    invoice_date = serializers.DateField(read_only=True, required=False)
    

class PaymentProofSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    payment_date = serializers.DateTimeField(required=True)
    payment_method_id = serializers.IntegerField(required=True)
    journal_id = serializers.IntegerField(required=True)
    proof_image = serializers.CharField(required=True)  # Base64 encoded image
    state = serializers.CharField(read_only=True)
    
    def validate_proof_image(self, value):
        """Validate base64 image"""
        try:
            # Check if valid base64
            base64.b64decode(value, validate=True)
            return value
        except:
            raise ValidationError('Invalid base64 image format')
        