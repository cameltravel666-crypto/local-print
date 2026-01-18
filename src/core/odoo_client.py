# -*- coding: utf-8 -*-
"""
Seisei Print Agent - Odoo Client
Handles HTTP authentication and JSON-RPC calls to Odoo

Developed by Seisei
"""

import logging
import requests
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OdooSession:
    """Odoo session information"""
    session_id: str
    uid: int
    username: str
    database: str
    is_authenticated: bool = False


class OdooClient:
    """Odoo HTTP client for authentication and RPC calls"""

    def __init__(self, server_url: str, database: str):
        self.server_url = server_url.rstrip('/')
        self.database = database
        self.session: Optional[OdooSession] = None
        self._session = requests.Session()
        self._session.headers.update({
            'Content-Type': 'application/json',
        })

    def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate with Odoo server

        Returns:
            bool: True if authentication successful
        """
        url = f"{self.server_url}/web/session/authenticate"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "db": self.database,
                "login": username,
                "password": password,
            },
            "id": 1,
        }

        try:
            response = self._session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()

            if 'error' in result:
                error_msg = result['error'].get('data', {}).get('message', 'Unknown error')
                logger.error(f"Authentication failed: {error_msg}")
                return False

            data = result.get('result', {})
            if data.get('uid'):
                self.session = OdooSession(
                    session_id=self._session.cookies.get('session_id', ''),
                    uid=data['uid'],
                    username=data.get('username', username),
                    database=self.database,
                    is_authenticated=True,
                )
                logger.info(f"Successfully authenticated as {username} (uid: {data['uid']})")
                return True
            else:
                logger.error("Authentication failed: Invalid credentials")
                return False

        except requests.exceptions.Timeout:
            logger.error("Authentication failed: Request timeout")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Authentication failed: Connection error - {e}")
            return False
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    def is_authenticated(self) -> bool:
        """Check if client is authenticated"""
        return self.session is not None and self.session.is_authenticated

    def get_session_id(self) -> Optional[str]:
        """Get current session ID"""
        return self.session.session_id if self.session else None

    def get_cookies(self) -> Dict[str, str]:
        """Get session cookies for WebSocket connection"""
        return dict(self._session.cookies)

    def call(self, model: str, method: str, args: List = None, kwargs: Dict = None) -> Any:
        """
        Call Odoo model method via JSON-RPC

        Args:
            model: Model name (e.g., 'res.partner')
            method: Method name (e.g., 'search_read')
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Method result
        """
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated")

        url = f"{self.server_url}/web/dataset/call_kw"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": model,
                "method": method,
                "args": args or [],
                "kwargs": kwargs or {},
            },
            "id": 2,
        }

        try:
            response = self._session.post(url, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()

            if 'error' in result:
                error_data = result['error'].get('data', {})
                error_msg = error_data.get('message', 'Unknown error')
                raise RuntimeError(f"RPC Error: {error_msg}")

            return result.get('result')

        except requests.exceptions.Timeout:
            raise RuntimeError("RPC call timeout")
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Connection error: {e}")

    def search_read(self, model: str, domain: List = None, fields: List = None,
                    limit: int = None, offset: int = 0, order: str = None) -> List[Dict]:
        """
        Search and read records

        Args:
            model: Model name
            domain: Search domain
            fields: Fields to read
            limit: Maximum records
            offset: Starting offset
            order: Sort order

        Returns:
            List of record dictionaries
        """
        kwargs = {
            'domain': domain or [],
            'fields': fields or [],
            'offset': offset,
        }
        if limit:
            kwargs['limit'] = limit
        if order:
            kwargs['order'] = order

        return self.call(model, 'search_read', kwargs=kwargs)

    def create(self, model: str, values: Dict) -> int:
        """Create a new record"""
        return self.call(model, 'create', args=[values])

    def write(self, model: str, ids: List[int], values: Dict) -> bool:
        """Update records"""
        return self.call(model, 'write', args=[ids, values])

    def unlink(self, model: str, ids: List[int]) -> bool:
        """Delete records"""
        return self.call(model, 'unlink', args=[ids])

    def check_session(self) -> bool:
        """Check if session is still valid"""
        if not self.session:
            return False

        url = f"{self.server_url}/web/session/get_session_info"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {},
            "id": 3,
        }

        try:
            response = self._session.post(url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()

            if 'error' in result:
                return False

            data = result.get('result', {})
            return data.get('uid') == self.session.uid

        except Exception:
            return False

    def logout(self):
        """Logout and invalidate session"""
        if not self.session:
            return

        url = f"{self.server_url}/web/session/destroy"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {},
            "id": 4,
        }

        try:
            self._session.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.warning(f"Logout error: {e}")
        finally:
            self.session = None
            self._session.cookies.clear()
