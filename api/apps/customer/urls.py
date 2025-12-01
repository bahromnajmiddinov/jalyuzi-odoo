from django.urls import path

from .views import CustomerListAPIView, CustomerRetrieveAPIView


urlpatterns = [
    path('', CustomerListAPIView.as_view(), name='cusutomer_list'),
    path('<int:id>/', CustomerRetrieveAPIView.as_view(), name='customer_retrieve'),
]
