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
    """
    List and create customers with pagination and search functionality.
    """
    
    @extend_schema(
        summary="List Customers",
        description="Retrieve a paginated list of customers with basic information.",
        responses={
            200: CustomerSerializer(many=True),
            500: OpenApiResponse(description="Internal Server Error")
        },
        parameters=[
            OpenApiParameter(
                name='page',
                description='Page number (default: 1)',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page_size',
                description='Number of items per page (default: 20, max: 100)',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search customers by name'
            ),
            OpenApiParameter(
                name='phone',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter customers by phone number'
            ),
            OpenApiParameter(
                name='city',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter customers by city'
            ),
            OpenApiParameter(
                name='zip',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter customers by zip code'
            ),
        ],
        tags=["Customers"]
    )
    def get(self, request):
        # Pagination parameters
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Limit max page size to prevent abuse
        page_size = min(page_size, 100)
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Search parameters
        search_by_name = request.query_params.get('search', '').strip()
        search_by_phone = request.query_params.get('phone', '').strip()
        search_by_city = request.query_params.get('city', '').strip()
        search_by_zip = request.query_params.get('zip', '').strip()

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Build domain - only get customers (not companies or other partner types)
            # Odoo res.partner model has 'customer' and 'supplier' boolean fields
            domain = []
            
            # Build search domain with OR conditions for name and phone
            search_domain = []
            if search_by_name:
                search_domain.append(('name', 'ilike', search_by_name))
            if search_by_phone:
                search_domain.append(('phone', 'ilike', search_by_phone))
            
            # Combine search domain with OR if both name and phone are provided
            if len(search_domain) > 1:
                domain.append('|')
                domain.extend(search_domain)
            elif len(search_domain) == 1:
                domain.extend(search_domain)
            
            # Add additional filters
            if search_by_city:
                domain.append(('city', 'ilike', search_by_city))
            if search_by_zip:
                domain.append(('zip', 'ilike', search_by_zip))

            # Call Odoo with pagination
            result = odoo.call(
                model='res.partner',
                method='search_read',
                kwargs={
                    'domain': domain,
                    'fields': [
                        'id', 'name', 'phone', 'street', 'street2', 
                        'city', 'zip', 'create_date', 'email', 'mobile',
                        'country_id', 'state_id', 'total_amount_remaining',
                    ],
                    'order': 'create_date desc',
                },
                limit=page_size,
                offset=offset,
                relation_fields={'country_id': ['id', 'name'], 'state_id': ['id', 'name']},
            )

            # Extract pagination metadata
            customers = result.get('result', [])
            total_count = result.get('total_count', len(customers))
            has_more = result.get('has_more', False)
            
            # Calculate pagination info
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
            
            return Response({
                "customers": customers,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": has_more,
                    "has_previous": page > 1,
                }
            })

        except Exception as e:
            logger.error(f"Error fetching customers: {str(e)}")
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
        
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Create customer in Odoo
            customer_result = odoo.call(
                model='res.partner',
                method='create',
                args=[{
                    'name': validated_data.get('name'),
                    'phone': validated_data.get('phone'),
                    'street': validated_data.get('street'),
                    'street2': validated_data.get('street2'),
                    'city': validated_data.get('city'),
                    'zip': validated_data.get('zip'),
                    'email': validated_data.get('email', False),
                    'mobile': validated_data.get('mobile', False),
                    'type': 'contact',  # Set as contact type
                }],
            )
            
            customer = customer_result['result'][0] if customer_result.get('result') else {'id': customer_id}
            
            return Response({
                'id': customer['id'],
                'name': customer.get('name', validated_data.get('name')),
                'phone': customer.get('phone', validated_data.get('phone')),
                'message': 'Customer created successfully'
            }, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            logger.error(f"Validation error creating customer: {str(e)}")
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating customer: {str(e)}")
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CustomerRetrieveAPIView(GenericAPIView):
    """
    Retrieve, update, and delete customer details.
    """
    
    @extend_schema(
        summary="Retrieve Customer",
        description="Retrieve detailed information of a customer by their ID.",
        responses={
            200: CustomerSerializer,
            404: OpenApiResponse(description="Customer not found"),
            500: OpenApiResponse(description="Internal Server Error")
        },
        tags=["Customers"],
    )
    def get(self, request, id):
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Get customer details
            result = odoo.call(
                model='res.partner',
                method='search_read',
                kwargs={
                    'domain': [
                        ('id', '=', int(id)), # Ensure it's a customer
                    ],
                    'fields': [
                        'id', 'name', 'phone', 'street', 'street2', 
                        'city', 'zip', 'email', 'mobile',
                        'country_id', 'state_id', 'create_date',
                        'write_date', 'vat', 'company_type',
                        'total_amount_remaining',
                    ],
                    'limit': 1
                },
                relation_fields={'country_id': ['id', 'name'], 'state_id': ['id', 'name']},
            )
            
            customers = result.get('result', [])
            
            if not customers:
                raise NotFound(detail='Customer not found!')
            
            return Response(customers[0], status=status.HTTP_200_OK)

        except NotFound as e:
            logger.warning(f"Customer not found: {id}")
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error retrieving customer {id}: {str(e)}")
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Update Customer",
        description="Update customer information.",
        request=CustomerSerializer,
        responses={
            200: OpenApiResponse(description="Customer updated successfully"),
            404: OpenApiResponse(description="Customer not found"),
            400: OpenApiResponse(description="Validation error"),
            500: OpenApiResponse(description="Internal Server Error")
        },
        tags=["Customers"],
    )
    def put(self, request, id):
        serializer = CustomerSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # First check if customer exists
            check_result = odoo.call(
                model='res.partner',
                method='search_read',
                kwargs={
                    'domain': [
                        ('id', '=', int(id)),
                    ],
                    'fields': ['id'],
                    'limit': 1
                }
            )
            
            if not check_result.get('result'):
                raise NotFound(detail='Customer not found!')

            # Prepare update data
            update_data = {}
            if 'name' in validated_data:
                update_data['name'] = validated_data['name']
            if 'phone' in validated_data:
                update_data['phone'] = validated_data['phone']
            if 'street' in validated_data:
                update_data['street'] = validated_data['street']
            if 'street2' in validated_data:
                update_data['street2'] = validated_data['street2']
            if 'city' in validated_data:
                update_data['city'] = validated_data['city']
            if 'zip' in validated_data:
                update_data['zip'] = validated_data['zip']
            if 'email' in validated_data:
                update_data['email'] = validated_data['email']
            if 'mobile' in validated_data:
                update_data['mobile'] = validated_data['mobile']
            
            # Update customer
            success = odoo.call(
                model='res.partner',
                method='write',
                args=[[int(id)], update_data]
            )
            
            if not success:
                return Response(
                    {"error": "Failed to update customer"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({
                'id': id,
                'message': 'Customer updated successfully'
            }, status=status.HTTP_200_OK)

        except NotFound as e:
            logger.warning(f"Customer not found for update: {id}")
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except ValidationError as e:
            logger.error(f"Validation error updating customer {id}: {str(e)}")
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating customer {id}: {str(e)}")
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Delete Customer",
        description="Delete a customer by ID.",
        responses={
            200: OpenApiResponse(description="Customer deleted successfully"),
            404: OpenApiResponse(description="Customer not found"),
            400: OpenApiResponse(description="Cannot delete customer with related records"),
            500: OpenApiResponse(description="Internal Server Error")
        },
        tags=["Customers"],
    )
    def delete(self, request, id):
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # First check if customer exists
            check_result = odoo.call(
                model='res.partner',
                method='search_read',
                kwargs={
                    'domain': [
                        ('id', '=', int(id)),
                    ],
                    'fields': ['id', 'name'],
                    'limit': 1
                }
            )
            
            if not check_result.get('result'):
                raise NotFound(detail='Customer not found!')
            
            customer = check_result['result'][0]
            
            # Optional: Check if customer has related records (orders, invoices, etc.)
            # This prevents accidental deletion of customers with history
            order_count_result = odoo.call(
                model='sale.order',
                method='search_count',
                kwargs={
                    'domain': [
                        ('partner_id', '=', int(id)),
                    ]
                }
            )
            
            order_count = order_count_result.get('result', 0)
            if order_count > 0:
                return Response({
                    'error': f'Cannot delete customer "{customer["name"]}" because they have {order_count} related order(s)',
                    'customer_name': customer['name'],
                    'order_count': order_count
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Delete customer
            success = odoo.call(
                model='res.partner',
                method='unlink',
                args=[[int(id)]]
            )
            
            if not success:
                return Response(
                    {"error": "Failed to delete customer"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({
                'message': f'Customer "{customer["name"]}" deleted successfully',
                'deleted_customer_id': id,
                'deleted_customer_name': customer['name']
            }, status=status.HTTP_200_OK)

        except NotFound as e:
            logger.warning(f"Customer not found for deletion: {id}")
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error deleting customer {id}: {str(e)}")
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            