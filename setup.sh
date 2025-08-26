#!/bin/bash

# MTProxy Telegram Bot Setup
# Supports: Ubuntu, Debian, CentOS, RHEL, Fedora, Amazon Linux
# Run with: sudo ./setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/telegram-bot-env"

echo "🚀 MTProxy Telegram Bot Setup"
echo "============================="

if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root: sudo ./setup.sh"
    exit 1
fi

ORIGINAL_USER=${SUDO_USER:-$USER}

# Function to extract port from MTProxy service file
extract_mtproxy_port() {
    if [ -f "/etc/systemd/system/MTProxy.service" ]; then
        local port=$(grep "ExecStart=" /etc/systemd/system/MTProxy.service | sed -n 's/.*-H \([0-9]*\).*/\1/p')
        if [[ "$port" =~ ^[0-9]+$ ]] && [ "$port" -ge 1 ] && [ "$port" -le 65535 ]; then
            echo "$port"
        fi
    fi
}

# Pre-flight checks
echo "🔍 Running pre-flight checks..."

if [ -z "$ORIGINAL_USER" ] || [ "$ORIGINAL_USER" = "root" ]; then
    echo "   ⚠️  Warning: Unable to determine original user, using root"
    ORIGINAL_USER="root"
else
    echo "   ✅ Original user: $ORIGINAL_USER"
fi

# Check internet connectivity
if ! ping -c 1 google.com > /dev/null 2>&1 && ! ping -c 1 8.8.8.8 > /dev/null 2>&1; then
    echo "   ❌ No internet connectivity detected"
    exit 1
else
    echo "   ✅ Internet connectivity confirmed"
fi

# Check available disk space (need at least 500MB)
AVAILABLE_SPACE=$(df . | tail -1 | awk '{print $4}')
if [ "$AVAILABLE_SPACE" -lt 512000 ]; then
    echo "   ⚠️  Warning: Low disk space ($(($AVAILABLE_SPACE/1024))MB available)"
else
    echo "   ✅ Sufficient disk space available"
fi

# Check if script directory is writable
if [ ! -w "$SCRIPT_DIR" ]; then
    echo "   ❌ Script directory is not writable"
    exit 1
else
    echo "   ✅ Script directory is writable"
fi

echo "   Pre-flight checks completed"

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
    elif [ -f /etc/debian_version ]; then
        OS=Debian
    elif [ -f /etc/redhat-release ]; then
        OS=RedHat
    else
        OS=$(uname -s)
    fi
}

# Install dependencies based on OS
install_dependencies() {
    echo "📦 Installing system dependencies..."
    echo "   Detected OS: $OS"
    
    case $OS in
        *"Ubuntu"*|*"Debian"*)
            apt update -qq > /dev/null 2>&1
            
            PACKAGES="python3 python3-pip python3-venv curl wget build-essential"
            for package in $PACKAGES; do
                if ! dpkg -l | grep -q "^ii  $package "; then
                    echo "   Installing $package..."
                    apt install -y $package > /dev/null 2>&1 || {
                        echo "   ❌ Failed to install $package"
                        exit 1
                    }
                fi
            done
            ;;
            
        *"CentOS"*|*"Red Hat"*|*"RHEL"*|*"Rocky"*|*"AlmaLinux"*)
            PKG_MGR="yum"
            command -v dnf &> /dev/null && PKG_MGR="dnf"
            
            [ "$PKG_MGR" = "yum" ] && $PKG_MGR install -y epel-release > /dev/null 2>&1 || true
            
            PACKAGES="python3 python3-pip curl wget gcc make"
            for package in $PACKAGES; do
                if ! rpm -q $package &> /dev/null; then
                    echo "   Installing $package..."
                    $PKG_MGR install -y $package > /dev/null 2>&1 || true
                fi
            done
            ;;
            
        *"Fedora"*)
            PACKAGES="python3 python3-pip curl wget gcc make python3-devel"
            for package in $PACKAGES; do
                if ! rpm -q $package &> /dev/null; then
                    echo "   Installing $package..."
                    dnf install -y $package > /dev/null 2>&1 || true
                fi
            done
            ;;
            
        *"Amazon Linux"*)
            PACKAGES="python3 python3-pip curl wget gcc make python3-devel"
            for package in $PACKAGES; do
                if ! rpm -q $package &> /dev/null; then
                    echo "   Installing $package..."
                    yum install -y $package > /dev/null 2>&1 || true
                fi
            done
            ;;
            
        *)
            echo "   ⚠️  Unsupported OS: $OS"
            if command -v apt &> /dev/null; then
                apt update && apt install -y python3 python3-pip python3-venv curl wget
            elif command -v yum &> /dev/null; then
                yum install -y python3 python3-pip curl wget
            elif command -v dnf &> /dev/null; then
                dnf install -y python3 python3-pip curl wget
            else
                echo "   ❌ No supported package manager found"
                exit 1
            fi
            ;;
    esac
    
    # Verify installations
    if ! command -v python3 &> /dev/null; then
        echo "   ❌ Python 3 installation failed"
        exit 1
    fi
    
    if ! command -v pip3 &> /dev/null && ! python3 -m pip --version &> /dev/null; then
        echo "   ❌ pip installation failed"
        exit 1
    fi
    
    echo "   ✅ All dependencies installed successfully"
}

