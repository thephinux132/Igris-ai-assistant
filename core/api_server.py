#!/usr/bin/env python3
"""
Remote Management API Server for Igris
Provides secure REST API for remote control.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import ssl

logger = logging.getLogger(__name__)

# Optional dependencies
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from core.api_auth import APIKeyManager, RateLimiter

@dataclass
class APIResponse:
    status: int
    data: Any
    error: Optional[str] = None

    def to_json(self) -> str:
        response = {"status": self.status}
        if self.error:
            response["error"] = self.error
        else:
            response["data"] = self.data
        return json.dumps(response)

class IgrisAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Igris API."""

    # Class-level references (set by server)
    key_manager: APIKeyManager = None
    rate_limiter: RateLimiter = None
    config: dict = {}

    def log_message(self, format, *args):
        """Custom logging."""
        logger.info(f"{self.address_string()} - {format % args}")

    def send_json(self, response: APIResponse):
        """Send JSON response."""
        self.send_response(response.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(response.to_json().encode())

    def authenticate(self) -> Optional[Dict]:
        """Authenticate request via API key."""
        if not self.config.get("security", {}).get("require_api_key", True):
            return {"permissions": ["read", "execute"]}

        header_name = self.config.get("security", {}).get("api_key_header", "X-Igris-API-Key")
        api_key = self.headers.get(header_name)

        if not api_key:
            return None

        key = self.key_manager.validate_key(api_key)
        if not key:
            return None

        return {"key_id": key.key_id, "permissions": key.permissions}

    def check_rate_limit(self) -> tuple:
        """Check rate limit for client."""
        client_ip = self.client_address[0]
        return self.rate_limiter.allow(client_ip)

    def do_GET(self):
        """Handle GET requests."""
        # Rate limiting
        allowed, retry_after = self.check_rate_limit()
        if not allowed:
            self.send_json(APIResponse(
                status=429,
                data=None,
                error=f"Rate limit exceeded. Retry after {retry_after}s"
            ))
            return

        # Authentication
        auth = self.authenticate()
        if auth is None:
            self.send_json(APIResponse(
                status=401,
                data=None,
                error="Invalid or missing API key"
            ))
            return

        # Parse URL
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # Route request
        if path == "/api/v1/status":
            self.handle_status(auth)
        elif path == "/api/v1/health":
            self.handle_health()
        elif path == "/api/v1/suggestions":
            self.handle_suggestions(auth)
        elif path == "/api/v1/plugins":
            self.handle_list_plugins(auth)
        elif path == "/api/v1/keys":
            self.handle_list_keys(auth)
        else:
            self.send_json(APIResponse(
                status=404,
                data=None,
                error="Endpoint not found"
            ))

    def do_POST(self):
        """Handle POST requests."""
        # Rate limiting
        allowed, retry_after = self.check_rate_limit()
        if not allowed:
            self.send_json(APIResponse(
                status=429,
                data=None,
                error=f"Rate limit exceeded. Retry after {retry_after}s"
            ))
            return

        # Authentication
        auth = self.authenticate()
        if auth is None:
            self.send_json(APIResponse(
                status=401,
                data=None,
                error="Invalid or missing API key"
            ))
            return

        # Parse body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_json(APIResponse(
                status=400,
                data=None,
                error="Invalid JSON body"
            ))
            return

        # Parse URL
        parsed = urlparse(self.path)
        path = parsed.path

        # Route request
        if path == "/api/v1/execute":
            self.handle_execute(auth, data)
        elif path == "/api/v1/keys/generate":
            self.handle_generate_key(auth, data)
        elif path == "/api/v1/keys/revoke":
            self.handle_revoke_key(auth, data)
        else:
            self.send_json(APIResponse(
                status=404,
                data=None,
                error="Endpoint not found"
            ))

    # === Endpoint Handlers ===

    def handle_health(self):
        """Health check endpoint (no auth required)."""
        self.send_json(APIResponse(
            status=200,
            data={"status": "healthy", "version": "2.0.0"}
        ))

    def handle_status(self, auth: dict):
        """Get system status."""
        if "read" not in auth.get("permissions", []):
            self.send_json(APIResponse(status=403, data=None, error="Permission denied"))
            return

        import platform
        import psutil

        status = {
            "platform": platform.system(),
            "hostname": platform.node(),
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
        }

        self.send_json(APIResponse(status=200, data=status))

    def handle_suggestions(self, auth: dict):
        """Get predictive suggestions."""
        if "read" not in auth.get("permissions", []):
            self.send_json(APIResponse(status=403, data=None, error="Permission denied"))
            return

        try:
            from core.predictive_engine import get_engine
            engine = get_engine()
            suggestions = engine.get_suggestions(limit=5)

            data = [
                {
                    "action": s.action,
                    "target": s.target,
                    "confidence": s.confidence,
                    "reason": s.reason
                }
                for s in suggestions
            ]

            self.send_json(APIResponse(status=200, data=data))
        except ImportError:
            self.send_json(APIResponse(
                status=503,
                data=None,
                error="Predictive engine not available"
            ))

    def handle_list_plugins(self, auth: dict):
        """List available plugins."""
        if "read" not in auth.get("permissions", []):
            self.send_json(APIResponse(status=403, data=None, error="Permission denied"))
            return

        try:
            from core.secure_plugin_loader import SecurePluginLoader
            loader = SecurePluginLoader()
            plugins = loader.list_plugins()

            self.send_json(APIResponse(status=200, data=plugins))
        except ImportError:
            self.send_json(APIResponse(
                status=503,
                data=None,
                error="Plugin loader not available"
            ))

    def handle_execute(self, auth: dict, data: dict):
        """Execute a command (with approval workflow)."""
        if "execute" not in auth.get("permissions", []):
            self.send_json(APIResponse(status=403, data=None, error="Permission denied"))
            return

        command = data.get("command")
        if not command:
            self.send_json(APIResponse(
                status=400,
                data=None,
                error="Missing 'command' field"
            ))
            return

        # Validate input
        try:
            from core.input_validation import InputValidator
            validator = InputValidator(strict_mode=True)
            is_valid, error = validator.validate_user_input(command)
            if not is_valid:
                self.send_json(APIResponse(
                    status=400,
                    data=None,
                    error=f"Validation failed: {error}"
                ))
                return
        except ImportError:
            pass

        # Check approval workflow
        try:
            from core.approval_workflow import ApprovalWorkflow, ApprovalLevel
            workflow = ApprovalWorkflow()
            level, message = workflow.check_command(command)

            if level in (ApprovalLevel.HIGH, ApprovalLevel.CRITICAL):
                # Remote execution of dangerous commands not allowed
                self.send_json(APIResponse(
                    status=403,
                    data=None,
                    error=f"Command requires local approval: {message}"
                ))
                return
        except ImportError:
            pass

        # Execute command
        try:
            from core.secure_execution import safe_run_command
            import shlex

            cmd_parts = shlex.split(command)
            result = safe_run_command(cmd_parts, timeout=30)

            self.send_json(APIResponse(
                status=200,
                data={
                    "returncode": result.returncode,
                    "stdout": result.stdout[:1000],  # Limit output
                    "stderr": result.stderr[:1000]
                }
            ))
        except Exception as e:
            self.send_json(APIResponse(
                status=500,
                data=None,
                error=str(e)
            ))

    def handle_list_keys(self, auth: dict):
        """List API keys (admin only)."""
        if "admin" not in auth.get("permissions", []):
            self.send_json(APIResponse(status=403, data=None, error="Admin permission required"))
            return

        keys = self.key_manager.list_keys()
        self.send_json(APIResponse(status=200, data=keys))

    def handle_generate_key(self, auth: dict, data: dict):
        """Generate new API key (admin only)."""
        if "admin" not in auth.get("permissions", []):
            self.send_json(APIResponse(status=403, data=None, error="Admin permission required"))
            return

        name = data.get("name", "unnamed")
        permissions = data.get("permissions", ["read"])

        raw_key = self.key_manager.generate_key(name, permissions)

        self.send_json(APIResponse(
            status=201,
            data={
                "api_key": raw_key,
                "message": "Store this key securely - it won't be shown again"
            }
        ))

    def handle_revoke_key(self, auth: dict, data: dict):
        """Revoke API key (admin only)."""
        if "admin" not in auth.get("permissions", []):
            self.send_json(APIResponse(status=403, data=None, error="Admin permission required"))
            return

        key_id = data.get("key_id")
        if not key_id:
            self.send_json(APIResponse(status=400, data=None, error="Missing key_id"))
            return

        if self.key_manager.revoke_key(key_id):
            self.send_json(APIResponse(status=200, data={"revoked": key_id}))
        else:
            self.send_json(APIResponse(status=404, data=None, error="Key not found"))

