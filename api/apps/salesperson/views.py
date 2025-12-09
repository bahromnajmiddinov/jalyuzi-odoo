import logging
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.db import transaction
from django.conf import settings

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import CustomUser
from .serializers import (
    DeliveryPersonLoginSerializer, 
    TokenResponseSerializer, 
    DeliveryPersonSerializer,
    TokenRefreshSerializer,
)
from apps.utils.odoo import get_odoo_client

logger = logging.getLogger(__name__)


@extend_schema(
    responses={
        200: OpenApiResponse(description='WebSocket test message sent successfully'),
        401: OpenApiResponse(description='Unauthorized'),
        500: OpenApiResponse(description='Failed to send WebSocket message'),
    },
    tags=['WebSocket'],
    summary='Test WebSocket connection',
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_websocket(request):
    """
    Test sending a WebSocket message to the user group.
    """
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.error("Channel layer is not configured")
            return Response(
                {"error": "WebSocket not configured"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        message_text = "Your monthly bill is due. Please make the payment."

        async_to_sync(channel_layer.group_send)(
            f"user_{request.user.id}",
            {
                "type": "send_notification",
                "message": message_text,
            }
        )
        
        logger.info(f"WebSocket message sent to user_{request.user.id}")
        return Response({"detail": "WebSocket test message sent."})
        
    except Exception as e:
        logger.error(f"WebSocket error for user {request.user.id}: {str(e)}", exc_info=True)
        return Response(
            {"error": f"Failed to send WebSocket message: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class TokenRefreshAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = TokenRefreshSerializer

    @extend_schema(
        request=TokenRefreshSerializer,
        responses={
            200: OpenApiResponse(
                description='Token refreshed successfully',
                response=TokenResponseSerializer
            ),
            400: OpenApiResponse(description='Invalid input'),
            401: OpenApiResponse(description='Invalid or expired refresh token'),
            500: OpenApiResponse(description='Server error or Odoo connection error')
        },
        tags=['Authentication'],
        summary='Refresh access token and update Odoo session cache',
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            refresh_token = serializer.validated_data.get('refresh')
            
            # Validate and decode the refresh token
            token = RefreshToken(refresh_token)
            user_id = token.get('user_id')
            
            # Get user from database
            from .models import CustomUser
            try:
                user = CustomUser.objects.get(id=user_id)
            except CustomUser.DoesNotExist:
                logger.error(f"User not found for id: {user_id}")
                return Response(
                    {'detail': 'User not found'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Generate new access token
            new_access_token = str(token.access_token)
            
            # Update Odoo session cache if user has Odoo credentials
            if hasattr(user, 'odoo_user_id') and user.odoo_user_id:
                try:
                    # Check if Odoo session exists in cache
                    session_cache_key = f"odoo_session_{getattr(settings, 'ODOO_DB', 'jdb')}_{user.username}"
                    cached_session = cache.get(session_cache_key)
                    
                    if cached_session:
                        # Refresh the Odoo session cache TTL (extend expiration)
                        # Default to 30 minutes (1800 seconds)
                        cache.set(session_cache_key, cached_session, 1800)
                        logger.info(f"Refreshed Odoo session cache for user {user.username}")
                        
                        # Also refresh user data cache if it exists
                        user_cache_key = f"delivery_person_{user.odoo_user_id}"
                        if cache.get(user_cache_key):
                            # Optionally, you can re-fetch fresh data from Odoo here
                            # For now, just extend the cache TTL
                            cache.touch(user_cache_key, 300)  # Extend by 5 minutes
                            logger.info(f"Extended user data cache for user {user.odoo_user_id}")
                    else:
                        logger.warning(f"No Odoo session cache found for user {user.username}")
                        # Session expired - user needs to login again
                        return Response(
                            {
                                'access_token': new_access_token,
                                'refresh_token': str(token),
                                'warning': 'Odoo session expired. Some features may require re-login.'
                            },
                            status=status.HTTP_200_OK
                        )
                        
                except Exception as e:
                    logger.error(f"Error refreshing Odoo cache for user {user.username}: {str(e)}")
                    # Continue anyway - JWT refresh succeeded
            
            logger.info(f"Token refreshed successfully for user: {user.username}")
            
            return Response({
                'access_token': new_access_token,
                'refresh_token': str(token),
                'user': {
                    'id': user.id,
                    'username': user.username,
                }
            }, status=status.HTTP_200_OK)
            
        except TokenError as e:
            logger.warning(f"Invalid refresh token: {str(e)}")
            return Response(
                {'detail': 'Invalid or expired refresh token'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to refresh token'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeliveryPersonLoginAPIView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = DeliveryPersonLoginSerializer

    @extend_schema(
        request=DeliveryPersonLoginSerializer,
        responses={
            200: OpenApiResponse(
                description='Login successful',
                response=TokenResponseSerializer
            ),
            400: OpenApiResponse(description='Invalid input'),
            403: OpenApiResponse(description='Incorrect password or account disabled'),
            404: OpenApiResponse(description='User not found'),
            429: OpenApiResponse(description='Too many login attempts'),
            500: OpenApiResponse(description='Server error or Odoo connection error')
        },
        tags=['Authentication'],
        summary='Delivery person login via phone number and password',
    )
    def post(self, request):
        # Rate limiting check
        username = request.data.get('username', '')
        rate_limit_key = f"login_attempts_{username}"
        attempts = cache.get(rate_limit_key, 0)
        
        if attempts >= 5:
            logger.warning(f"Too many login attempts for {username}")
            return Response(
                {'detail': 'Too many login attempts. Please try again later.'}, 
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data.get('username')
        password = serializer.validated_data.get('password')

        # Authenticate with Odoo using user's credentials
        try:
            odoo = get_odoo_client(username=username, password=password)
        except Exception as e:
            # Increment failed attempts
            cache.set(rate_limit_key, attempts + 1, 300)
            logger.error(f"Odoo authentication failed for {username}: {str(e)}")
            return Response(
                {'detail': 'Invalid credentials'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Get user details from Odoo (no need to search, we're already authenticated)
            users = odoo.call(
                'res.users', 
                'search_read',
                args=[[('login', '=', username)]],
                kwargs={
                    'fields': ['id', 'login', 'name', 'email', 'partner_id'],
                    'limit': 1
                }
            )
            
            if not users:
                cache.set(rate_limit_key, attempts + 1, 300)
                logger.warning(f"User not found in Odoo: {username}")
                return Response(
                    {'detail': 'User not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            odoo_user = users['result'][0]
            
        except Exception as e:
            cache.set(rate_limit_key, attempts + 1, 300)
            logger.error(f"Odoo user search error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Service temporarily unavailable. Please try again later.'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Clear rate limiting on successful authentication
        cache.delete(rate_limit_key)

        # Create or update local user
        try:
            with transaction.atomic():
                user, created = CustomUser.objects.get_or_create(
                    username=username,
                    defaults={
                        'odoo_user_id': odoo_user['id'],
                        'email': odoo_user.get('email', ''),
                    }
                )
                
                # Update user information if not created
                if not created:
                    user.username = odoo_user.get('login') or username
                    user.odoo_user_id = odoo_user['id']
                    user.email = odoo_user.get('email', '')
                
                # Sync the password locally (store for future local auth)
                user.set_password(password)
                user.save()
                
                logger.info(f"User {'created' if created else 'updated'}: {username}")

        except Exception as e:
            logger.error(f"Database error during user creation: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to create local user account'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Authenticate locally
        authenticated_user = authenticate(
            request=request, 
            username=username, 
            password=password
        )
        
        if not authenticated_user:
            logger.error(f"Local authentication failed for {username}")
            return Response(
                {'error': 'Failed to authenticate user locally'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Generate JWT tokens
        refresh = RefreshToken.for_user(authenticated_user)
        
        logger.info(f"Successful login for user: {username}")
        
        return Response({
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'user': {
                'id': authenticated_user.id,
                'username': authenticated_user.username,
            }
        }, status=status.HTTP_200_OK)


class DeliveryPersonAPIView(GenericAPIView):
    serializer_class = DeliveryPersonSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description='Delivery person details and statistics',
                response=DeliveryPersonSerializer
            ),
            403: OpenApiResponse(description='Not authenticated or not a delivery person'),
            500: OpenApiResponse(description='Server error or Odoo connection error')
        },
        tags=['Delivery Person'],
        summary='Get delivery person profile and statistics',
    )
    def get(self, request):
        user = request.user

        if not hasattr(user, 'odoo_user_id') or not user.odoo_user_id:
            return Response(
                {'detail': 'User is not linked to Odoo'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # Use cache for user data (5 minutes TTL)
        cache_key = f"delivery_person_{user.odoo_user_id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            logger.info(f"Returning cached data for user {user.odoo_user_id}")
            return Response(cached_data, status=status.HTTP_200_OK)

        # Use cached Odoo session - no password storage needed
        # The session was created during login and cached per user
        try:
            from django.conf import settings
            
            # Check if user has an active Odoo session
            session_cache_key = f"odoo_session_{getattr(settings, 'ODOO_DB', 'jdb')}_{user.username}"
            cached_session = cache.get(session_cache_key)
            
            if not cached_session:
                logger.error(f"No active Odoo session for user {user.username}")
                return Response(
                    {'detail': 'Session expired. Please login again.'}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Create client that will use the cached session
            # No password needed - it uses the cached session_id and uid
            odoo = get_odoo_client(
                username=user.username,
                password="",  # Empty password - will use cached session
                db=getattr(settings, 'ODOO_DB', 'jdb'),
                url=getattr(settings, 'ODOO_URL', 'http://localhost:8069')
            )
            
        except Exception as e:
            logger.error(f"Failed to create Odoo client for user {user.username}: {str(e)}")
            return Response(
                {'detail': 'Failed to connect to Odoo. Please login again.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            # Get user details from res.users and related partner
            odoo_user = odoo.call(
                'res.users', 
                'search_read',
                args=[[('id', '=', user.odoo_user_id)]],
                kwargs={
                    'fields': [
                        'name', 'login', 'email', 'mobile', 'phone',
                        'partner_id', 'image_1920_url', 'total_sales',
                        'total_orders', 'total_payments', 'debt_amount',
                        'debt_limit', 'profit_percentage', 'sale_debt', 'sale_debt_limit',
                        'pending_orders', 'delivered_orders', 'cancelled_orders'
                    ],
                    'limit': 1
                },
                relation_fields={'partner_id': ['delivery_person_sale_debt', 'delivery_person_sale_debt_limit', 'delivery_person_sales_amount']}
            )

            if not odoo_user:
                logger.error(f"Odoo user not found: {user.odoo_user_id}")
                return Response(
                    {'detail': 'User not found in Odoo'}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            odoo_user = odoo_user['result'][0]
            
            # Get partner details if needed (for additional fields)
            partner_id = odoo_user.get('partner_id') if odoo_user.get('partner_id') else None
            
            delivery_person_data = {
                'name': odoo_user.get('name'),
                'email': odoo_user.get('email'),
                'phone': odoo_user.get('mobile') or odoo_user.get('phone'),
                'avatar': odoo_user.get('image_1920'),
            }
            
            # If you have custom fields on res.partner for delivery stats, fetch them
            if partner_id:
                partner_data = {
                    'delivery_person_sale_debt': partner_id.get('delivery_person_sale_debt', 0.0),
                    'delivery_person_sale_debt_limit': partner_id.get('delivery_person_sale_debt_limit', 0.0),
                    'delivery_person_sales_amount': partner_id.get('delivery_person_sales_amount', 0.0),
                }
                
                if partner_data:
                    delivery_person_data.update(partner_data)

            # Fetch sales statistics
            # Assuming sale.order has a field linking to the delivery user
            domain = [
                ('user_id.id', '=', user.odoo_user_id),
                ('state', '!=', 'cancel')
            ]
            
            fields = ['name', 'amount_total', 'state', 'date_order', 'paid_amount', 'partner_id']
            orders = odoo.call(
                'sale.order', 
                'search_read', 
                args=[domain], 
                kwargs={
                    'fields': fields,
                    'order': 'date_order desc',
                    'limit': 5
                },
                relation_fields={'partner_id': ['name', 'id']}
            )
            print(orders)
            # Calculate statistics
            total_sales = odoo_user.get('total_sales', 0.0)
            total_orders = odoo_user.get('total_orders', 0)
            pending_orders = odoo_user.get('pending_orders', 0)
            delivered_orders = odoo_user.get('delivered_orders', 0)
            cancelled_orders = odoo_user.get('cancelled_orders', 0)

            stats = {
                "total_sales": total_sales,
                "total_orders": total_orders,
                "pending_orders": pending_orders,
                "delivered_orders": delivered_orders,
                "cancelled_orders": cancelled_orders,
                "recent_orders": orders['result'] if orders else []
            }

            response_data = {
                "user": delivery_person_data,
                "stats": stats
            }
            
            # Cache the response
            cache.set(cache_key, response_data, 300)  # 5 minutes
            
            logger.info(f"Successfully fetched data for user {user.odoo_user_id}")
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Odoo connection error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Service temporarily unavailable. Please try again later.'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            