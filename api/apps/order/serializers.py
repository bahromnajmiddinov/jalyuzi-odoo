from rest_framework import serializers


class OrderLineSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.FloatField()
    width = serializers.FloatField(required=False, allow_null=True)
    height = serializers.FloatField(required=False, allow_null=True)
    count = serializers.FloatField(required=False, allow_null=True)
    take_remains = serializers.BooleanField(
        default=False,
        help_text="If checked, the order line will take into account the remaining stock of the product."
    )


class SaleOrderSerializer(serializers.Serializer):
    partner_id = serializers.IntegerField()
    order_lines = OrderLineSerializer(many=True)
    name = serializers.CharField(max_length=100, read_only=True)
    amount_total = serializers.FloatField(read_only=True)
    state = serializers.CharField(read_only=True)
    amount_to_invoice = serializers.FloatField(read_only=True)
    access_url = serializers.CharField(read_only=True)
    access_token = serializers.CharField(read_only=True)
    note = serializers.CharField(required=False, allow_blank=True)
