import requests
import logging
from django.core.cache import cache
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


class OdooRESTClient:
    def __init__(self, url, db, username, password, use_cache=True):
        """
        Initialize Odoo client with per-user authentication.
        """
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session_id = None
        self.uid = None
        
        self.cache_key = f"odoo_session_{db}_{username}"
        
        if use_cache:
            cached_session = cache.get(self.cache_key)
            if cached_session:
                self.session_id = cached_session.get('session_id')
                self.uid = cached_session.get('uid')
                self.session.cookies.set("session_id", self.session_id)
                logger.info(f"Using cached session for user: {username}")
                return
            
        if password:
            self._login()
        else:
            raise Exception("No cached session found and no password provided")

    def _login(self):
        """Authenticate user with Odoo and store session."""
        login_url = f"{self.url}/web/session/authenticate"
        payload = {
            "jsonrpc": "2.0",
            "params": {
                "db": self.db,
                "login": self.username,
                "password": self.password,
            },
        }

        try:
            response = self.session.post(login_url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get("result") and not result.get("error"):
                result_data = result["result"]
                self.session_id = self.session.cookies.get("session_id")
                self.uid = result_data.get("uid")
                
                if not self.session_id or not self.uid:
                    raise Exception("Login failed: Invalid session or uid")
                
                cache.set(self.cache_key, {
                    'session_id': self.session_id,
                    'uid': self.uid
                }, timeout=3600)
                
                logger.info(f"Successfully logged in user: {self.username} (uid: {self.uid})")
            else:
                error_msg = result.get("error", {}).get("data", {}).get("message", "Unknown error")
                raise Exception(f"Login failed: {error_msg}")
                
        except requests.RequestException as e:
            logger.error(f"Login request failed for {self.username}: {e}")
            raise Exception(f"Login request failed: {e}")
        except Exception as e:
            logger.error(f"Login failed for {self.username}: {e}")
            raise Exception(f"Login failed: {e}")

    def _refresh_session(self):
        """Refresh the session by logging in again."""
        logger.info(f"Refreshing session for user: {self.username}")
        cache.delete(self.cache_key)
        self._login()

    def call(self, model, method, args=None, kwargs=None, limit=None, offset=None):
        """
        Call Odoo model method with automatic session refresh and pagination support.
        
        Args:
            model: Odoo model name (e.g., 'res.users')
            method: Method name (e.g., 'search_read')
            args: Positional arguments
            kwargs: Keyword arguments
            limit: Number of records to return (pagination)
            offset: Number of records to skip (pagination)
        
        Returns:
            Dict with:
                - result: The actual data
                - total_count: Total number of records (if paginated)
                - limit: Limit used
                - offset: Offset used
                - has_more: Boolean indicating if more records exist
        """
        url = f"{self.url}/custom_api/call"
        payload = {
            "model": model,
            "method": method,
            "args": args or [],
            "kwargs": kwargs or {}
        }
        
        # Add pagination parameters
        if limit is not None:
            payload["limit"] = limit
            payload["offset"] = offset or 0
        
        headers = {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest"
        }

        try:
            response = self.session.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 401 or "invalid session" in response.text.lower():
                logger.warning(f"Session expired for user: {self.username}, refreshing...")
                self._refresh_session()
                response = self.session.post(url, json=payload, headers=headers, timeout=10)
            
            response.raise_for_status()
            data = response.json()
            
            if 'error' in data.get('result', {}):
                error_msg = data['result']['error']
                logger.error(f"Odoo error for user {self.username}: {error_msg}")
                raise Exception(f"Odoo error: {error_msg}")
            
            # Return full response with pagination metadata
            return data["result"]
            
        except requests.RequestException as e:
            logger.error(f"Request failed for user {self.username}: {e}")
            raise Exception(f"Request failed: {e}")
        except ValueError as e:
            logger.error(f"Invalid JSON response for user {self.username}: {response.text}")
            raise Exception(f"Invalid JSON response: {response.text}")
        except Exception as e:
            logger.error(f"Odoo call failed for user {self.username}: {e}")
            raise Exception(f"Odoo call failed: {e}")

    def logout(self):
        """Logout and clear session cache."""
        try:
            logout_url = f"{self.url}/web/session/destroy"
            self.session.post(logout_url, timeout=5)
            cache.delete(self.cache_key)
            logger.info(f"Logged out user: {self.username}")
        except Exception as e:
            logger.warning(f"Logout failed for {self.username}: {e}")


def get_odoo_client(username, password, db="jdb", url="http://localhost:8069"):
    """
    Get Odoo client instance for specific user.
    """
    try:
        client = OdooRESTClient(
            url=url,
            db=db,
            username=username,
            password=password
        )
        return client
    except Exception as e:
        logger.error(f"Failed to create Odoo client for {username}: {e}")
        raise Exception(f"Connection failed: {str(e)}")
    

def get_odoo_client_with_cached_session(username, db="jdb", url="http://localhost:8069"):
    """
    Get Odoo client instance using cached session for specific user.
    """
    try:
        session_cache_key = f"odoo_session_{getattr(settings, 'ODOO_DB', 'jdb')}_{username}"
        cached_session = cache.get(session_cache_key)
        
        if not cached_session:
            logger.error(f"No active Odoo session for user {username}")
            return Response(
                {'detail': 'Session expired. Please login again.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        odoo = get_odoo_client(
            username=username,
            password="",
            db=getattr(settings, 'ODOO_DB', 'jdb'),
            url=getattr(settings, 'ODOO_URL', 'http://localhost:8069')
        )
        return odoo
        
    except Exception as e:
        logger.error(f"Failed to create Odoo client for user {username}: {str(e)}")
        return Response(
            {'detail': 'Failed to connect to Odoo. Please login again.'}, 
            status=status.HTTP_401_UNAUTHORIZED
        )


if __name__ == "__main__":
    client = get_odoo_client(
        username="user@example.com",
        password="user_password"
    )

    # Example with pagination
    result = client.call(
        model='sale.order',
        method='search_read',
        args=[[('state', '=', 'sale')]],
        kwargs={'fields': ['name', 'amount_total', 'state']},
        limit=10,
        offset=0
    )
    
    print("Orders:", result.get('result'))
    print(f"Total: {result.get('total_count')}, Has more: {result.get('has_more')}")
    
    client.logout()