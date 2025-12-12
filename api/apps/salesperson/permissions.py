from rest_framework.permissions import BasePermission
from django.conf import settings


class IsLinkedToOdoo(BasePermission):
    """
    Custom permission to only allow users linked to Odoo.
    """

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and hasattr(user, 'odoo_user_id') and user.odoo_user_id is not None


class IsOdoo(BasePermission):
    """
    Make sure only Odoo servers can access this view
    """
    def has_permission(self, request, view):
        expected = getattr(settings, "ODOO_SHARED_TOKEN", None)
        received = request.headers.get("X-ODOO-TOKEN")
        return received is not None and received == expected
    
