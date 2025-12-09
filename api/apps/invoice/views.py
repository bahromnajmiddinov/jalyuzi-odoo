from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError, NotFound

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.utils.odoo import get_odoo_client_with_cached_session
from .serializers import (
    InvoiceSerializer,
    PaymentSerializer,
    PaymentRegisterSerializer,
)


class OrderInvoiceListAPIView(GenericAPIView):
    """
    Get invoices for a specific order and create invoices for orders.
    """
    serializer_class = InvoiceSerializer
    
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
                description='Filter by invoice state (draft, posted, cancel)',
                required=False,
                type=str,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={200: InvoiceSerializer(many=True)},
        summary="List invoices for an order",
        description="Get all invoices related to a specific sale order"
    )
    def get(self, request, order_id):
        """Get all invoices for a specific order"""
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        offset = (page - 1) * page_size
        invoice_state = request.query_params.get('state')

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            if isinstance(odoo, Response):
                return odoo

            # Verify order belongs to user
            order_result = odoo.call(
                model='sale.order',
                method='search_read',
                kwargs={
                    'domain': [
                        ('id', '=', int(order_id)), 
                        ('user_id.id', '=', request.user.odoo_user_id)
                    ],
                    'fields': ['id', 'name', 'invoice_ids'],
                    'limit': 1,
                },
                relation_fields={
                    'invoice_ids': ['id'],
                    }
            )
            if not order_result.get('result'):
                return Response(
                    {"error": "Order not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            order = order_result['result'][0]
            invoice_ids = order.get('invoice_ids', [])
            
            if isinstance(invoice_ids[0], dict):
                invoice_ids = list(order['invoice_ids'][0].values())
            
            if not invoice_ids:
                return Response({
                    "invoices": [],
                    "order_info": {
                        "id": order['id'],
                        "name": order['name']
                    },
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_count": 0,
                        "total_pages": 0,
                        "has_next": False,
                        "has_previous": False,
                    }
                })

            # Build domain for invoices
            domain = [('id', 'in', invoice_ids)]
            if invoice_state:
                domain.append(('state', '=', invoice_state))
            
            # Get invoices with pagination
            result = odoo.call(
                model='account.move',
                method='search_read',
                kwargs={
                    'domain': domain,
                    'fields': [
                        'id', 'name', 'invoice_date', 'invoice_date_due',
                        'amount_total', 'amount_residual', 'amount_untaxed', 'amount_tax',
                        'state', 'payment_state', 'currency_id', 'partner_id',
                        'invoice_origin', 'ref',
                    ],
                },
                limit=page_size,
                offset=offset,
                relation_fields={
                    'currency_id': ['id', 'name', 'symbol'],
                    'partner_id': ['id', 'name', 'email'],
                }
            )

            invoices = result.get('result', [])
            total_count = result.get('total_count', len(invoices))
            has_more = result.get('has_more', False)
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
            201: OpenApiResponse(description='Invoice created successfully'),
            200: OpenApiResponse(description='Invoice already exists'),
            404: OpenApiResponse(description='Order not found'),
            400: OpenApiResponse(description='Cannot create invoice'),
        },
        summary="Create invoice for order",
        description="Create an invoice for the specified sale order"
    )
    def post(self, request, order_id):
        """Create invoice for a sale order"""
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            if isinstance(odoo, Response):
                return odoo

            # Verify order belongs to user
            order_result = odoo.call(
                model='sale.order',
                method='search_read',
                kwargs={
                    'domain': [
                        ('id', '=', int(order_id)), 
                        ('user_id.id', '=', request.user.odoo_user_id)
                    ],
                    'fields': ['id', 'name', 'state', 'invoice_status', 'invoice_ids'],
                    'limit': 1
                },
                relation_fields={
                    'invoice_ids': ['id'],
                    }
            )
            
            if not order_result.get('result'):
                return Response(
                    {"error": "Order not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            order = order_result['result'][0]
            
            # Check if invoices already exist
            if order.get('invoice_ids'):
                return Response({
                    'message': 'Invoice(s) already exist for this order',
                    'invoice_ids': order['invoice_ids']
                }, status=status.HTTP_200_OK)
            
            # Check if order is confirmed
            if order['state'] not in ['sale', 'done']:
                return Response(
                    {'error': 'Order must be confirmed before creating invoice'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            result = odoo.call(
                model='sale.order',
                method='action_create_invoice',
                args=[[int(order_id)]]
            )
            
            if not result:
                return Response(
                    {"error": "Failed to create invoice"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # result is a list of invoice IDs
            result = result.get('result', [])
            invoice_ids = result if isinstance(result, list) else [result]
            
            # Get created invoice details
            invoice_result = odoo.call(
                model='account.move',
                method='search_read',
                kwargs={
                    'domain': [('id', 'in', invoice_ids)],
                    'fields': ['id', 'name', 'amount_total', 'state', 'payment_state'],
                }
            )
            
            invoices = invoice_result.get('result', [])
            
            return Response({
                'message': 'Invoice(s) created successfully',
                'invoices': invoices
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InvoiceDetailAPIView(GenericAPIView):
    """
    Retrieve a single invoice with its details and payments.
    """
    serializer_class = InvoiceSerializer
    
    @extend_schema(
        responses={200: InvoiceSerializer},
        summary="Get invoice details",
        description="Retrieve a single invoice with payment information"
    )
    def get(self, request, invoice_id):
        """Get detailed invoice information including payments"""
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            if isinstance(odoo, Response):
                return odoo

            # Get invoice with validation through sale order
            invoice_result = odoo.call(
                model='account.move',
                method='search_read',
                kwargs={
                    'domain': [
                        ('id', '=', int(invoice_id)),
                        ('move_type', '=', 'out_invoice'),
                        ('user_id', '=', request.user.odoo_user_id)
                    ],
                    'fields': [
                        'id', 'name', 'invoice_date', 'invoice_date_due',
                        'amount_total', 'amount_residual', 'amount_untaxed', 'amount_tax',
                        'state', 'payment_state', 'currency_id', 'partner_id',
                        'invoice_origin', 'ref', 'invoice_payment_term_id',
                    ],
                    'limit': 1
                },
                relation_fields={
                    'currency_id': ['id', 'name', 'symbol'],
                    'partner_id': ['id', 'name', 'email'],
                    'invoice_payment_term_id': ['id', 'name'],
                }
            )
            
            if not invoice_result.get('result'):
                return Response(
                    {"error": "Invoice not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            invoice = invoice_result['result'][0]
            
            # Get payment reconciliation information
            reconcile_result = odoo.call(
                model='account.move',
                method='read',
                args=[[int(invoice_id)], ['invoice_payments_widget']]
            )
            
            payment_widget = None
            if reconcile_result:
                payment_widget = reconcile_result[0].get('invoice_payments_widget')
            
            invoice['payment_info'] = payment_widget
            
            return Response(invoice, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InvoicePaymentListAPIView(GenericAPIView):
    """
    List and register payments for an invoice.
    """
    serializer_class = PaymentSerializer
    
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
        responses={200: PaymentSerializer(many=True)},
        summary="List payments for invoice",
        description="Get all payments registered against an invoice"
    )
    def get(self, request, invoice_id):
        """Get all payments for a specific invoice"""
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        offset = (page - 1) * page_size

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            if isinstance(odoo, Response):
                return odoo

            # Verify invoice belongs to user's order
            # invoice_result = odoo.call(
            #     model='account.move',
            #     method='search_read',
            #     kwargs={
            #         'domain': [
            #             ('id', '=', int(invoice_id)),
            #             ('move_type', '=', 'out_invoice'),
            #             ('user_id', '=', request.user.odoo_user_id)
            #         ],
            #         'fields': ['id', 'name', 'amount_total', 'amount_residual'],
            #         'limit': 1
            #     }
            # )
            
            # if not invoice_result.get('result'):
            #     return Response(
            #         {"error": "Invoice not found or access denied"},
            #         status=status.HTTP_404_NOT_FOUND
            #     )
            
            # invoice = invoice_result['result'][0]
            
            # Get payments reconciled with this invoice
            payment_result = odoo.call(
                model='account.payment',
                method='search_read',
                kwargs={
                    'domain': [
                        ('reconciled_invoice_ids', 'in', [int(invoice_id)]),
                    ],
                    'fields': [
                        'id', 'name', 'amount', 'date',
                        'state', 'payment_type', 'payment_method_line_id',
                        'journal_id', 'currency_id', 'partner_id',
                    ],
                },
                limit=page_size,
                offset=offset,
                sudo=True
            )

            payments = payment_result.get('result', [])
            total_count = payment_result.get('total_count', len(payments))
            has_more = payment_result.get('has_more', False)
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
            
            return Response({
                "payments": payments,
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
            201: OpenApiResponse(description='Payment registered successfully'),
            404: OpenApiResponse(description='Invoice not found'),
            400: OpenApiResponse(description='Invalid payment data'),
        },
        summary="Register payment for invoice",
        description="Register a new payment against an invoice"
    )
    def post(self, request, invoice_id):
        """Register a payment for an invoice"""
        serializer = PaymentRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        amount = serializer.validated_data.get('amount')
        journal_id = serializer.validated_data.get('journal_id')
        payment_date = serializer.validated_data.get('payment_date')
        payment_method_line_id = serializer.validated_data.get('payment_method_line_id')
        communication = serializer.validated_data.get('communication', '')

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            if isinstance(odoo, Response):
                return odoo

            # Verify invoice belongs to user's order
            invoice_result = odoo.call(
                model='account.move',
                method='search_read',
                kwargs={
                    'domain': [
                        ('id', '=', int(invoice_id)),
                        ('move_type', '=', 'out_invoice'),
                        ('invoice_line_ids.sale_line_ids.order_id.user_id', '=', request.user.odoo_user_id)
                    ],
                    'fields': [
                        'id', 'name', 'amount_residual', 'currency_id', 
                        'partner_id', 'state'
                    ],
                    'limit': 1
                }
            )
            
            if not invoice_result.get('result'):
                return Response(
                    {"error": "Invoice not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            invoice = invoice_result['result'][0]
            
            # Check invoice state
            if invoice['state'] != 'posted':
                return Response(
                    {'error': 'Invoice must be posted to register payments'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            amount_residual = invoice['amount_residual']
            
            # Validate payment amount
            if amount_residual == 0:
                return Response(
                    {'message': 'Invoice is already fully paid'},
                    status=status.HTTP_200_OK
                )

            if amount > amount_residual:
                return Response(
                    {'error': 'Payment amount exceeds outstanding amount'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create payment using account.payment model
            payment_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': invoice['partner_id'][0] if invoice.get('partner_id') else False,
                'amount': float(amount),
                'currency_id': invoice['currency_id'][0] if invoice.get('currency_id') else False,
                'journal_id': int(journal_id),
                'payment_date': payment_date.strftime('%Y-%m-%d'),
                'ref': communication,
            }
            
            # Add payment method line if provided
            if payment_method_line_id:
                payment_vals['payment_method_line_id'] = int(payment_method_line_id)
            
            # Create payment
            payment_id = odoo.call(
                model='account.payment',
                method='create',
                args=[payment_vals]
            )
            
            if not payment_id:
                return Response(
                    {'error': 'Failed to create payment'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Post the payment
            post_result = odoo.call(
                model='account.payment',
                method='action_post',
                args=[[payment_id]]
            )
            
            # Reconcile payment with invoice using Odoo's standard method
            try:
                # Method 1: Use js_assign_outstanding_line (preferred in Odoo UI)
                odoo.call(
                    model='account.move',
                    method='js_assign_outstanding_line',
                    args=[[int(invoice_id)], payment_id]
                )
            except Exception as e:
                # Method 2: Link via reconciled_invoice_ids if method 1 fails
                try:
                    odoo.call(
                        model='account.payment',
                        method='write',
                        args=[[payment_id], {
                            'reconciled_invoice_ids': [(4, int(invoice_id))]
                        }]
                    )
                except:
                    pass  # Payment might auto-reconcile
            
            # Get updated invoice info
            updated_invoice = odoo.call(
                model='account.move',
                method='read',
                args=[[int(invoice_id)], ['amount_residual', 'payment_state']]
            )
            
            return Response({
                'message': 'Payment registered successfully',
                'payment_id': payment_id,
                'invoice_id': invoice_id,
                'amount': amount,
                'remaining_amount': updated_invoice[0].get('amount_residual') if updated_invoice else None,
                'payment_state': updated_invoice[0].get('payment_state') if updated_invoice else None
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


class PaymentDetailAPIView(GenericAPIView):
    """
    Retrieve details of a specific payment.
    """
    serializer_class = PaymentSerializer
    
    @extend_schema(
        responses={200: PaymentSerializer},
        summary="Get payment details",
        description="Retrieve details of a specific payment"
    )
    def get(self, request, payment_id):
        """Get detailed payment information"""
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            if isinstance(odoo, Response):
                return odoo

            # Get payment with validation through invoice and order
            payment_result = odoo.call(
                model='account.payment',
                method='search_read',
                kwargs={
                    'domain': [
                        ('id', '=', int(payment_id)),
                        ('reconciled_invoice_ids.invoice_line_ids.sale_line_ids.order_id.user_id', '=', request.user.odoo_user_id)
                    ],
                    'fields': [
                        'id', 'name', 'amount', 'payment_date', 'date',
                        'state', 'payment_type', 'payment_method_line_id',
                        'journal_id', 'ref', 'currency_id', 'partner_id',
                        'reconciled_invoice_ids', 'move_id',
                    ],
                    'limit': 1
                }
            )
            
            if not payment_result.get('result'):
                return Response(
                    {"error": "Payment not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            payment = payment_result['result'][0]
            
            return Response(payment, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )