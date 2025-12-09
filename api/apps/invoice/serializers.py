from rest_framework import serializers
from datetime import date
from datetime import datetime
from django.utils import timezone


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
    

class PaymentProofSerializer(serializers.Serializer):
    """Serializer for payment proof display"""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    payment_date = serializers.DateTimeField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    currency_id = serializers.DictField(read_only=True)
    sale_order_id = serializers.DictField(read_only=True)
    payment_method_id = serializers.DictField(read_only=True)
    journal_id = serializers.DictField(read_only=True, allow_null=True)
    proof_image = serializers.CharField(read_only=True, allow_null=True)
    state = serializers.ChoiceField(
        choices=['draft', 'submitted', 'verified', 'rejected', 'processed'],
        read_only=True
    )
    notes = serializers.CharField(allow_blank=True, allow_null=True)
    invoice_id = serializers.DictField(read_only=True, allow_null=True)
    partner_id = serializers.DictField(read_only=True, allow_null=True)
    create_date = serializers.DateTimeField(read_only=True, required=False)
    write_date = serializers.DateTimeField(read_only=True, required=False)


class PaymentProofCreateSerializer(serializers.Serializer):
    """Serializer for creating payment proof"""
    payment_date = serializers.DateTimeField(
        required=True,
        help_text="Date and time of payment"
    )
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        required=True,
        help_text="Payment amount (must be positive)"
    )
    payment_method_id = serializers.IntegerField(
        required=True,
        help_text="ID of the payment method used"
    )
    journal_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID of the payment journal (bank or cash)"
    )
    invoice_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID of the linked invoice (optional)"
    )
    proof_image = serializers.ImageField(
        required=False,
        allow_null=True,
        help_text="Image file of payment proof (receipt, screenshot, etc.)"
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=5000,
        help_text="Additional notes or comments"
    )

    def validate_amount(self, value):
        """Validate that amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be greater than zero")
        return value

    def validate_payment_date(self, value):
        """Validate that payment date is not in the future"""
        if value > timezone.now():
            raise serializers.ValidationError("Payment date cannot be in the future")
        return value


class PaymentProofUpdateSerializer(serializers.Serializer):
    """Serializer for updating payment proof"""
    payment_date = serializers.DateTimeField(
        required=False,
        help_text="Date and time of payment"
    )
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        required=False,
        help_text="Payment amount (must be positive)"
    )
    payment_method_id = serializers.IntegerField(
        required=False,
        help_text="ID of the payment method used"
    )
    journal_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID of the payment journal (bank or cash)"
    )
    invoice_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID of the linked invoice (optional)"
    )
    proof_image = serializers.ImageField(
        required=False,
        allow_null=True,
        help_text="Image file of payment proof (receipt, screenshot, etc.)"
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=5000,
        help_text="Additional notes or comments"
    )

    def validate_amount(self, value):
        """Validate that amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be greater than zero")
        return value

    def validate_payment_date(self, value):
        """Validate that payment date is not in the future"""
        if value > timezone.now():
            raise serializers.ValidationError("Payment date cannot be in the future")
        return value
