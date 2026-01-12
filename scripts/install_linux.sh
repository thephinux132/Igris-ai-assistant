#!/bin/bash
# Igris Linux Installation Script

set -e

INSTALL_DIR="/opt/igris"
CONFIG_DIR="$HOME/.config/igris"
SERVICE_USER="$USER"

echo "======================================"
echo "  Igris AI Assistant - Linux Install"
echo "======================================"

# Check if running as root for system install
if [ "$EUID" -eq 0 ]; then
    SYSTEM_INSTALL=true
    echo "Running as root - system-wide installation"
else
    SYSTEM_INSTALL=false
    INSTALL_DIR="$HOME/.local/share/igris"
    echo "Running as user - user installation"
fi

# Check Python version
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v $cmd &> /dev/null; then
        version=$($cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$(echo $version | cut -d. -f1)
        minor=$(echo $version | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON_CMD=$cmd
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "Error: Python 3.10+ required"
    exit 1
fi
echo "Using Python: $PYTHON_CMD ($($PYTHON_CMD --version))"

# Create directories
echo "Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/data"

# Copy files
echo "Copying files..."
cp -r . "$INSTALL_DIR/"

# Create virtual environment
echo "Creating virtual environment..."
$PYTHON_CMD -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r "$INSTALL_DIR/config/requirements.txt"

# Install optional dependencies
echo "Installing optional dependencies..."
pip install secretstorage keyring || echo "Warning: Secret storage deps failed"
pip install SpeechRecognition pyaudio || echo "Warning: Voice deps failed"

# Create config if not exists
if [ ! -f "$CONFIG_DIR/settings.yaml" ]; then
    cp "$INSTALL_DIR/config/settings.example.yaml" "$CONFIG_DIR/settings.yaml"
    echo "Created config at $CONFIG_DIR/settings.yaml"
fi

# Install systemd service
echo "Installing systemd service..."
if [ "$SYSTEM_INSTALL" = true ]; then
    # System service
    cat > /etc/systemd/system/igris.service << EOF
[Unit]
Description=Igris AI Assistant
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python -m core.api_server
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    echo "System service installed"
else
    # User service
    mkdir -p "$HOME/.config/systemd/user"
    cat > "$HOME/.config/systemd/user/igris.service" << EOF
[Unit]
Description=Igris AI Assistant

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python -m core.api_server
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    echo "User service installed"
fi

# Create CLI wrapper
echo "Creating CLI wrapper..."
WRAPPER_PATH="$HOME/.local/bin/igris"
mkdir -p "$HOME/.local/bin"
cat > "$WRAPPER_PATH" << EOF
#!/bin/bash
source "$INSTALL_DIR/venv/bin/activate"
python "$INSTALL_DIR/cli/igris_cli.py" "\$ @"
EOF
chmod +x "$WRAPPER_PATH"

echo ""
echo "======================================"
echo "  Installation Complete!"
echo "======================================"
echo ""
echo "Commands:"
echo "  igris              - Run Igris CLI"
echo "  igris --help       - Show help"
echo ""
if [ "$SYSTEM_INSTALL" = true ]; then
    echo "  sudo systemctl start igris    - Start service"
    echo "  sudo systemctl enable igris   - Enable on boot"
    echo "  sudo systemctl status igris   - Check status"
else
    echo "  systemctl --user start igris  - Start service"
    echo "  systemctl --user enable igris - Enable on boot"
    echo "  systemctl --user status igris - Check status"
fi
echo ""
echo "Config: $CONFIG_DIR/settings.yaml"
echo "Logs:   $INSTALL_DIR/logs/"