# Step 1: Detect OS and install dependencies
detect_os
install_dependencies

# Step 2: Setup Python environment
echo "🐍 Setting up Python environment..."
cd "$SCRIPT_DIR"

# Create requirements.txt if missing
if [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
    echo "   Creating requirements.txt..."
    cat > "$SCRIPT_DIR/requirements.txt" << EOF
python-telegram-bot==20.7
paramiko==3.4.0
python-dotenv==1.0.0
EOF
fi

# Remove old virtual environment
[ -d "$VENV_DIR" ] && rm -rf "$VENV_DIR"

# Ensure proper ownership of the script directory
chown -R $ORIGINAL_USER:$ORIGINAL_USER "$SCRIPT_DIR"

# Create virtual environment
echo "   Creating virtual environment..."
if ! sudo -u $ORIGINAL_USER python3 -m venv "$VENV_DIR"; then
    echo "   ❌ Virtual environment creation failed"
    echo "   Trying alternative approach..."
    # Alternative: create as root then change ownership
    if python3 -m venv "$VENV_DIR"; then
        chown -R $ORIGINAL_USER:$ORIGINAL_USER "$VENV_DIR"
        echo "   ✅ Virtual environment created with alternative method"
    else
        echo "   ❌ Virtual environment creation failed completely"
        exit 1
    fi
fi

# Install packages
echo "   Installing Python packages..."
if ! sudo -u $ORIGINAL_USER "$VENV_DIR/bin/pip" install --upgrade pip > /dev/null 2>&1; then
    echo "   ⚠️  pip upgrade failed, continuing..."
fi

if ! sudo -u $ORIGINAL_USER "$VENV_DIR/bin/pip" install -r requirements.txt > /dev/null 2>&1; then
    echo "   ❌ Package installation failed"
    exit 1
fi

# Verify key packages
if ! sudo -u $ORIGINAL_USER "$VENV_DIR/bin/python" -c "import telegram; import paramiko; import dotenv" > /dev/null 2>&1; then
    echo "   ❌ Package verification failed"
    exit 1
fi

echo "   ✅ Python environment setup complete"

# Step 3: Setup configuration
echo "📝 Setting up configuration..."

# Create .env.example if missing
if [ ! -f "$SCRIPT_DIR/.env.example" ]; then
    cat > "$SCRIPT_DIR/.env.example" << EOF
BOT_TOKEN=your_bot_token_here
CHANNEL_ID=@your_channel_username
BOT_LANGUAGE=en
VPS_HOST=localhost
MTPROXY_PATH=/opt/MTProxy
MTPROXY_PORT=auto_detect
EOF
fi

# Create .env if missing
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    sudo -u $ORIGINAL_USER cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
fi

# Interactive bot configuration (always ask to allow changes)
echo "   Configuring bot settings..."

# Function to check if a value is empty or placeholder
is_empty_or_placeholder() {
    local value="$1"
    [[ -z "$value" || "$value" == "your_bot_token_here" || "$value" == "@your_channel_username" ]]
}

# Get current values
CURRENT_BOT_TOKEN=$(grep "^BOT_TOKEN=" "$SCRIPT_DIR/.env" 2>/dev/null | cut -d'=' -f2 | tr -d ' "'"'"'')
CURRENT_CHANNEL_ID=$(grep "^CHANNEL_ID=" "$SCRIPT_DIR/.env" 2>/dev/null | cut -d'=' -f2 | tr -d ' "'"'"'')

# Always configure BOT_TOKEN (show current if exists)
echo ""
echo "🤖 Bot Token Configuration"
echo "=========================="
if ! is_empty_or_placeholder "$CURRENT_BOT_TOKEN"; then
    echo "Current Bot Token: ${CURRENT_BOT_TOKEN:0:10}...${CURRENT_BOT_TOKEN: -10}"
    echo ""
fi
echo "Get a bot token from @BotFather on Telegram:"
echo "1. Open Telegram and search for @BotFather"
echo "2. Send /newbot command (or /mybots to manage existing bots)"
echo "3. Follow the instructions to create your bot"
echo "4. Copy the token (format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)"
echo ""

while true; do
    if ! is_empty_or_placeholder "$CURRENT_BOT_TOKEN"; then
        read -p "Enter new Bot Token (or press Enter to keep current): " BOT_TOKEN
        # If empty, keep current token
        if [[ -z "$BOT_TOKEN" ]]; then
            BOT_TOKEN="$CURRENT_BOT_TOKEN"
            echo "   ✅ Keeping current bot token"
            break
        fi
    else
        read -p "Enter your Bot Token: " BOT_TOKEN
    fi
    
    # Remove any quotes or spaces
    BOT_TOKEN=$(echo "$BOT_TOKEN" | tr -d ' "'"'"'')
    
    # Check if user wants to skip (for testing)
    if [[ "$BOT_TOKEN" == "skip" ]]; then
        echo "   ⚠️  Skipping bot token configuration"
        break
    fi
    
    # Validate bot token format (precise regex)
    if [[ "$BOT_TOKEN" =~ ^[0-9]{10}:[a-zA-Z0-9_-]{35}$ ]]; then
        # Update .env file
        if grep -q "^BOT_TOKEN=" "$SCRIPT_DIR/.env"; then
            sed -i "s/^BOT_TOKEN=.*/BOT_TOKEN=$BOT_TOKEN/" "$SCRIPT_DIR/.env"
        else
            echo "BOT_TOKEN=$BOT_TOKEN" >> "$SCRIPT_DIR/.env"
        fi
        echo "   ✅ Bot token configured"
        break
    else
        echo "   ❌ Invalid token format. Please enter a valid bot token."
        echo "   Format: 10 digits, colon, then 35 characters (letters, numbers, _, -)"
        echo "   Example: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456789"
        echo "   Or type 'skip' to configure later"
    fi
done

# Always configure CHANNEL_ID (show current if exists)
echo ""
echo "📢 Channel Configuration"
echo "======================="
if ! is_empty_or_placeholder "$CURRENT_CHANNEL_ID"; then
    echo "Current Channel: $CURRENT_CHANNEL_ID"
    echo ""
fi
echo "Specify your Telegram channel:"
echo "• Username format: @channelname (e.g., @mychannel)"
echo "• Telegram URL: https://t.me/channelname or t.me/channelname"
echo "• Private channels: -100xxxxxxxxxx (numeric ID)"
echo "• Groups: -xxxxxxxxxx (numeric ID)"
echo ""
echo "Note: The bot must be added as an admin to your channel/group"
echo ""

while true; do
    if ! is_empty_or_placeholder "$CURRENT_CHANNEL_ID"; then
        read -p "Enter new Channel ID/Username (or press Enter to keep current): " CHANNEL_ID
        # If empty, keep current channel
        if [[ -z "$CHANNEL_ID" ]]; then
            CHANNEL_ID="$CURRENT_CHANNEL_ID"
            echo "   ✅ Keeping current channel: $CHANNEL_ID"
            break
        fi
    else
        read -p "Enter your Channel ID or Username: " CHANNEL_ID
    fi
    
    # Remove any quotes or spaces
    CHANNEL_ID=$(echo "$CHANNEL_ID" | tr -d ' "'"'"'')
    
    # Check if user wants to skip (for testing)
    if [[ "$CHANNEL_ID" == "skip" ]]; then
        echo "   ⚠️  Skipping channel configuration"
        break
    fi
    
    # Extract username from Telegram URL if provided
    if [[ "$CHANNEL_ID" =~ (https?://)?(www\.)?(t\.me|telegram\.me|telegram\.dog)/([a-zA-Z0-9_]{5,32})/?$ ]]; then
        CHANNEL_ID="@${BASH_REMATCH[4]}"
        echo "   Extracted username: $CHANNEL_ID"
    fi
    
    # Validate channel ID format (precise validation)
    if [[ "$CHANNEL_ID" =~ ^@[a-zA-Z0-9_]{5,32}$ ]] || [[ "$CHANNEL_ID" =~ ^-[0-9]+$ ]]; then
        # Update .env file
        if grep -q "^CHANNEL_ID=" "$SCRIPT_DIR/.env"; then
            sed -i "s/^CHANNEL_ID=.*/CHANNEL_ID=$CHANNEL_ID/" "$SCRIPT_DIR/.env"
        else
            echo "CHANNEL_ID=$CHANNEL_ID" >> "$SCRIPT_DIR/.env"
        fi
        echo "   ✅ Channel ID configured"
        break
    else
        echo "   ❌ Invalid format. Please enter:"
        echo "   • @channelname (5-32 characters, letters, numbers, underscore)"
        echo "   • https://t.me/channelname or t.me/channelname"
        echo "   • -100xxxxxxxxxx for private channels"
        echo "   • -xxxxxxxxxx for groups"
        echo "   Or type 'skip' to configure later"
    fi
done

# Final configuration check
FINAL_BOT_TOKEN=$(grep "^BOT_TOKEN=" "$SCRIPT_DIR/.env" 2>/dev/null | cut -d'=' -f2 | tr -d ' "'"'"'')
FINAL_CHANNEL_ID=$(grep "^CHANNEL_ID=" "$SCRIPT_DIR/.env" 2>/dev/null | cut -d'=' -f2 | tr -d ' "'"'"'')

if is_empty_or_placeholder "$FINAL_BOT_TOKEN" || is_empty_or_placeholder "$FINAL_CHANNEL_ID"; then
    echo ""
    echo "❌ Configuration incomplete!"
    echo "Please ensure both BOT_TOKEN and CHANNEL_ID are properly set in .env file"
    exit 1
fi

# Always ask for language preference (show current if exists)
CURRENT_LANGUAGE=$(grep "^BOT_LANGUAGE=" "$SCRIPT_DIR/.env" 2>/dev/null | cut -d'=' -f2 | tr -d ' "'"'"'')
echo ""
echo "🌐 Language Selection"
echo "===================="
if [[ -n "$CURRENT_LANGUAGE" ]]; then
    case "$CURRENT_LANGUAGE" in
        "en") echo "Current language: English (en)" ;;
        "fa") echo "Current language: Persian/Farsi (fa)" ;;
        *) echo "Current language: $CURRENT_LANGUAGE" ;;
    esac
    echo ""
fi
echo "Choose bot language:"
echo "1) English (en)"
echo "2) Persian/Farsi (fa)"
echo ""

while true; do
    if [[ -n "$CURRENT_LANGUAGE" ]]; then
        read -p "Select language [1-2] (or press Enter to keep current): " LANG_CHOICE
        # If empty, keep current language
        if [[ -z "$LANG_CHOICE" ]]; then
            BOT_LANGUAGE="$CURRENT_LANGUAGE"
            echo "   ✅ Keeping current language: $BOT_LANGUAGE"
            break
        fi
    else
        read -p "Select language [1-2] (default: 1): " LANG_CHOICE
        LANG_CHOICE=${LANG_CHOICE:-1}
    fi
    
    case "$LANG_CHOICE" in
        1)
            BOT_LANGUAGE="en"
            break
            ;;
        2)
            BOT_LANGUAGE="fa"
            break
            ;;
        *)
            echo "   ❌ Invalid choice. Please enter 1 or 2"
            ;;
    esac
