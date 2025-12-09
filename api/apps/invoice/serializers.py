from rest_framework import serializers
from datetime import date


class InvoiceSerializer(serializers.Serializer):
    """Serializer for invoice data from Odoo"""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    invoice_date = serializers.DateField(read_only=True)
    invoice_date_due = serializers.DateField(read_only=True)
    amount_total = serializers.FloatField(read_only=True)
    amount_residual = serializers.FloatField(read_only=True)
    amount_untaxed = serializers.FloatField(read_only=True)
    amount_tax = serializers.FloatField(read_only=True)
    state = serializers.CharField(read_only=True)
    payment_state = serializers.CharField(read_only=True)
    invoice_origin = serializers.CharField(read_only=True)
    ref = serializers.CharField(read_only=True, allow_null=True)


class PaymentSerializer(serializers.Serializer):
    """Serializer for payment data from Odoo"""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    amount = serializers.FloatField(read_only=True)
    payment_date = serializers.DateField(read_only=True)
    state = serializers.CharField(read_only=True)
    payment_type = serializers.CharField(read_only=True)
    ref = serializers.CharField(read_only=True, allow_null=True)


class PaymentRegisterSerializer(serializers.Serializer):
    """Serializer for registering a new payment"""
    amount = serializers.FloatField(
        required=True,
        min_value=0.01,
        help_text="Payment amount"
    )
    journal_id = serializers.IntegerField(
        required=True,
        help_text="Payment journal ID"
    )
    payment_date = serializers.DateField(
        required=False,
        default=date.today,
        help_text="Payment date (default: today)"
    )
    payment_method_line_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Payment method line ID"
    )
    communication = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        help_text="Payment reference/memo"
    )

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        return value


class PaymentJournalSerializer(serializers.Serializer):
    """Serializer for payment journal data"""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    type = serializers.CharField(read_only=True)
    code = serializers.CharField(read_only=True)


class PaymentMethodLineSerializer(serializers.Serializer):
    """Serializer for payment method line data"""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    code = serializers.CharField(read_only=True)
    payment_type = serializers.CharField(read_only=True)
    