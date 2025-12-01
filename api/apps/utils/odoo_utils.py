from apps.utils.odoo import get_odoo_client


def _get_profit_per_order(salesperson_id):
    """
    Retrieve the profit per order for a given salesperson.
    This is a placeholder function and should be implemented based on your business logic.
    """
    odoo = get_odoo_client()
    profit_percentage = odoo.call(
            'hr.employee',
            'search_read',
            args=[[('id', '=', salesperson_id)]],
            kwargs={'fields': ['profit_percentage'], 'limit': 1}
        )
    profit_percentage = profit_percentage[0]['profit_percentage'] if profit_percentage else None
    if not profit_percentage:
        return 0.0
    return profit_percentage / 100.0
