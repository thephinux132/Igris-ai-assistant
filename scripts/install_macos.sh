#!/bin/bash
# Igris macOS Installation Script

set -e

INSTALL_DIR="/usr/local/opt/igris"
CONFIG_DIR="$HOME/.config/igris"
LOG_DIR="/usr/local/var/log/igris"

echo "======================================"
echo "  Igris AI Assistant - macOS Install"
echo "======================================"

# Check for Homebrew Python
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    version=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "Using Python: $PYTHON_CMD ($version)"
else
    echo "Error: Python 3 required. Install with: brew install python"
    exit 1
fi

# Create directories
echo "Creating directories..."
sudo mkdir -p "$INSTALL_DIR"
sudo chown $USER "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
sudo mkdir -p "$LOG_DIR"
sudo chown $USER "$LOG_DIR"

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

# Install macOS-specific dependencies
echo "Installing macOS dependencies..."
pip install keyring pyobjc-framework-LocalAuthentication || echo "Warning: Some deps failed"

# Create config
if [ ! -f "$CONFIG_DIR/settings.yaml" ]; then
    cp "$INSTALL_DIR/config/settings.example.yaml" "$CONFIG_DIR/settings.yaml"
fi

# Install launchd service
echo "Installing launchd service..."
PLIST_PATH="$HOME/Library/LaunchAgents/com.igris.assistant.plist"
mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.igris.assistant</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/venv/bin/python</string>
        <string>-m</string>
        <string>core.api_server</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>
    <key>RunAtLoad</key>
    <false/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/stderr.log</string>
</dict>
</plist>
EOF

# Create CLI wrapper
echo "Creating CLI wrapper..."
sudo mkdir -p /usr/local/bin
cat > /tmp/igris << EOF
#!/bin/bash
source "$INSTALL_DIR/venv/bin/activate"
python "$INSTALL_DIR/cli/igris_cli.py" "\$ @"
EOF
sudo mv /tmp/igris /usr/local/bin/igris
sudo chmod +x /usr/local/bin/igris

echo ""
echo "======================================"
echo "  Installation Complete!"
echo "======================================"
echo ""
echo "Commands:"
echo "  igris                    - Run Igris CLI"
echo "  igris --help             - Show help"
echo ""
echo "  launchctl load ~/Library/LaunchAgents/com.igris.assistant.plist"
echo "  launchctl start com.igris.assistant"
echo "  launchctl stop com.igris.assistant"
echo ""
echo "Config: $CONFIG_DIR/settings.yaml"
echo "Logs:   $LOG_DIR/"
