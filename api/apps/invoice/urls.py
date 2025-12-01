from django.urls import path

from .views import (
    PaymentJournalListAPIView, PaymentMethodListAPIView,
    PaymentProofAPIView, PaymentProofDetailAPIView
)


urlpatterns = [
    # path('<int:order_id>/', InvoiceListAPIView.as_view(), name='invoices_list'),
    # path('invoice/<int:id>/', InvoiceRetrieveAPIView.as_view(), name='invoice_detail'),
    # path('payment/<int:invoice_id>/', PaymentRegisterAPIView.as_view(), name='payment_register'),
    path('journals/', PaymentJournalListAPIView.as_view(), name='payment_journals'),
    path('payment-methods/', PaymentMethodListAPIView.as_view(), name='payment_methods'),
    path('orders/<int:order_id>/payments/', PaymentProofAPIView.as_view(), name='payment_proof'),
    path('payments/<int:id>/', PaymentProofDetailAPIView.as_view(), name='payment_proof_detail'),
]
