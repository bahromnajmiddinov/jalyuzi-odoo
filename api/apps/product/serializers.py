from rest_framework import serializers
from apps.utils.odoo_utils import _get_profit_per_order


class IdNameField(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()

    def to_representation(self, instance):
        if isinstance(instance, (list, tuple)) and len(instance) == 2:
            return list(instance)
        return [instance.id, instance.name]


class ProductCategorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    product_count = serializers.IntegerField()
    image_1920 = serializers.ImageField(required=False, allow_null=True)
    

class ProductTagSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class ProductFormulaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    formula = serializers.CharField()
    active = serializers.BooleanField()


class ProductFormulaCalculateSerializer(serializers.Serializer):
    formula_id = serializers.IntegerField()
    product_id = serializers.IntegerField()
    width = serializers.FloatField()
    height = serializers.FloatField()
    count = serializers.IntegerField(default=1)
    take_remains = serializers.BooleanField(
        default=False,
        help_text="If checked, the order line will take into account the remaining stock of the product."
    )


class ProductSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    default_code = serializers.CharField()
    list_price = serializers.FloatField()
    standard_price = serializers.FloatField()
    uom_id = IdNameField()
    uom_name = serializers.CharField()
    taxes_id = serializers.ListField(child=serializers.IntegerField())
    formula_id = IdNameField()
    image_1920 = serializers.ImageField()
    categ_id = IdNameField()
    product_tag_ids = serializers.ListField(child=serializers.IntegerField())
    qty_available = serializers.FloatField()
    
    def to_representation(self, instance):
        data = super().to_representation(instance)

        # In case related fields are returned as objects instead of tuples
        def flatten_related(obj):
            if hasattr(obj, 'id') and hasattr(obj, 'name'):
                return [obj.id, obj.name]
            return obj

        data["uom_id"] = flatten_related(data["uom_id"])
        data["formula_id"] = flatten_related(data["formula_id"])
        data["categ_id"] = flatten_related(data["categ_id"])

        return data


class ComboComponentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    quantity = serializers.FloatField()


class ComboProductWithComponentsSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    list_price = serializers.FloatField()
    image_1920 = serializers.CharField(required=False)
    components = ComboComponentSerializer(many=True)

