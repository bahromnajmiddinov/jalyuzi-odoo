from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError, NotFound

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.utils.odoo import get_odoo_client, get_odoo_client_with_cached_session
from apps.utils.pagination import StandardResultsSetPagination
from .serializers import (
    InvoiceSerializer,
    PaymentJournalSerializer,
    PaymentMethodSerializer,
    PaymentRegisterSerializer,
    PaymentProofSerializer
)


class PaymentProofAPIView(GenericAPIView):
    """
    Create and list payment proofs for orders belonging to the authenticated user.
    """
    serializer_class = PaymentProofSerializer

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
        ],
        responses={200: PaymentProofSerializer(many=True)},
        summary="List payment proofs for an order",
        description="Returns paginated list of payment proofs for a specific order belonging to the authenticated user"
    )
    def get(self, request, order_id):
        # Pagination parameters
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Limit max page size to prevent abuse
        page_size = min(page_size, 100)
        
        # Calculate offset
        offset = (page - 1) * page_size

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # First check if order exists and belongs to user
            order_result = odoo.call(
                model='sale.order',
                method='search_read',
                kwargs={
                    'domain': [('id', '=', int(order_id)), ('user_id.id', '=', request.user.odoo_user_id)],
                    'fields': ['id'],
                    'limit': 1
                }
            )
            
            if not order_result.get('result'):
                return Response(
                    {"error": "Order not found or you don't have permission to view it"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get payment proofs with pagination
            result = odoo.call(
                model='payment.proof',
                method='search_read',
                kwargs={
                    'domain': [('sale_order_id', '=', int(order_id))],
                    'fields': [
                        'id', 'name', 'amount', 'payment_date', 
                        'state', 'payment_method_id', 'journal_id', 'proof_image',
                        'create_date', 'sale_order_id',
                    ],
                },
                limit=page_size,
                offset=offset
            )

            # Extract pagination metadata
            proofs = result.get('result', [])
            total_count = result.get('total_count', len(proofs))
            has_more = result.get('has_more', False)
            
            # Calculate pagination info
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
            
            return Response({
                "payment_proofs": proofs,
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

    @extend_schema(
        request=PaymentProofSerializer,
        responses={
            201: OpenApiResponse(description="Payment proof created successfully"),
            400: OpenApiResponse(description="Bad request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Order not found"),
        },
        summary="Create payment proof",
        description="Create a new payment proof for an order belonging to the authenticated user"
    )
    def post(self, request, order_id):
        """Create payment proof in Odoo"""
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Check order access using user_id
            order_result = odoo.call(
                model='sale.order',
                method='search_read',
                kwargs={
                    'domain': [('id', '=', int(order_id)), ('user_id.id', '=', request.user.odoo_user_id)],
                    'fields': ['id', 'name', 'state', 'amount_total', 'amount_residual'],
                    'limit': 1
                }
            )
            
            if not order_result.get('result'):
                return Response(
                    {"error": "Order not found or access denied"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            order = order_result['result'][0]
            
            # Validate and prepare data
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            
            # Check if amount exceeds order residual
            if data['amount'] > order.get('amount_residual', 0):
                return Response(
                    {'error': 'Payment amount exceeds order residual amount'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create payment proof in Odoo
            proof_id = odoo.call(
                model='payment.proof',
                method='create',
                args=[{
                    'sale_order_id': int(order_id),
                    'amount': float(data['amount']),
                    'payment_date': data['payment_date'].strftime('%Y-%m-%d %H:%M:%S'),
                    'payment_method_id': data['payment_method_id'],
                    'journal_id': data['journal_id'],
                    'proof_image': data['proof_image'],
                    'state': 'submitted',
                    'user_id': request.user.odoo_user_id,
                }]
            )
            
            return Response({
                'id': proof_id,
                'message': 'Payment proof submitted for review',
                'order_id': int(order_id)
            }, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentProofDetailAPIView(GenericAPIView):
    """
    Retrieve, update, or delete a payment proof belonging to the authenticated user.
    """
    serializer_class = PaymentProofSerializer
    
    @extend_schema(
        responses={200: PaymentProofSerializer},
        summary="Retrieve a payment proof",
        description="Get details of a specific payment proof if it belongs to an order of the authenticated user"
    )
    def get(self, request, id):
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Get payment proof with user validation through sale order
            proof_result = odoo.call(
                model='payment.proof',
                method='search_read',
                kwargs={
                    'domain': [
                        ('id', '=', int(id)),
                        ('sale_order_id.user_id', '=', request.user.odoo_user_id)
                    ],
                    'fields': [
                        'id', 'name', 'amount', 'payment_date', 
                        'state', 'payment_method_id', 'journal_id', 'proof_image',
                        'sale_order_id', 'create_date', 'write_date',
                    ],
                    'limit': 1
                }
            )
            
            proofs = proof_result.get('result', [])
            
            if not proofs:
                raise NotFound("Payment proof not found or access denied")
            
            return Response(proofs[0], status=status.HTTP_200_OK)

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
    
    @extend_schema(
        request=PaymentProofSerializer,
        responses={
            200: OpenApiResponse(description="Payment proof updated successfully"),
            400: OpenApiResponse(description="Bad request"),
            404: OpenApiResponse(description="Payment proof not found"),
        },
        summary="Update a payment proof",
        description="Update a payment proof if it belongs to an order of the authenticated user"
    )
    def put(self, request, id):
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # First check if payment proof exists and belongs to user
            check_result = odoo.call(
                model='payment.proof',
                method='search_read',
                kwargs={
                    'domain': [
                        ('id', '=', int(id)),
                        ('sale_order_id.user_id', '=', request.user.odoo_user_id)
                    ],
                    'fields': ['id', 'state'],
                    'limit': 1
                }
            )
            
            if not check_result.get('result'):
                return Response(
                    {"error": "Payment proof not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            proof = check_result['result'][0]
            
            # Don't allow updating if proof is already approved/rejected
            if proof.get('state') in ['approved', 'rejected']:
                return Response(
                    {"error": f"Cannot update payment proof in {proof['state']} state"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate and prepare update data
            serializer = self.get_serializer(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            
            # Prepare update values
            update_values = {}
            if 'amount' in data:
                update_values['amount'] = float(data['amount'])
            if 'payment_date' in data:
                update_values['payment_date'] = data['payment_date'].strftime('%Y-%m-%d %H:%M:%S')
            if 'payment_method_id' in data:
                update_values['payment_method_id'] = data['payment_method_id']
            if 'journal_id' in data:
                update_values['journal_id'] = data['journal_id']
            if 'proof_image' in data:
                update_values['proof_image'] = data['proof_image']

            # Update the payment proof
            success = odoo.call(
                model='payment.proof',
                method='write',
                args=[[int(id)], update_values]
            )
            
            if not success:
                return Response(
                    {'error': 'Failed to update payment proof'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response(
                {'message': 'Payment proof updated successfully'},
                status=status.HTTP_200_OK
            )

        except ValidationError as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        responses={
            200: OpenApiResponse(description="Payment proof deleted successfully"),
            404: OpenApiResponse(description="Payment proof not found"),
        },
        summary="Delete a payment proof",
        description="Delete a payment proof if it belongs to an order of the authenticated user"
    )
    def delete(self, request, id):
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # First check if payment proof exists and belongs to user
            check_result = odoo.call(
                model='payment.proof',
                method='search_read',
                kwargs={
                    'domain': [
                        ('id', '=', int(id)),
                        ('sale_order_id.user_id', '=', request.user.odoo_user_id)
                    ],
                    'fields': ['id', 'state'],
                    'limit': 1
                }
            )
            
            if not check_result.get('result'):
                return Response(
                    {"error": "Payment proof not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            proof = check_result['result'][0]
            
            # Don't allow deleting if proof is already approved/rejected
            if proof.get('state') in ['approved', 'rejected']:
                return Response(
                    {"error": f"Cannot delete payment proof in {proof['state']} state"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Delete the payment proof
            success = odoo.call(
                model='payment.proof',
                method='unlink',
                args=[[int(id)]]
            )
            
            if not success:
                return Response(
                    {'error': 'Failed to delete payment proof'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response(
                {'message': 'Payment proof deleted successfully'},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentJournalListAPIView(GenericAPIView):
    """
    Returns paginated payment journals.
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
                name='type',
                description='Filter by journal type (bank, cash, general, etc.)',
                required=False,
                type=str,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={200: PaymentJournalSerializer(many=True)},
        description="List all payment journals from Odoo with pagination"
    )
    def get(self, request):
        # Pagination parameters
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Limit max page size to prevent abuse
        page_size = min(page_size, 100)
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Filter parameters
        journal_type = request.query_params.get('type')

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Build domain
            domain = []
            if journal_type:
                domain.append(('type', '=', journal_type))
            
            # Add filter for active journals
            domain.append(('active', '=', True))

            # Call Odoo with pagination
            result = odoo.call(
                model='account.journal',
                method='search_read',
                kwargs={
                    'domain': domain,
                    'fields': ['id', 'name', 'type', 'code', 'currency_id'],
                },
                limit=page_size,
                offset=offset
            )

            # Extract pagination metadata
            journals = result.get('result', [])
            total_count = result.get('total_count', len(journals))
            has_more = result.get('has_more', False)
            
            # Calculate pagination info
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
            
            return Response({
                "journals": journals,
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


class PaymentMethodListAPIView(GenericAPIView):
    """
    Returns paginated payment methods.
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
                name='code',
                description='Filter by payment method code',
                required=False,
                type=str,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={200: PaymentMethodSerializer(many=True)},
        description="List all payment methods from Odoo with pagination"
    )
    def get(self, request):
        # Pagination parameters
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Limit max page size to prevent abuse
        page_size = min(page_size, 100)
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Filter parameters
        method_code = request.query_params.get('code')

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Build domain
            domain = []
            if method_code:
                domain.append(('code', '=', method_code))

            # Call Odoo with pagination
            result = odoo.call(
                model='account.payment.method',
                method='search_read',
                kwargs={
                    'domain': domain,
                    'fields': ['id', 'name', 'code', 'payment_type'],
                },
                limit=page_size,
                offset=offset
            )

            # Extract pagination metadata
            payment_methods = result.get('result', [])
            total_count = result.get('total_count', len(payment_methods))
            has_more = result.get('has_more', False)
            
            # Calculate pagination info
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
            
            return Response({
                "payment_methods": payment_methods,
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


class InvoiceListAPIView(GenericAPIView):
    """
    Get and create invoices for orders belonging to the authenticated user.
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
                name='state',
                description='Filter by invoice state',
                required=False,
                type=str,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={200: InvoiceSerializer(many=True)},
        description="Get invoices related to a sale order belonging to the authenticated user"
    )
    def get(self, request, order_id):
        # Pagination parameters
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Limit max page size to prevent abuse
        page_size = min(page_size, 100)
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Filter parameters
        invoice_state = request.query_params.get('state')

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # First check if order exists and belongs to user
            order_result = odoo.call(
                model='sale.order',
                method='search_read',
                kwargs={
                    'domain': [('id', '=', int(order_id)), ('user_id.id', '=', request.user.odoo_user_id)],
                    'fields': ['id', 'name'],
                    'limit': 1
                }
            )
            
            if not order_result.get('result'):
                return Response(
                    {"error": "Sale order not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            order = order_result['result'][0]
            order_name = order['name']
            
            # Build domain for invoices
            domain = [('invoice_origin', '=', order_name)]
            if invoice_state:
                domain.append(('state', '=', invoice_state))

            # Get invoices with pagination
            result = odoo.call(
                model='account.move',
                method='search_read',
                kwargs={
                    'domain': domain,
                    'fields': [
                        'id', 'name', 'amount_total', 'amount_residual', 
                        'invoice_date', 'state', 'invoice_date_due',
                        'payment_state', 'invoice_origin',
                    ],
                },
                limit=page_size,
                offset=offset
            )

            # Extract pagination metadata
            invoices = result.get('result', [])
            total_count = result.get('total_count', len(invoices))
            has_more = result.get('has_more', False)
            
            # Calculate pagination info
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
            
            return Response({
                "invoices": invoices,
                "order_info": {
                    "id": order['id'],
                    "name": order['name']
                },
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

    @extend_schema(
        request=None,
        responses={
            201: OpenApiResponse(description='Invoice created', response=InvoiceSerializer),
            200: OpenApiResponse(description='Invoice already exists'),
            404: OpenApiResponse(description='Sale order not found'),
            400: OpenApiResponse(description='Invoice creation failed'),
        },
        description="Create an invoice for the specified sale order if it doesn't exist"
    )
    def post(self, request, order_id):
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Check if order exists and belongs to user
            order_result = odoo.call(
                model='sale.order',
                method='search_read',
                kwargs={
                    'domain': [('id', '=', int(order_id)), ('user_id.id', '=', request.user.odoo_user_id)],
                    'fields': ['id', 'name', 'state', 'amount_total'],
                    'limit': 1
                }
            )
            
            if not order_result.get('result'):
                return Response(
                    {"error": "Sale order not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            order = order_result['result'][0]
            order_name = order['name']
            
            # Check if invoice already exists
            existing_result = odoo.call(
                model='account.move',
                method='search_read',
                kwargs={
                    'domain': [('invoice_origin', '=', order_name)],
                    'fields': ['id', 'name', 'state', 'amount_total'],
                    'limit': 1
                }
            )
            
            if existing_result.get('result'):
                existing_invoice = existing_result['result'][0]
                return Response({
                    'message': 'Invoice already exists',
                    'invoice_id': existing_invoice['id'],
                    'invoice_name': existing_invoice['name'],
                    'state': existing_invoice['state']
                }, status=status.HTTP_200_OK)

            # Confirm order if not already confirmed
            if order['state'] not in ['sale', 'done']:
                odoo.call(
                    model='sale.order',
                    method='action_confirm',
                    args=[[int(order_id)]]
                )

            # Create invoice
            invoice_ids = odoo.call(
                model='sale.order',
                method='_create_invoices',
                args=[[int(order_id)], {
                    'move_type': 'out_invoice',
                }]
            )
            
            if not invoice_ids:
                return Response(
                    {"error": "Invoice creation failed"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            invoice_id = invoice_ids[0]
            
            # Post the invoice
            odoo.call(
                model='account.move',
                method='action_post',
                args=[[invoice_id]]
            )
            
            # Get created invoice details
            invoice_result = odoo.call(
                model='account.move',
                method='search_read',
                kwargs={
                    'domain': [('id', '=', invoice_id)],
                    'fields': ['id', 'name', 'amount_total', 'state'],
                    'limit': 1
                }
            )
            
            invoice = invoice_result['result'][0] if invoice_result.get('result') else {'id': invoice_id}
            
            return Response({
                'message': 'Invoice created successfully',
                'invoice_id': invoice['id'],
                'invoice_name': invoice.get('name', ''),
                'amount_total': invoice.get('amount_total', order['amount_total']),
                'state': invoice.get('state', 'draft')
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InvoiceRetrieveAPIView(GenericAPIView):
    """
    Retrieve a single invoice if it belongs to an order of the authenticated user.
    """
    
    @extend_schema(
        responses={200: InvoiceSerializer},
        description="Retrieve a single invoice by ID"
    )
    def get(self, request, id):
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Get invoice with validation that it belongs to user's order
            result = odoo.call(
                model='account.move',
                method='search_read',
                kwargs={
                    'domain': [
                        ('id', '=', int(id)),
                        ('invoice_line_ids.sale_line_ids.order_id.user_id', '=', request.user.odoo_user_id)
                    ],
                    'fields': [
                        'id', 'name', 'amount_total', 'amount_residual', 
                        'invoice_date', 'state', 'invoice_date_due',
                        'payment_state', 'invoice_origin', 'ref',
                        'amount_untaxed', 'amount_tax',
                    ],
                    'limit': 1
                }
            )
            
            invoices = result.get('result', [])
            
            if not invoices:
                return Response(
                    {"error": "Invoice not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            return Response(invoices[0], status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentRegisterAPIView(GenericAPIView):
    """
    Register and manage payments for invoices belonging to orders of the authenticated user.
    """
    serializer_class = PaymentRegisterSerializer

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
        ],
        responses={200: PaymentRegisterSerializer(many=True)},
        description="List all payments for a given invoice belonging to user's order"
    )
    def get(self, request, invoice_id):
        # Pagination parameters
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Limit max page size to prevent abuse
        page_size = min(page_size, 100)
        
        # Calculate offset
        offset = (page - 1) * page_size

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # First validate invoice belongs to user's order
            invoice_result = odoo.call(
                model='account.move',
                method='search_read',
                kwargs={
                    'domain': [
                        ('id', '=', int(invoice_id)),
                        ('invoice_line_ids.sale_line_ids.order_id.user_id', '=', request.user.odoo_user_id)
                    ],
                    'fields': ['id', 'name', 'amount_residual'],
                    'limit': 1
                }
            )
            
            if not invoice_result.get('result'):
                return Response(
                    {"error": "Invoice not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            invoice = invoice_result['result'][0]
            
            # Get payments with pagination
            result = odoo.call(
                model='account.payment',
                method='search_read',
                kwargs={
                    'domain': [('invoice_ids', 'in', [int(invoice_id)])],
                    'fields': [
                        'id', 'amount', 'payment_date', 'journal_id', 'state',
                        'payment_method_id', 'ref', 'currency_id',
                    ],
                },
                limit=page_size,
                offset=offset
            )

            # Extract pagination metadata
            payments = result.get('result', [])
            total_count = result.get('total_count', len(payments))
            has_more = result.get('has_more', False)
            
            # Calculate pagination info
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
            
            return Response({
                "payments": payments,
                "invoice_info": {
                    "id": invoice['id'],
                    "name": invoice['name'],
                    "amount_residual": invoice['amount_residual']
                },
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

    @extend_schema(
        request=PaymentRegisterSerializer,
        responses={
            200: OpenApiResponse(description='Payment registered'),
            404: OpenApiResponse(description='Invoice not found'),
            400: OpenApiResponse(description='Invalid amount or request data'),
        },
        description="Register a payment for a given invoice belonging to user's order"
    )
    def post(self, request, invoice_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        amount = serializer.validated_data.get('amount')
        journal_id = serializer.validated_data.get('journal_id')
        payment_date = serializer.validated_data.get('payment_date')
        payment_method_id = serializer.validated_data.get('payment_method_id', False)
        communication = serializer.validated_data.get('communication', '')

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Validate invoice belongs to user's order
            invoice_result = odoo.call(
                model='account.move',
                method='search_read',
                kwargs={
                    'domain': [
                        ('id', '=', int(invoice_id)),
                        ('invoice_line_ids.sale_line_ids.order_id.user_id', '=', request.user.odoo_user_id)
                    ],
                    'fields': ['id', 'name', 'amount_residual', 'currency_id', 'partner_id'],
                    'limit': 1
                }
            )
            
            if not invoice_result.get('result'):
                return Response(
                    {"error": "Invoice not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            invoice = invoice_result['result'][0]
            amount_due = invoice['amount_residual']
            
            # Validate payment amount
            if amount_due == 0:
                return Response(
                    {'message': 'Invoice already paid'}, 
                    status=status.HTTP_200_OK
                )

            if amount > amount_due:
                return Response(
                    {'error': 'Payment amount exceeds due amount'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create payment
            payment_id = odoo.call(
                model='account.payment',
                method='create',
                args=[{
                    'amount': amount,
                    'payment_date': payment_date.strftime('%Y-%m-%d'),
                    'journal_id': journal_id,
                    'payment_method_id': payment_method_id,
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': invoice['partner_id'][0] if invoice.get('partner_id') else False,
                    'ref': communication,
                    'currency_id': invoice.get('currency_id', False),
                    'invoice_ids': [(4, int(invoice_id))],
                }]
            )
            
            # Post the payment
            odoo.call(
                model='account.payment',
                method='action_post',
                args=[[payment_id]]
            )
            
            return Response({
                'message': 'Payment registered successfully',
                'payment_id': payment_id,
                'invoice_id': invoice_id,
                'amount': amount
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            