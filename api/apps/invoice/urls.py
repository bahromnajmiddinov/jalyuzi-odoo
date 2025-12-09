from django.urls import path
from .views import (
    OrderInvoiceListAPIView,
    InvoiceDetailAPIView,
    InvoicePaymentListAPIView,
    PaymentDetailAPIView,
    OrderPaymentProofListAPIView,
    PaymentProofDetailAPIView,
    PaymentProofSubmitAPIView,
    PaymentJournalAPIView,
    PaymentMethodLineAPIView,
)

urlpatterns = [
    # Invoice endpoints
    path(
        'orders/<int:order_id>/invoices/',
        OrderInvoiceListAPIView.as_view(),
        name='order-invoices'
    ),
    path(
        '<int:invoice_id>/',
        InvoiceDetailAPIView.as_view(),
        name='invoice-detail'
    ),
    
    # Payment endpoints
    path(
        '<int:invoice_id>/payments/',
        InvoicePaymentListAPIView.as_view(),
        name='invoice-payments'
    ),
    path(
        'payments/<int:payment_id>/',
        PaymentDetailAPIView.as_view(),
        name='payment-detail'
    ),
    
    # Payment Proof endpoints
    path(
        'orders/<int:order_id>/payment-proofs/',
        OrderPaymentProofListAPIView.as_view(),
        name='order-payment-proof-list'
    ),
    path(
        'payment-proofs/<int:proof_id>/',
        PaymentProofDetailAPIView.as_view(),
        name='payment-proof-detail'
    ),
    path(
        'payment-proofs/<int:proof_id>/submit/',
        PaymentProofSubmitAPIView.as_view(),
        name='payment-proof-submit'
    ),
    
    # Additional endpoints
    path(
        'payment-journals/',
        PaymentJournalAPIView.as_view(),
        name='payment-journal-list'
    ),
    path(
        'payment-method-lines/',
        PaymentMethodLineAPIView.as_view(),
        name='payment-method-line-list'
    ),
]