done

# Update .env file
if grep -q "^BOT_LANGUAGE=" "$SCRIPT_DIR/.env"; then
    sed -i "s/^BOT_LANGUAGE=.*/BOT_LANGUAGE=$BOT_LANGUAGE/" "$SCRIPT_DIR/.env"
else
    echo "BOT_LANGUAGE=$BOT_LANGUAGE" >> "$SCRIPT_DIR/.env"
fi

echo "   ✅ Language set to: $BOT_LANGUAGE"

echo ""
echo "   ✅ Bot configuration complete"
echo "   Bot Token: ${FINAL_BOT_TOKEN:0:10}...${FINAL_BOT_TOKEN: -10}"
echo "   Channel: $FINAL_CHANNEL_ID"
echo "   Language: $(grep "^BOT_LANGUAGE=" "$SCRIPT_DIR/.env" | cut -d'=' -f2)"

# Step 4: Check bot files
echo "🔧 Checking bot files..."
REQUIRED_FILES=("bot.py" "config.py" "database.py" "languages.py")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$SCRIPT_DIR/$file" ]; then
        echo "   ❌ Required file missing: $file"
        exit 1
    fi
done

# Set proper ownership for all files
chown -R $ORIGINAL_USER:$ORIGINAL_USER "$SCRIPT_DIR"
echo "   ✅ Bot files configured"

