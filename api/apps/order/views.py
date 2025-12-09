from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound

from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiResponse, OpenApiParameter
)

from apps.utils.odoo import get_odoo_client, get_odoo_client_with_cached_session
from apps.utils.pagination import StandardResultsSetPagination
from .serializers import SaleOrderSerializer


@extend_schema_view(
    get=extend_schema(
        summary="List Sale Orders",
        description="Returns a paginated list of sale orders for the authenticated user.",
        responses={200: SaleOrderSerializer(many=True)},
    ),
    post=extend_schema(
        summary="Create Sale Order",
        description="Creates a new sale order with the given partner and order lines.",
        request=SaleOrderSerializer,
        responses={201: OpenApiResponse(description="Sale order created successfully"),
                   400: OpenApiResponse(description="Bad request, validation error"),
                   404: OpenApiResponse(description="Product not found"),
                   500: OpenApiResponse(description="Internal server error")},
    )
)
class OrderListAPIView(GenericAPIView):
    """
    Returns paginated sale orders with metadata for the authenticated user.
    """
    
    @extend_schema(
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
                name='start_date',
                description='Filter orders from this date (YYYY-MM-DD)',
                required=False,
                type=str,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='end_date',
                description='Filter orders until this date (YYYY-MM-DD)',
                required=False,
                type=str,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='customer',
                description='Filter orders by customer name (partial match)',
                required=False,
                type=str,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='state',
                description='Filter orders by state',
                required=False,
                type=str,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={200: SaleOrderSerializer(many=True)},
        summary="List Sale Orders with Filters",
        description="Returns a paginated list of sale orders with optional filters for date range, customer name, and state."
    )
    def get(self, request):
        # Pagination parameters
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Limit max page size to prevent abuse
        page_size = min(page_size, 100)
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get filter parameters
        start_date = request.query_params.get('start_date')  # format: 'YYYY-MM-DD'
        end_date = request.query_params.get('end_date')      # format: 'YYYY-MM-DD'
        customer_name = request.query_params.get('customer')  # partial or full name
        state = request.query_params.get('state')  # order state

        # Build domain filters - filter by user_id (odoo user id)
        domain = [('user_id.id', '=', request.user.odoo_user_id)]

        if start_date:
            domain.append(('date_order', '>=', start_date))
        if end_date:
            domain.append(('date_order', '<=', end_date))
        if customer_name:
            domain.append(('partner_id.name', 'ilike', customer_name))
        if state:
            domain.append(('state', '=', state))

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Call Odoo with pagination
            result = odoo.call(
                model='sale.order',
                method='search_read',
                kwargs={
                    'domain': domain,
                    'fields': [
                        'id', 'name', 'amount_total', 'state', 'partner_id',
                        'order_line', 'note', 'amount_to_invoice',
                        'access_url', 'access_token', 'date_order',
                        'payment_proof_ids', 'user_id', 'create_date',
                        'amount_untaxed', 'amount_tax',
                    ],
                },
                relation_fields={
                    # Limit fields in related records for better performance
                    'user_id': ['id', 'name', 'email'],
                    'payment_proof_ids': ['id', 'name', 'payment_date', 'amount', 'state'],
                    'product_tag_ids': ['id', 'name', 'color'],
                    'order_line': ['id', 'product_id', 'product_uom_qty', 'price_unit', 'price_subtotal'],
                    'partner_id': ['id', 'name', 'email', 'phone'],
                },
                limit=page_size,
                offset=offset
            )

            # Extract pagination metadata
            orders = result.get('result', [])
            total_count = result.get('total_count', len(orders))
            has_more = result.get('has_more', False)
            
            # Calculate pagination info
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
            
            return Response({
                "orders": orders,
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
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        partner_id = serializer.validated_data['partner_id']
        order_lines_data = serializer.validated_data['order_lines']

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Validate products and calculate total amount
            order_lines = []
            total_amount = 0.0
            
            for line in order_lines_data:
                # Get product details
                product_result = odoo.call(
                    model='product.product',
                    method='search_read',
                    kwargs={
                        'domain': [('id', '=', line['product_id'])],
                        'fields': ['id', 'list_price'],
                        'limit': 1
                    }
                )
                
                products = product_result.get('result', [])
                
                if not products:
                    return Response(
                        {'error': f'Product not found with ID {line["product_id"]}!'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                product = products[0]
                line_total = product['list_price'] * line['quantity']
                total_amount += line_total
                
                order_lines.append((0, 0, {
                    'product_id': line['product_id'],
                    'product_uom_qty': line['quantity'],
                    'height': line.get('height', 0.0),
                    'width': line.get('width', 0.0),
                    'count': line.get('count', 1),
                    'take_remains': line.get('take_remains', False),
                }))

            # Check user's debt limit (using user_id instead of salesperson_id)
            # This assumes you have a way to get the user's debt limit
            # You might need to adjust this based on your Odoo model structure
            user_info_result = odoo.call(
                model='res.users',
                method='search_read',
                kwargs={
                    'domain': [('id', '=', request.user.odoo_user_id)],
                    'fields': ['id', 'sale_debt', 'sale_debt_limit'],
                    'limit': 1
                }
            )
            
            if user_info_result.get('result'):
                user_info = user_info_result['result'][0]
                current_debt = user_info.get('sale_debt', 0)
                debt_limit = user_info.get('sale_debt_limit', 0)
                
                if current_debt + total_amount > debt_limit:
                    return Response(
                        {'error': 'Total order amount exceeds the allowed debt limit for this user.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Create the sale order
            sale_order_id = odoo.call(
                model='sale.order',
                method='create',
                args=[{
                    'partner_id': partner_id,
                    'order_line': order_lines,
                    'user_id': request.user.odoo_user_id,  # Use user_id instead of delivery_person_id
                    'note': serializer.validated_data.get('note', ''),
                }]
            )
            
            return Response(
                {
                    'sale_order_id': sale_order_id,
                    'message': 'Sale order created successfully'
                }, 
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve a Sale Order",
        description="Fetch details of a sale order for the given ID.",
        responses={200: SaleOrderSerializer},
    ),
    put=extend_schema(
        summary="Update a Sale Order",
        description="Update order lines for an existing sale order.",
        request=SaleOrderSerializer,
        responses={200: OpenApiResponse(description="Sale order updated")},
    ),
    delete=extend_schema(
        summary="Delete a Sale Order",
        description="Delete a sale order by its ID if it belongs to the authenticated user.",
        responses={
            204: OpenApiResponse(description="Sale order deleted successfully"),
            404: OpenApiResponse(description="Sale order not found or permission denied"),
        },
    )
)
class OrderDetailAPIView(GenericAPIView):
    """
    Retrieve, update, or delete a sale order for the authenticated user.
    """
    
    def get(self, request, pk):
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Get order with user_id filter
            result = odoo.call(
                model='sale.order',
                method='search_read',
                kwargs={
                    'domain': [('id', '=', int(pk)), ('user_id.id', '=', request.user.odoo_user_id)],
                    'fields': [
                        'id', 'name', 'amount_total', 'state', 'partner_id',
                        'order_line', 'note', 'amount_to_invoice', 
                        'access_url', 'access_token', 'date_order',
                        'create_date', 'amount_untaxed', 'amount_tax',
                        'payment_proof_ids',
                    ],
                    'limit': 1
                },
                relation_fields={
                    # Limit fields in related records for better performance
                    'user_id': ['id', 'name', 'email'],
                    'payment_proof_ids': ['id', 'name', 'payment_date', 'amount', 'state'],
                    'product_tag_ids': ['id', 'name', 'color'],
                    'order_line': ['id', 'product_id', 'product_uom_qty', 'price_unit', 'price_subtotal'],
                    'partner_id': ['id', 'name', 'email', 'phone'],
                    'product_id': ['id', 'name', 'list_price'],
                },
            )
            
            order = result.get('result', [])
            
            if not order:
                raise NotFound("Order not found or you don't have permission to view it")


            return Response(order, status=status.HTTP_200_OK)

        except NotFound as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_lines_data = serializer.validated_data['order_lines']

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # First check if order exists and belongs to user
            check_result = odoo.call(
                model='sale.order',
                method='search_read',
                kwargs={
                    'domain': [('id', '=', int(pk)), ('user_id.id', '=', request.user.odoo_user_id)],
                    'fields': ['id'],
                    'limit': 1
                }
            )
            
            if not check_result.get('result'):
                return Response(
                    {"error": "Order not found or you don't have permission to update it"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Validate products
            order_lines = []
            for line in order_lines_data:
                product_result = odoo.call(
                    model='product.product',
                    method='search_read',
                    kwargs={
                        'domain': [('id', '=', line['product_id'])],
                        'fields': ['id'],
                        'limit': 1
                    }
                )
                
                if not product_result.get('result'):
                    return Response(
                        {'error': f'Product not found with ID {line["product_id"]}!'},
                        status=status.HTTP_404_NOT_FOUND
                    )

                order_lines.append((0, 0, {
                    'product_id': line['product_id'],
                    'product_uom_qty': line['quantity'],
                    'height': line.get('height', 0.0),
                    'width': line.get('width', 0.0),
                    'count': line.get('count', 0),
                }))

            # Update the sale order
            sale_order_id = odoo.call(
                model='sale.order',
                method='write',
                args=[[int(pk)], {
                    'order_line': order_lines,
                }]
            )
            
            return Response(
                {
                    'sale_order_id': sale_order_id,
                    'message': 'Sale order updated successfully'
                }, 
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def delete(self, request, pk):
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Check if order exists and belongs to user
            check_result = odoo.call(
                model='sale.order',
                method='search_read',
                kwargs={
                    'domain': [('id', '=', int(pk)), ('user_id.id', '=', request.user.odoo_user_id)],
                    'fields': ['id', 'state'],
                    'limit': 1
                }
            )
            
            if not check_result.get('result'):
                return Response(
                    {"error": "Order not found or you don't have permission to delete it"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            order = check_result['result'][0]
            
            # Optional: Check if order can be deleted (e.g., not in certain states)
            if order.get('state') in ['done', 'cancel']:
                return Response(
                    {"error": f"Cannot delete order in {order['state']} state"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Delete the sale order
            odoo.call(
                model='sale.order',
                method='unlink',
                args=[[int(pk)]]
            )
            
            return Response(
                {'message': 'Sale order deleted successfully'},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )