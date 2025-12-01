from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError, NotFound
from django.core.cache import cache
import logging

from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .serializers import CustomerSerializer
from apps.utils.pagination import StandardResultsSetPagination
from apps.utils.odoo import get_odoo_client, get_odoo_client_with_cached_session


logger = logging.getLogger(__name__)


class CustomerListAPIView(GenericAPIView):
    serializer_class = CustomerSerializer
    pagination_class = StandardResultsSetPagination

    @extend_schema(
        summary="List Customers",
        description="Retrieve a paginated list of customers with basic information.",
        responses={
            200: CustomerSerializer(many=True),
            500: OpenApiResponse(description="Internal Server Error")
        },
        parameters=[
            OpenApiParameter(name='search', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, description='Search customers by name'),
            OpenApiParameter(name='phone', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, description='Filter customers by phone number')
        ],
        tags=["Customers"]
    )
    def get(self, request):
        try:
            domain = []
            search_by_name = request.query_params.get('search', '').strip()
            search_by_phone = request.query_params.get('phone', '').strip()
            limit = self.pagination_class.page_size
            offset = (int(request.query_params.get('page', 1)) - 1) * limit
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)

            if search_by_name and search_by_phone:
                domain = ['|', ('name', 'ilike', search_by_name), ('phone', 'ilike', search_by_phone)]
            elif search_by_name:
                domain = [('name', 'ilike', search_by_name)]
            elif search_by_phone:
                domain = [('phone', 'ilike', search_by_phone)]

            customers = odoo.call('res.partner', 'search_read', kwargs={
                'fields': ['id', 'name', 'phone', 'street', 'street2', 'city', 'zip', 'create_date'],
                'order': 'create_date desc', 
                # 'offset': offset, 'limit': limit,
            }, args=[domain])

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        page = self.paginate_queryset(customers)
        if page is not None:
            return self.get_paginated_response(page)

        return Response(customers, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Create Customer",
        description="Create a new customer record.",
        request=CustomerSerializer,
        responses={
            201: OpenApiResponse(description="Customer created successfully", response=CustomerSerializer),
            400: OpenApiResponse(description="Validation error"),
            500: OpenApiResponse(description="Internal Server Error")
        },
        tags=["Customers"]
    )
    def post(self, request):
        serializer = CustomerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        
        user = request.user
        odoo = get_odoo_client_with_cached_session(username=user.username)

        try:
            customer_id = odoo.call('res.partner', 'create', args=[{
                'name': validated_data.get('name'),
                'phone': validated_data.get('phone'),
                'street': validated_data.get('street'),
                'street2': validated_data.get('street2'),
                'city': validated_data.get('city'),
                'zip': validated_data.get('zip'),
            }])
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'id': customer_id}, status=status.HTTP_201_CREATED)


class CustomerRetrieveAPIView(GenericAPIView):
    serializer_class = CustomerSerializer

    @extend_schema(
        summary="Retrieve Customer",
        description="Retrieve detailed information of a customer by their ID.",
        responses={
            200: CustomerSerializer,
            404: OpenApiResponse(description="Customer not found"),
            500: OpenApiResponse(description="Internal Server Error")
        },
        tags=["Customers"],
        # parameters=[
        #     OpenApiParameter(name='id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH, description='Customer ID')
        # ]
    )
    def get(self, request, id):
        
        user = request.user
        odoo = get_odoo_client_with_cached_session(username=user.username)
        
        try:
            customer = odoo.call('res.partner', 'search_read', args=[[('id', '=', id)]], kwargs={
                'fields': ['id', 'name', 'phone', 'street', 'street2', 'city', 'zip']
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not customer:
            raise NotFound(detail='Customer not found!')

        return Response(customer[0], status=status.HTTP_200_OK)
