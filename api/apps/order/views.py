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
        description="Returns a paginated list of sale orders assigned to the authenticated delivery person.",
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
    serializer_class = SaleOrderSerializer
    pagination_class = StandardResultsSetPagination

    @extend_schema(
        parameters=[
            OpenApiParameter(name='page', type=int, location=OpenApiParameter.QUERY, description="Page number for pagination"),
            OpenApiParameter(name='start_date', type=str, location=OpenApiParameter.QUERY, description="Filter orders from this date (YYYY-MM-DD)"),
            OpenApiParameter(name='end_date', type=str, location=OpenApiParameter.QUERY, description="Filter orders until this date (YYYY-MM-DD)"),
            OpenApiParameter(name='customer', type=str, location=OpenApiParameter.QUERY, description="Filter orders by customer name (partial match)")
        ],
        responses={200: SaleOrderSerializer(many=True)},
        summary="List Sale Orders with Filters",
        description="Returns a paginated list of sale orders with optional filters for date range and customer name."
    )
    def get(self, request):
        try:
            limit = self.pagination_class.page_size
            offset = (int(request.query_params.get('page', 1)) - 1) * limit

            start_date = request.query_params.get('start_date')  # format: 'YYYY-MM-DD'
            end_date = request.query_params.get('end_date')      # format: 'YYYY-MM-DD'
            customer_name = request.query_params.get('customer')  # partial or full name

            # Build domain filters
            domain = [('user_id', '=', request.user.odoo_user_id)]

            if start_date:
                # convert to full datetime if needed
                domain.append(('date_order', '>=', start_date))
            if end_date:
                domain.append(('date_order', '<=', end_date))
            if customer_name:
                domain.append(('partner_id.name', 'ilike', customer_name))

            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            all_orders = odoo.call(
                'sale.order', 'search_read',
                args=[domain],
                kwargs={
                    'fields': [
                        'name', 'amount_total', 'state', 'partner_id',
                        'order_line', 'note', 'amount_to_invoice',
                        'access_url', 'access_token', 'date_order',
                        'payment_proof_ids',
                    ],
                    # 'offset': offset,
                    # 'limit': limit,
                }
            )

            page = self.paginate_queryset(all_orders)
            return self.get_paginated_response(page)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        partner_id = serializer.validated_data['partner_id']
        order_lines_data = serializer.validated_data['order_lines']

        order_lines = []
        total_amount = 0.0
        
        odoo = get_odoo_client()
        for line in order_lines_data:
            product = odoo.call('product.product', 'search_read',
                                args=[[('id', '=', line['product_id'])]],
                                kwargs={'fields': ['id', 'list_price']})
            if not product:
                return Response({'error': f'Product not found with ID {line["product_id"]}!'},
                                status=status.HTTP_404_NOT_FOUND)
            total_amount += product[0]['list_price'] * line['quantity']
            order_lines.append((0, 0, {
                'product_id': line['product_id'],
                'product_uom_qty': line['quantity'],
                'height': line.get('height', 0.0),
                'width': line.get('width', 0.0),
                'count': line.get('count', 1),
                'take_remains': line.get('take_remains', False),
            }))

        try:
            delivery_person = odoo.call('hr.employee', 'search_read',
                args=[[('id', '=', request.user.salesperson_id)]],
                kwargs={'fields': ['id', 'delivery_person_sale_debt', 'delivery_person_sale_debt_limit']}
            )
            
            if delivery_person:
                delivery_person = delivery_person[0]
                if delivery_person['delivery_person_sale_debt'] + total_amount > delivery_person['delivery_person_sale_debt_limit']:
                    return Response(
                        {'error': 'Total order amount exceeds the allowed debt limit for this delivery person.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            sale_order_id = odoo.call('sale.order', 'create', [{
                'partner_id': partner_id,
                'order_line': order_lines,
                'delivery_person_id': request.user.salesperson_id,
                'note': serializer.validated_data.get('note', ''),
            }])
            return Response({'sale_order_id': int(sale_order_id.split('(')[1].split(',')[0])}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve a Sale Order",
        description="Fetch details of a sale order for the given ID.",
        responses={200: SaleOrderSerializer},
        # parameters=[OpenApiParameter(name="pk", description="Sale Order ID", required=True, type=int)],
    ),
    put=extend_schema(
        summary="Update a Sale Order",
        description="Update order lines for an existing sale order.",
        request=SaleOrderSerializer,
        responses={200: OpenApiResponse(description="Sale order updated")},
    )
)
class OrderDetailAPIView(GenericAPIView):
    serializer_class = SaleOrderSerializer

    def get(self, request, pk):
        try:
            odoo = get_odoo_client()
            order = odoo.call('sale.order', 'search_read',
                              args=[[('id', '=', pk), ('delivery_person_id', '=', request.user.salesperson_id)]],
                              kwargs={'fields': [
                                  'name', 'amount_total', 'state', 'partner_id',
                                  'order_line', 'note', 'amount_to_invoice', 'access_url', 'access_token'
                              ]})
            if not order:
                raise NotFound("Order not found")

            # First, fetch the order lines with product_id (which returns [ID, Name])
            order_lines = odoo.call('sale.order.line', 'search_read',
                                    args=[[('order_id', '=', order[0]['id'])]],
                                    kwargs={'fields': ['product_id', 'product_uom_qty', 'height', 'width', 'count']})

            for line in order_lines:
                if line.get('product_id'): # Ensure product_id exists
                    product_id = line['product_id'][0] # Get the ID from the [ID, Name] tuple
                    
                    # Fetch the image directly from the product.product model
                    product_data = odoo.call('product.product', 'search_read',
                                            args=[[('id', '=', product_id)]],
                                            kwargs={'fields': ['image_1920']}) # Request the image directly

                    if product_data:
                        line['product_image'] = product_data[0].get('image_1920')
                    else:
                        line['product_image'] = False 

            order[0]['order_line'] = order_lines

            return Response(order[0], status=status.HTTP_200_OK)

        except NotFound as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_lines_data = serializer.validated_data['order_lines']

        odoo = get_odoo_client()
        
        order_lines = []
        for line in order_lines_data:
            product = odoo.call('product.product', 'search_read',
                                args=[[('id', '=', line['product_id'])]],
                                kwargs={'fields': ['id']})
            if not product:
                return Response({'error': f'Product not found with ID {line["product_id"]}!'},
                                status=status.HTTP_404_NOT_FOUND)

            order_lines.append((0, 0, {
                'product_id': line['product_id'],
                'product_uom_qty': line['quantity'],
                'height': line.get('height', 0.0),
                'width': line.get('width', 0.0),
                'count': line.get('count', 0),
            }))

        try:
            sale_order_id = odoo.call('sale.order', 'write', [pk], {
                'order_line': order_lines,
            })
            return Response({'sale_order_id': sale_order_id}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Delete a Sale Order",
        description="Delete a sale order by its ID if it belongs to the authenticated delivery person.",
        responses={204: OpenApiResponse(description="Sale order deleted successfully"),
                   404: OpenApiResponse(description="Sale order not found or permission denied"),
                   500: OpenApiResponse(description="Internal server error")},
    )
    def delete(self, request, pk):
        try:
            odoo = get_odoo_client()
            order = odoo.call('sale.order', 'search_read',
                              args=[[('id', '=', pk), ('delivery_person_id', '=', request.user.salesperson_id)]],
                              kwargs={'fields': ['id']})
            if not order:
                raise Response({'error': 'Order not found or you do not have permission to delete it.'},
                               status=status.HTTP_404_NOT_FOUND)

            odoo.call('sale.order', 'unlink', [pk])
            return Response(status=status.HTTP_204_NO_CONTENT)

        except NotFound as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    