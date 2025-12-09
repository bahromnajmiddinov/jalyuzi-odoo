from django.urls import path
from .views import (
    OrderInvoiceListAPIView,
    InvoiceDetailAPIView,
    InvoicePaymentListAPIView,
    PaymentDetailAPIView,
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
]