# Step 5: Create startup script
echo "🚀 Creating startup script..."
cat > "$SCRIPT_DIR/start_bot.sh" << EOF
#!/bin/bash
cd "$SCRIPT_DIR"
source "$VENV_DIR/bin/activate"
python bot.py
EOF

chmod +x "$SCRIPT_DIR/start_bot.sh"
chown $ORIGINAL_USER:$ORIGINAL_USER "$SCRIPT_DIR/start_bot.sh"

# Step 6: Create systemd service
echo "🔧 Creating systemd service..."
cat > /etc/systemd/system/mtproxy-bot.service << EOF
[Unit]
Description=MTProxy Telegram Bot
After=network.target MTProxy.service

[Service]
Type=simple
User=root
WorkingDirectory=$SCRIPT_DIR
ExecStart=/bin/bash $SCRIPT_DIR/start_bot.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Step 7: Check and install MTProxy if needed
echo "🔍 Checking MTProxy installation..."

if [ ! -f "/etc/systemd/system/MTProxy.service" ]; then
    echo "   ❌ MTProxy not installed - installing now..."
    echo "   This requires user interaction..."
    
    # Download MTProxy installer
    if ! curl -o MTProtoProxyOfficialInstall.sh -L https://git.io/fjo3u; then
        if ! wget -O MTProtoProxyOfficialInstall.sh https://git.io/fjo3u; then
            echo "   ❌ Download failed. Manual installation required:"
            echo "   curl -L https://git.io/fjo3u | bash"
            exit 1
        fi
    fi
    
    echo "   ⚠️  IMPORTANT: Follow the interactive prompts"
    echo "   ⚠️  Choose a port (recommended: 443 or 8080-8999)"
    echo "   Press Enter to continue..."
    read -p "   "
    
    chmod +x MTProtoProxyOfficialInstall.sh
    if ! bash MTProtoProxyOfficialInstall.sh; then
        echo "   ❌ MTProxy installation failed"
        rm -f MTProtoProxyOfficialInstall.sh
        exit 1
    fi
    
    rm -f MTProtoProxyOfficialInstall.sh
    sleep 3
    
    if [ ! -f "/etc/systemd/system/MTProxy.service" ]; then
        echo "   ❌ MTProxy installation incomplete"
        exit 1
    fi
    
    echo "   ✅ MTProxy installation completed"
    
    # Clean up old database since MTProxy has new secrets
    echo "   🧹 Cleaning up old database (MTProxy has new secrets)..."
    if [ -f "$SCRIPT_DIR/bot_data.db" ]; then
        rm -f "$SCRIPT_DIR/bot_data.db"
        echo "   ✅ Old database removed - bot will create fresh database"
    else
        echo "   ✅ No old database found"
    fi
