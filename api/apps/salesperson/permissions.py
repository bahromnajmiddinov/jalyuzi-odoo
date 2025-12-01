from rest_framework.permissions import BasePermission


class IsLinkedToOdoo(BasePermission):
    """
    Custom permission to only allow users linked to Odoo.
    """

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and hasattr(user, 'odoo_user_id') and user.odoo_user_id is not None
