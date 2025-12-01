from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError, NotFound

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.utils.odoo import get_odoo_client
from apps.utils.pagination import StandardResultsSetPagination
from .serializers import (
    InvoiceSerializer,
    PaymentJournalSerializer,
    PaymentMethodSerializer,
    PaymentRegisterSerializer,
    PaymentProofSerializer
)


class PaymentProofAPIView(GenericAPIView):
    serializer_class = PaymentProofSerializer

    def get_queryset(self):
        return []
    
    def post(self, request, order_id):
        """Create payment proof in Odoo"""
        # Validate delivery person access
        delivery_person_id = request.user.salesperson_id
        if not delivery_person_id:
            return Response(
                {'error': 'Salesperson not assigned'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # Check order access
        odoo = get_odoo_client()
        order_exists = odoo.call('sale.order', 'search_count', [
            [('id', '=', order_id), 
             ('delivery_person_id', '=', delivery_person_id)]
        ])
        if not order_exists:
            return Response(
                {'error': 'Order not found or access denied'}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # Validate and prepare data
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        # Create payment proof in Odoo
        try:
            proof_id = odoo.call('payment.proof', 'create', [{
                'sale_order_id': order_id,
                'amount': float(data['amount']),
                'payment_date': data['payment_date'].strftime('%Y-%m-%d %H:%M:%S'),
                'payment_method_id': data['payment_method_id'],
                'journal_id': data['journal_id'],
                'proof_image': data['proof_image'],
                'state': 'submitted',
            }])
            
            return Response({
                'id': int(proof_id.split('(')[1].split(',')[0]),
                'message': 'Payment proof submitted for review'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, order_id):
        """List payment proofs for an order"""
        delivery_person_id = request.user.salesperson_id
        if not delivery_person_id:
            return Response(
                {'error': 'Salesperson not assigned'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # Get proofs from Odoo
        odoo = get_odoo_client()
        proofs = odoo.call('payment.proof', 'search_read', [
            [('sale_order_id', '=', order_id),
             ('sale_order_id.delivery_person_id', '=', delivery_person_id)]
        ], {'fields': [
            'id', 'name', 'amount', 'payment_date', 
            'state', 'payment_method_id', 'journal_id', 'proof_image'
        ]})
        
        return Response(proofs, status=status.HTTP_200_OK)


class PaymentProofDetailAPIView(GenericAPIView):
    serializer_class = PaymentProofSerializer
    
    def get(self, request, id):
        try:
            odoo = get_odoo_client()
            payment_proof = odoo.call('payment.proof', 'search_read',
                              args=[[('id', '=', id), ('sale_order_id.delivery_person_id', '=', request.user.salesperson_id)]],
                              kwargs={'fields': [
                                'id', 'name', 'amount', 'payment_date', 
                                'state', 'payment_method_id', 'journal_id', 'proof_image'
                              ]})
            if not payment_proof:
                raise NotFound("Payment proof not found")
            
            return Response(payment_proof[0], status=status.HTTP_200_OK)

        except NotFound as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, id):
        try:
            odoo = get_odoo_client()
            success = odoo.call('payment.proof', 'unlink', args=[[id]])
            if not success:
                return Response({'error': 'Failed to delete payment proof'}, status=status.HTTP_400_BAD_REQUEST)
            return Response({'info': 'Payment proof deleted'}, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request, id):
        try:
            odoo = get_odoo_client()
            values = {}
            if 'amount' in request.data:
                values['amount'] = request.data['amount']
            if 'payment_date' in request.data:
                values['payment_date'] = request.data['payment_date']
            if 'payment_method_id' in request.data:
                values['payment_method_id'] = request.data['payment_method_id']
            if 'journal_id' in request.data:
                values['journal_id'] = request.data['journal_id']
            if 'proof_image' in request.data:
                values['proof_image'] = request.data['proof_image']

            success = odoo.call('payment.proof', 'write', args=[[id], values])
            if not success:
                return Response({'error': 'Failed to update payment proof'}, status=status.HTTP_400_BAD_REQUEST)
            return Response({'info': 'Payment proof updated'}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PaymentJournalListAPIView(GenericAPIView):
    serializer_class = PaymentJournalSerializer

    @extend_schema(
        responses=PaymentJournalSerializer(many=True),
        description="List all payment journals from Odoo"
    )
    def get(self, request):
        odoo = get_odoo_client()
        journals = odoo.call('account.journal', 'search_read', kwargs={'fields': ['id', 'name']})
        return Response(journals, status=status.HTTP_200_OK)


class PaymentMethodListAPIView(GenericAPIView):
    serializer_class = PaymentMethodSerializer

    @extend_schema(
        responses=PaymentMethodSerializer(many=True),
        description="List all payment methods from Odoo"
    )
    def get(self, request):
        odoo = get_odoo_client()
        try:
            payment_methods = odoo.call('account.payment.method', 'search_read', kwargs={'fields': ['id', 'name']})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(payment_methods, status=status.HTTP_200_OK)


class InvoiceListAPIView(GenericAPIView):
    serializer_class = InvoiceSerializer
    pagination_class = StandardResultsSetPagination

    @extend_schema(
        # parameters=[
        #     OpenApiParameter(name='order_id', description='Sale order ID', required=True, type=int)
        # ],
        responses=InvoiceSerializer(many=True),
        description="Get invoices related to a sale order assigned to the delivery person"
    )
    def get(self, request, order_id):
        delivery_person_id = request.user.salesperson_id
        if not delivery_person_id:
            raise ValidationError({'error': 'Salesperson not assigned to this user'})

        domain = [('invoice_origin', '!=', False)]
        odoo = get_odoo_client()
        sale_order = odoo.call('sale.order', 'search_read',
                               args=[[('id', '=', int(order_id)), ('delivery_person_id.id', '=', delivery_person_id)]],
                               kwargs={'fields': ['name']})

        if not sale_order:
            return Response({'error': 'Sale order not found or access denied'}, status=status.HTTP_404_NOT_FOUND)

        sale_order_name = sale_order[0]['name']
        domain.append(('invoice_origin', '=', sale_order_name))

        invoices = odoo.call('account.move', 'search_read',
                             args=[domain],
                             kwargs={'fields': ['id', 'name', 'amount_total', 'amount_residual', 'invoice_date']})

        page = self.paginate_queryset(invoices)
        return self.get_paginated_response(page)

    @extend_schema(
        request=None,
        responses={
            201: OpenApiResponse(description='Invoice created', response=InvoiceSerializer),
            200: OpenApiResponse(description='Invoice already exists'),
            404: OpenApiResponse(description='Sale order not found'),
            400: OpenApiResponse(description='Invoice creation failed'),
            500: OpenApiResponse(description='Internal server error'),
        },
        description="Create an invoice for the specified sale order if it doesn't exist"
    )
    def post(self, request, order_id):
        try:
            # Read sale order with state field
            odoo = get_odoo_client()
            sale_order = odoo.call('sale.order', 'read', args=[[order_id]], kwargs={'fields': ['name', 'state']})
            if not sale_order:
                return Response({'error': 'Sale order not found'}, status=status.HTTP_404_NOT_FOUND)

            # Confirm order if not already confirmed
            if sale_order[0]['state'] not in ['sale', 'done']:
                odoo.call('sale.order', 'action_confirm', args=[[order_id]])

            sale_order_name = sale_order[0]['name']
            existing_invoices = odoo.call('account.move', 'search_read',
                                            args=[[('invoice_origin', '=', sale_order_name)]],
                                            kwargs={'fields': ['id', 'state', 'amount_total']})

            if existing_invoices:
                return Response({
                    'info': 'Invoice already exists',
                    'invoice_id': existing_invoices[0]['id']
                }, status=status.HTTP_200_OK)

            # CORRECTED METHOD NAME: Use action_invoice_create
            invoice_ids = odoo.call('sale.order', 'action_create_invoice', args=[[order_id]])
            if not invoice_ids:
                return Response({'error': 'Invoice creation failed'}, status=status.HTTP_400_BAD_REQUEST)

            invoice_id = invoice_ids[0]
            odoo.call('account.move', 'action_post', args=[[invoice_id]])

            return Response({'info': 'Invoice created', 'invoice_id': invoice_id}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InvoiceRetrieveAPIView(GenericAPIView):
    serializer_class = InvoiceSerializer

    @extend_schema(
        # parameters=[
        #     OpenApiParameter(name='id', description='Invoice ID', required=True, type=int)
        # ],
        responses=InvoiceSerializer,
        description="Retrieve a single invoice by ID"
    )
    def get(self, request, id):
        odoo = get_odoo_client()
        invoice = odoo.call('account.move', 'search_read', args=[[('id', '=', id)]],
                            kwargs={'fields': ['id', 'name', 'amount_total', 'amount_residual', 'invoice_date']})
        if not invoice:
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(invoice[0], status=status.HTTP_200_OK)

    @extend_schema(
        # parameters=[
        #     OpenApiParameter(name='id', description='Invoice ID', required=True, type=int)
        # ],
        responses={204: OpenApiResponse(description='Invoice deleted')},
        description="Delete an invoice by ID"
    )
    def delete(self, request, id):
        odoo = get_odoo_client()
        success = odoo.call('account.move', 'unlink', args=[[id]])
        if not success:
            return Response({'error': 'Failed to delete invoice'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'info': 'Invoice deleted'}, status=status.HTTP_204_NO_CONTENT)


class PaymentRegisterAPIView(GenericAPIView):
    serializer_class = PaymentRegisterSerializer

    @extend_schema(
        request=PaymentRegisterSerializer,
        responses={
            200: OpenApiResponse(description='Payment registered'),
            404: OpenApiResponse(description='Invoice not found'),
            400: OpenApiResponse(description='Invalid amount or request data'),
        },
        description="Register a payment for a given invoice"
    )
    def post(self, request, invoice_id):
        serializer = PaymentRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data.get('amount')
        journal_id = serializer.validated_data.get('journal_id')
        payment_date = serializer.validated_data.get('payment_date')
        odoo = get_odoo_client()
        invoice_data = odoo.call('account.move', 'read', args=[[invoice_id]], kwargs={'fields': ['amount_residual']})
        if not invoice_data:
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)

        amount_due = invoice_data[0]['amount_residual']
        if amount_due == 0:
            return Response({'info': 'Invoice already paid'}, status=status.HTTP_200_OK)

        if amount > amount_due:
            return Response({'error': 'Amount exceeds due'}, status=status.HTTP_400_BAD_REQUEST)

        payment_wizard_id = odoo.call('account.payment.register', 'create', [{
            'amount': amount,
            'payment_date': payment_date,
            'journal_id': journal_id,
            'payment_type': 'inbound',
        }])

        odoo.call('account.payment.register', 'action_create_payments', args=[[payment_wizard_id], {
            'active_model': 'account.move',
            'active_ids': [invoice_id],
        }])

        payments = odoo.call('account.payment', 'search_read', args=[[('invoice_ids', 'in', [invoice_id])]],
                             kwargs={'fields': ['id', 'amount', 'payment_date', 'journal_id']})
        return Response({'info': 'Payment registered', 'payments': payments}, status=status.HTTP_200_OK)

    @extend_schema(
        responses=PaymentRegisterSerializer(many=True),
        description="List all payments for a given invoice"
    )
    def get(self, request, invoice_id):
        odoo = get_odoo_client()
        payments = odoo.call('account.payment', 'search_read', args=[[('invoice_ids', 'in', [invoice_id])]],
                             kwargs={'fields': ['id', 'amount', 'payment_date', 'journal_id', 'state']})
        return Response(payments, status=status.HTTP_200_OK)

    @extend_schema(
        request=PaymentRegisterSerializer,
        responses={200: OpenApiResponse(description='Payment updated')},
        description="Update a payment by ID"
    )
    def put(self, request, invoice_id):
        payment_id = request.data.get('payment_id')
        if not payment_id:
            return Response({'error': 'payment_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        values = {}
        if 'amount' in request.data:
            values['amount'] = request.data['amount']
        if 'payment_date' in request.data:
            values['payment_date'] = request.data['payment_date']
        if 'journal_id' in request.data:
            values['journal_id'] = request.data['journal_id']
        odoo = get_odoo_client()
        success = odoo.call('account.payment', 'write', args=[[payment_id], values])
        if not success:
            return Response({'error': 'Failed to update payment'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'info': 'Payment updated'}, status=status.HTTP_200_OK)

    @extend_schema(
        request=None,
        responses={204: OpenApiResponse(description='Payment deleted')},
        description="Delete a payment by ID"
    )
    def delete(self, request, invoice_id):
        payment_id = request.data.get('payment_id')
        if not payment_id:
            return Response({'error': 'payment_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        odoo = get_odoo_client()
        success = odoo.call('account.payment', 'unlink', args=[[payment_id]])
        if not success:
            return Response({'error': 'Failed to delete payment'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'info': 'Payment deleted'}, status=status.HTTP_204_NO_CONTENT)