else
    echo "   ✅ MTProxy service found"
fi

# Step 8: Configure MTProxy port
echo "🔧 Configuring MTProxy port..."

CURRENT_PORT=$(grep "^MTPROXY_PORT=" "$SCRIPT_DIR/.env" 2>/dev/null | cut -d'=' -f2 | tr -d ' ')

if [[ ! "$CURRENT_PORT" =~ ^[0-9]+$ ]] || [ "$CURRENT_PORT" -lt 1 ] || [ "$CURRENT_PORT" -gt 65535 ]; then
    DETECTED_PORT=$(extract_mtproxy_port)
    
    if [ -n "$DETECTED_PORT" ]; then
        echo "   Auto-detected MTProxy port: $DETECTED_PORT"
        if grep -q "^MTPROXY_PORT=" "$SCRIPT_DIR/.env"; then
            sed -i "s/^MTPROXY_PORT=.*/MTPROXY_PORT=$DETECTED_PORT/" "$SCRIPT_DIR/.env"
        else
            echo "MTPROXY_PORT=$DETECTED_PORT" >> "$SCRIPT_DIR/.env"
        fi
        echo "   ✅ MTPROXY_PORT set to $DETECTED_PORT"
    else
        echo "   ❌ Could not auto-detect MTProxy port"
        echo "   Please update MTPROXY_PORT in .env file manually"
        exit 1
    fi
