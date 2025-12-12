from django.urls import path

from rest_framework_simplejwt.views import (
    TokenVerifyView,
)

from .views import (
    DeliveryPersonLoginAPIView, DeliveryPersonAPIView,
    test_websocket, TokenRefreshAPIView, send_notification,
)


urlpatterns = [
    path('login/', DeliveryPersonLoginAPIView.as_view(), name='salesperson_login'),
    path('token/refresh/', TokenRefreshAPIView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('me/', DeliveryPersonAPIView.as_view(), name='me'),
    path('test-websocket/', test_websocket, name='test_websocket'),
    path('send-notification/', send_notification, name='send_notification'),
]
