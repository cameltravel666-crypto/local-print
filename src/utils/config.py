# -*- coding: utf-8 -*-
"""
Seisei Print Agent - Configuration Manager
Handles loading, saving, and encrypting configuration data

Developed by Seisei
"""

import os
import json
import uuid
import base64
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


def get_app_data_dir() -> Path:
    """Get application data directory based on OS"""
    if os.name == 'nt':  # Windows
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    elif os.name == 'posix':
        if 'darwin' in os.uname().sysname.lower():  # macOS
            base = Path.home() / 'Library' / 'Application Support'
        else:  # Linux
            base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    else:
        base = Path.home()

    app_dir = base / 'LocalPrintAgent'
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


@dataclass
class ServerConfig:
    """Server configuration"""
    server_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    server_name: str = ""
    server_url: str = "http://localhost"
    http_port: int = 8069
    websocket_port: int = 8072
    database: str = "odoo"
    username: str = "admin"
    password: str = ""  # Will be encrypted
    auto_connect: bool = True
    enabled: bool = True

    def get_http_url(self) -> str:
        """Get full HTTP URL"""
        url = self.server_url.rstrip('/')
        # For HTTPS, always use standard port 443 (reverse proxy handles routing)
        # For HTTP (local dev), use the configured http_port
        if url.startswith('https://'):
            return url
        return f"{url}:{self.http_port}"

    def get_websocket_url(self) -> str:
        """Get full WebSocket URL"""
        url = self.server_url.rstrip('/')
        base = url.replace('http://', 'ws://').replace('https://', 'wss://')
        # For HTTPS, always use standard port 443 (reverse proxy routes to 8072)
        # For HTTP (local dev), use the configured websocket_port
        if url.startswith('https://'):
            return f"{base}/websocket"
        return f"{base}:{self.websocket_port}/websocket"


@dataclass
class PrinterConfig:
    """Printer configuration"""
    default_printer: str = ""
    auto_print: bool = False
    print_copies: int = 1
    duplex_printing: bool = False


@dataclass
class ApplicationConfig:
    """Application configuration"""
    window_width: int = 960
    window_height: int = 600
    window_x: int = 100
    window_y: int = 100
    theme: str = "default"
    language: str = "zh_CN"


@dataclass
class SettingsConfig:
    """General settings"""
    machine_name: str = ""
    machine_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    station_tag: str = ""
    scan_interval: int = 30
    cache_time: int = 5
    max_log_lines: int = 1000
    include_offline: bool = False
    auto_start: bool = False
    minimize_tray: bool = True
    save_logs: bool = True
    log_level: str = "INFO"


class ConfigManager:
    """Configuration manager with encryption support"""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or get_app_data_dir()
        self.config_file = self.config_dir / "config.json"
        self.servers_file = self.config_dir / "servers.json"
        self.key_file = self.config_dir / ".key"

        self._fernet: Optional[Fernet] = None
        self._init_encryption()

        # Configuration objects
        self.printer = PrinterConfig()
        self.application = ApplicationConfig()
        self.settings = SettingsConfig()
        self.servers: Dict[str, ServerConfig] = {}

        # Load existing configuration
        self.load()

    def _init_encryption(self):
        """Initialize encryption key"""
        if self.key_file.exists():
            key = self.key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            self.key_file.write_bytes(key)
            # Set restrictive permissions on key file
            if os.name != 'nt':
                os.chmod(self.key_file, 0o600)

        self._fernet = Fernet(key)

    def encrypt(self, data: str) -> str:
        """Encrypt a string"""
        if not data:
            return ""
        encrypted = self._fernet.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()

    def decrypt(self, data: str) -> str:
        """Decrypt a string"""
        if not data:
            return ""
        try:
            encrypted = base64.b64decode(data.encode())
            return self._fernet.decrypt(encrypted).decode()
        except Exception as e:
            logger.warning(f"Failed to decrypt data: {e}")
            return ""

    def load(self):
        """Load configuration from files"""
        # Load main config
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if 'printer' in data:
                    self.printer = PrinterConfig(**data['printer'])
                if 'application' in data:
                    self.application = ApplicationConfig(**data['application'])
                if 'settings' in data:
                    self.settings = SettingsConfig(**data['settings'])

            except Exception as e:
                logger.error(f"Failed to load config: {e}")

        # Load servers config
        if self.servers_file.exists():
            try:
                with open(self.servers_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for server_id, server_data in data.get('servers', {}).items():
                    # Decrypt password
                    if server_data.get('password'):
                        server_data['password'] = self.decrypt(server_data['password'])
                    self.servers[server_id] = ServerConfig(**server_data)

            except Exception as e:
                logger.error(f"Failed to load servers config: {e}")

    def save(self):
        """Save configuration to files"""
        # Save main config
        try:
            data = {
                'printer': asdict(self.printer),
                'application': asdict(self.application),
                'settings': asdict(self.settings),
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save config: {e}")

        # Save servers config
        try:
            servers_data = {}
            for server_id, server in self.servers.items():
                server_dict = asdict(server)
                # Encrypt password
                if server_dict.get('password'):
                    server_dict['password'] = self.encrypt(server_dict['password'])
                servers_data[server_id] = server_dict

            with open(self.servers_file, 'w', encoding='utf-8') as f:
                json.dump({'servers': servers_data}, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save servers config: {e}")

    def add_server(self, server: ServerConfig) -> str:
        """Add a new server configuration"""
        self.servers[server.server_id] = server
        self.save()
        return server.server_id

    def remove_server(self, server_id: str):
        """Remove a server configuration"""
        if server_id in self.servers:
            del self.servers[server_id]
            self.save()

    def get_server(self, server_id: str) -> Optional[ServerConfig]:
        """Get a server configuration by ID"""
        return self.servers.get(server_id)

    def get_enabled_servers(self) -> Dict[str, ServerConfig]:
        """Get all enabled servers"""
        return {k: v for k, v in self.servers.items() if v.enabled}

    def get_auto_connect_servers(self) -> Dict[str, ServerConfig]:
        """Get all servers with auto_connect enabled"""
        return {k: v for k, v in self.servers.items() if v.enabled and v.auto_connect}


# Global configuration instance
_config: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get global configuration manager instance"""
    global _config
    if _config is None:
        _config = ConfigManager()
    return _config
