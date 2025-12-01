from django.core.cache import cache
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework import serializers

from .serializers import (
    ProductSerializer, ProductCategorySerializer,
    ProductTagSerializer, ProductFormulaSerializer,
    ProductFormulaCalculateSerializer, ComboProductWithComponentsSerializer,
)
from apps.utils.pagination import StandardResultsSetPagination
from apps.utils.odoo import get_odoo_client, get_odoo_client_with_cached_session
from apps.utils.odoo_utils import _get_profit_per_order
from .utils import _get_products_by_combo_id


class ProductListAPIView(GenericAPIView):
    serializer_class = ProductSerializer
    pagination_class = StandardResultsSetPagination

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='search',
                description='Search products by name',
                required=False,
                type=str,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='tag',
                description='Filter products by tag ID',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='category',
                description='Filter products by category ID',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='combo_id',
                description='Filter products by combo ID',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={200: ProductSerializer(many=True)},
        summary="List all products with optional filtering by tag and category",
    )
    def get(self, request):
        try:
            domain = []

            tag_id = request.query_params.get('tag')
            category_id = request.query_params.get('category')
            search_by_name = request.query_params.get('search')
            combo_id = request.query_params.get('combo_id')
            limit = self.pagination_class.page_size
            offset = (int(request.query_params.get('page', 1)) - 1) * limit
            odoo = get_odoo_client()
            if category_id:
                domain.append(('categ_id', '=', int(category_id)))

            if tag_id:
                domain.append(('product_tag_ids', 'in', [int(tag_id)]))

            if search_by_name:
                domain.append(('name', 'ilike', search_by_name))

            if combo_id:
                products = _get_products_by_combo_id(int(combo_id), odoo, product_domain=domain)
            else:
                products = odoo.call('product.template', 'search_read', kwargs={
                    'domain': domain,
                    'fields': [
                        'id', 'name', 'default_code', 'list_price',
                        'uom_id', 'formula_id', 'image_1920', 'taxes_id',
                        'uom_name', 'standard_price', 'categ_id', 'product_tag_ids',
                        'qty_available',
                    ],
                    # 'offset': offset,
                    # 'limit': limit,
                })
                
            paginator = self.pagination_class()
            paginated_data = paginator.paginate_queryset(products, request)
            return paginator.get_paginated_response(paginated_data)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductRetrieveAPIView(GenericAPIView):
    serializer_class = ProductSerializer

    @extend_schema(
        responses={200: ProductSerializer},
        summary="Retrieve a product by ID",
        parameters=[
            # OpenApiParameter(name='id', description='Product ID', required=True, type=int)
        ],
    )
    def get(self, request, id):
        try:
            odoo = get_odoo_client()
            product = odoo.call('product.template', 'search_read', args=[[('id', '=', id)]], kwargs={'fields': [
                'id', 'name', 'default_code', 'list_price',
                'uom_id', 'formula_id', 'image_1920', 'taxes_id',
                'uom_name', 'standard_price', 'categ_id', 'product_tag_ids', 'qty_available'
            ]})
            if request.user.salesperson_id:
                profit_percentage = _get_profit_per_order(request.user.salesperson_id)
                for p in product:
                    p['list_price'] = round(p['list_price'] * (1 + profit_percentage), 2)

            if not product:
                raise NotFound("Product not found.")
            return Response(product[0], status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductCategoryListAPIView(GenericAPIView):
    serializer_class = ProductCategorySerializer

    @extend_schema(
        responses={200: ProductCategorySerializer(many=True)},
        summary="List all product categories",
    )
    def get(self, request):
        try:
            odoo = get_odoo_client()
            categories = odoo.call('product.category', 'search_read', kwargs={'fields': [
                'id', 'name', 'product_count', 'image_1920'
            ]})
            return Response(categories, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductTagListAPIView(GenericAPIView):
    serializer_class = ProductTagSerializer

    @extend_schema(
        responses={200: ProductTagSerializer(many=True)},
        summary="List all product tags",
    )
    def get(self, request):
        try:
            odoo = get_odoo_client()
            tags = odoo.call('product.tag', 'search_read', kwargs={'fields': [
                'id', 'name'
            ]})
            return Response(tags, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductFormulaRetrieveAPIView(GenericAPIView):
    serializer_class = ProductFormulaSerializer

    @extend_schema(
        responses={200: ProductFormulaSerializer},
        summary="Retrieve a product formula by ID",
        parameters=[
            # OpenApiParameter(name='id', description='Formula ID', required=True, type=int)
        ],
    )
    def get(self, request, id):
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            formula = odoo.call('product.formula', 'search_read', args=[[('id', '=', id)]], kwargs={'fields': [
                'id', 'name', 'formula', 'active'
            ]})
            if not formula:
                raise NotFound("Formula not found.")
            return Response(formula[0], status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductFormulaCalculateAPIView(GenericAPIView):
    serializer_class = ProductFormulaCalculateSerializer

    @extend_schema(
        request=ProductFormulaCalculateSerializer,
        responses={200: serializers.FloatField()},
        summary="Calculate product price using a formula",
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        
        user = request.user
        odoo = get_odoo_client_with_cached_session(username=user.username)
        try:
            formula_id = validated_data['formula_id']
            product_id = validated_data['product_id']
            width = validated_data['width']
            height = validated_data['height']
            count = validated_data.get('count', 1)
            take_remains = validated_data.get('take_remains', False)
            formula_wizard = odoo.call('product.formula.wizard', 'create', args=[{
                'formula_id': formula_id,
                'product_id': product_id,
                'width': width,
                'height': height,
                'count': count,
                'take_remains': True,
                # 'order_line_id': validated_data.get('order_line_id', False),
            }])
            result = odoo.call('product.formula.wizard', 'apply_formula', args=[int(formula_wizard.split('(')[1].split(',')[0])])
            formula_wizard_remains = odoo.call('product.formula.wizard', 'create', args=[{
                'formula_id': formula_id,
                'product_id': product_id,
                'width': width,
                'height': height,
                'count': count,
                'take_remains': False,
                # 'order_line_id': validated_data.get('order_line_id', False),
            }])
            result_remain = odoo.call('product.formula.wizard', 'apply_formula', args=[int(formula_wizard_remains.split('(')[1].split(',')[0])])
            return Response({'result': f'{result},{result_remain}'}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductFullAPIView(GenericAPIView):
    """
    Returns:
      - products (templates)
      - variants (product.product)
      - attributes
      - attribute_values
      - attribute_lines (template attribute lines)
      - combos (merged inside products)
    """
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='search',
                description='Search products by name',
                required=False,
                type=str,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='tag',
                description='Filter products by tag ID',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='category',
                description='Filter products by category ID',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='combo_id',
                description='Filter products by combo ID',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={200: ProductSerializer(many=True)},
        summary="List all products with optional filtering by tag and category",
    )
    def get(self, request):
        domain = []

        tag_id = request.query_params.get('tag')
        category_id = request.query_params.get('category')
        search_by_name = request.query_params.get('search')
        combo_id = request.query_params.get('combo_id')
        limit = self.pagination_class.page_size
        offset = (int(request.query_params.get('page', 1)) - 1) * limit
        if category_id:
            domain.append(('categ_id', '=', int(category_id)))

        if tag_id:
            domain.append(('product_tag_ids', 'in', [int(tag_id)]))

        if search_by_name:
            domain.append(('name', 'ilike', search_by_name))
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)

            # 1) Products (Template level)
            products = odoo.call('product.template', 'search_read', kwargs={
                'domain': domain,
                'fields': [
                    'id', 'name', 'default_code', 'list_price',
                    'uom_id', 'image_1920', 'taxes_id', 'standard_price',
                    'categ_id', 'product_tag_ids', 'qty_available',
                    'product_variant_ids',
                    'attribute_line_ids',
                    'combo_ids',
                ]
            })

            return Response({
                "products": products,
            })

        except Exception as e:
            return Response({"error": str(e)}, status=500)

