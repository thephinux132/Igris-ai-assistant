#!/bin/bash
set -e

# Igris Docker Entrypoint

echo "======================================"
echo "  Igris AI Assistant - Docker"
echo "======================================"
echo "Environment: ${IGRIS_ENV:-development}"
echo "Log Level: ${IGRIS_LOG_LEVEL:-INFO}"

# Create config from example if not exists
if [ ! -f "$IGRIS_CONFIG_DIR/settings.yaml" ]; then
    echo "Creating default configuration..."
    cp "$IGRIS_CONFIG_DIR/settings.example.yaml" "$IGRIS_CONFIG_DIR/settings.yaml" 2>/dev/null || true
fi

# Generate API key if not exists
if [ ! -f "$IGRIS_CONFIG_DIR/.api_keys" ]; then
    echo "Generating initial API key..."
    python -c "
from core.api_auth import APIKeyManager
manager = APIKeyManager()
key = manager.generate_key('docker-admin', ['read', 'execute', 'admin'])
print(f'Admin API Key: {key}')
print('Store this key securely!')
" > /app/data/initial_api_key.txt
    cat /app/data/initial_api_key.txt
fi

# Handle different run modes
case "$1" in
    api)
        echo "Starting API server..."
        exec python -m core.api_server --host 0.0.0.0 --port 8420
        ;;

    cli)
        echo "Starting CLI..."
        exec python -m cli.igris_cli "${@:2}"
        ;;

    shell)
        echo "Starting shell..."
        exec /bin/bash
        ;;

    test)
        echo "Running tests..."
        exec python -m pytest tests/ -v
        ;;

    *)
        # Run any custom command
        exec "$@"
        ;;
esac
