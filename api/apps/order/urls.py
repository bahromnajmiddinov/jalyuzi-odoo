from django.urls import path

from .views import OrderListAPIView, OrderDetailAPIView


urlpatterns = [
    path('', OrderListAPIView.as_view(), name='orders_list'),
    path('<int:pk>/', OrderDetailAPIView.as_view(), name='order_detail'),
]