class IgrisAPIServer:
    """API server manager."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).parent.parent / "config" / "api_config.yaml"
        self.config = self._load_config()
        self.key_manager = APIKeyManager()
        self.rate_limiter = RateLimiter(
            rate=self.config.get("security", {}).get("rate_limit", 60),
            burst=self.config.get("security", {}).get("burst_limit", 10)
        )
        self.server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def _load_config(self) -> dict:
        """Load server configuration."""
        if YAML_AVAILABLE and self.config_path.exists():
            try:
                return yaml.safe_load(self.config_path.read_text())
            except Exception as e:
                logger.error(f"Failed to load API config: {e}")

        return {
            "server": {"host": "127.0.0.1", "port": 8420},
            "security": {"require_api_key": True, "rate_limit": 60}
        }

    def start(self, blocking: bool = True):
        """Start the API server."""
        host = self.config.get("server", {}).get("host", "127.0.0.1")
        port = self.config.get("server", {}).get("port", 8420)

        # Configure handler class
        IgrisAPIHandler.key_manager = self.key_manager
        IgrisAPIHandler.rate_limiter = self.rate_limiter
        IgrisAPIHandler.config = self.config

        self.server = HTTPServer((host, port), IgrisAPIHandler)

        # TLS setup
        if self.config.get("security", {}).get("tls_enabled", False):
            cert = self.config["security"]["tls_cert"]
            key = self.config["security"]["tls_key"]
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            self.server.socket = context.wrap_socket(
                self.server.socket,
                server_side=True
            )
            logger.info("TLS enabled")

        logger.info(f"Starting API server on {host}:{port}")

        if blocking:
            self.server.serve_forever()
        else:
            self._thread = threading.Thread(
                target=self.server.serve_forever,
                daemon=True
            )
            self._thread.start()

    def stop(self):
        """Stop the API server."""
        if self.server:
            self.server.shutdown()
            logger.info("API server stopped")

    def generate_admin_key(self) -> str:
        """Generate initial admin API key."""
        return self.key_manager.generate_key(
            name="admin",
            permissions=["read", "execute", "admin"]
        )


# CLI entry point
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Igris API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8420, help="Bind port")
    parser.add_argument("--generate-key", action="store_true", help="Generate admin API key")
    args = parser.parse_args()

    server = IgrisAPIServer()

    if args.generate_key:
        key = server.generate_admin_key()
        print(f"\nAdmin API Key (store securely):\n{key}\n")
        return

    print(f"Starting Igris API Server on {args.host}:{args.port}")
    print("Press Ctrl+C to stop")

    try:
        server.start(blocking=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop()


if __name__ == "__main__":
    main()