else
    echo "   ✅ Valid MTPROXY_PORT found: $CURRENT_PORT"
fi

# Step 9: Start services
echo "🔧 Starting services..."

# Start MTProxy if not running
if ! systemctl is-active --quiet MTProxy; then
    systemctl start MTProxy
    sleep 2
fi

# Start bot service
systemctl daemon-reload
systemctl enable mtproxy-bot
systemctl stop mtproxy-bot 2>/dev/null || true
systemctl start mtproxy-bot

sleep 5

# Check status
if systemctl is-active --quiet mtproxy-bot; then
    echo ""
    echo "🎉 SUCCESS! MTProxy Telegram Bot is running!"
    echo "==========================================="
    echo ""
    echo "✅ System: $OS"
    echo "✅ Python: $(python3 --version 2>/dev/null)"
    echo "✅ Bot service: Active"
    
    if systemctl is-active --quiet MTProxy; then
        echo "✅ MTProxy service: Active"
        DETECTED_PORT=$(extract_mtproxy_port)
        [ -n "$DETECTED_PORT" ] && echo "✅ MTProxy port: $DETECTED_PORT"
    fi
    
    echo ""
    echo "📱 Next Steps:"
    echo "   1. Add bot as admin to your channel: $FINAL_CHANNEL_ID"
    echo "   2. Give bot 'Manage Chat' and 'Post Messages' permissions"
    echo "   3. Test with /start command in bot private chat"
    echo "   4. Users will get proxies when they join your channel"
    echo ""
    echo "🔧 Management Commands:"
    echo "   systemctl status mtproxy-bot     # Check status"
    echo "   journalctl -u mtproxy-bot -f     # View logs"
    echo "   systemctl restart mtproxy-bot    # Restart"
    echo "   nano .env                        # Edit config"
    
else
    echo ""
    echo "❌ Bot failed to start!"
    echo "====================="
    echo ""
    echo "🔍 Checking logs..."
    journalctl -u mtproxy-bot --no-pager -l --since "2 minutes ago"
    echo ""
    echo "🔧 Troubleshooting:"
    echo "   1. Check config: cat .env"
    echo "   2. Test manually: cd $SCRIPT_DIR && ./start_bot.sh"
    echo "   3. Check MTProxy: systemctl status MTProxy"
    echo "   4. Check permissions: ls -la $SCRIPT_DIR"
    
    exit 1
fi