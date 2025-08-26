#!/bin/bash

# MTProxy Telegram Bot Update Script
# Updates all files except .env and bot_data.db
# Run with: sudo ./update.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR/backup_$(date +%Y%m%d_%H%M%S)"
TEMP_DIR="/tmp/telegram-proxy-bot-update-$$"

echo "🔄 MTProxy Telegram Bot Update"
echo "=============================="

if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root: sudo ./update.sh"
    exit 1
fi

ORIGINAL_USER=${SUDO_USER:-$USER}

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

# Check if bot is currently running
if systemctl is-active --quiet mtproxy-bot 2>/dev/null; then
    BOT_WAS_RUNNING=true
    echo "   ✅ Bot service is running - will restart after update"
else
    BOT_WAS_RUNNING=false
    echo "   ℹ️  Bot service is not running"
fi

echo "   Pre-flight checks completed"

# Step 1: Create backup of important files
echo "💾 Creating backup..."
mkdir -p "$BACKUP_DIR"

# Backup .env and database if they exist
if [ -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env" "$BACKUP_DIR/"
    echo "   ✅ Backed up .env"
fi

if [ -f "$SCRIPT_DIR/bot_data.db" ]; then
    cp "$SCRIPT_DIR/bot_data.db" "$BACKUP_DIR/"
    echo "   ✅ Backed up bot_data.db"
fi

# Backup any custom files user might have
for file in "$SCRIPT_DIR"/*.log "$SCRIPT_DIR"/*.txt; do
    if [ -f "$file" ]; then
        cp "$file" "$BACKUP_DIR/" 2>/dev/null || true
    fi
done

echo "   ✅ Backup created at: $BACKUP_DIR"

# Step 2: Stop bot service if running
if [ "$BOT_WAS_RUNNING" = true ]; then
    echo "⏹️  Stopping bot service..."
    systemctl stop mtproxy-bot
    echo "   ✅ Bot service stopped"
fi

# Step 3: Download latest version
echo "📥 Downloading latest version..."
mkdir -p "$TEMP_DIR"
cd "$TEMP_DIR"

if ! curl -L https://github.com/rraammiinn/telegram-proxy-specifier-bot/archive/refs/heads/main.tar.gz | tar -xz; then
    echo "   ❌ Download failed"
    rm -rf "$TEMP_DIR"
    exit 1
fi

if [ ! -d "$TEMP_DIR/telegram-proxy-specifier-bot-main" ]; then
    echo "   ❌ Downloaded files not found"
    rm -rf "$TEMP_DIR"
    exit 1
fi

echo "   ✅ Latest version downloaded"

# Step 4: Update files (excluding .env and bot_data.db)
echo "🔄 Updating files..."
cd "$TEMP_DIR/telegram-proxy-specifier-bot-main"

# List of files to update
UPDATE_FILES=(
    "bot.py"
    "config.py" 
    "database.py"
    "languages.py"
    "setup.sh"
    "update.sh"
    "requirements.txt"
    ".env.example"
    "README.md"
)

# Update each file
for file in "${UPDATE_FILES[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$SCRIPT_DIR/"
        chown $ORIGINAL_USER:$ORIGINAL_USER "$SCRIPT_DIR/$file"
        echo "   ✅ Updated $file"
    else
        echo "   ⚠️  File not found in update: $file"
    fi
done

# Make scripts executable
chmod +x "$SCRIPT_DIR/setup.sh" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/update.sh" 2>/dev/null || true

echo "   ✅ Files updated successfully"

# Step 5: Update Python dependencies
echo "🐍 Updating Python dependencies..."
VENV_DIR="$SCRIPT_DIR/telegram-bot-env"

if [ -d "$VENV_DIR" ]; then
    echo "   Updating packages in existing virtual environment..."
    if sudo -u $ORIGINAL_USER "$VENV_DIR/bin/pip" install --upgrade pip > /dev/null 2>&1; then
        echo "   ✅ pip upgraded"
    else
        echo "   ⚠️  pip upgrade failed, continuing..."
    fi
    
    if sudo -u $ORIGINAL_USER "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" --upgrade > /dev/null 2>&1; then
        echo "   ✅ Python packages updated"
    else
        echo "   ⚠️  Package update failed, may need manual intervention"
    fi
else
    echo "   ⚠️  Virtual environment not found - run setup.sh to recreate"
fi

# Step 6: Restore preserved files
echo "🔄 Restoring preserved files..."

# Restore .env if it was backed up
if [ -f "$BACKUP_DIR/.env" ]; then
    cp "$BACKUP_DIR/.env" "$SCRIPT_DIR/"
    chown $ORIGINAL_USER:$ORIGINAL_USER "$SCRIPT_DIR/.env"
    echo "   ✅ Restored .env configuration"
fi

# Restore database if it was backed up
if [ -f "$BACKUP_DIR/bot_data.db" ]; then
    cp "$BACKUP_DIR/bot_data.db" "$SCRIPT_DIR/"
    chown $ORIGINAL_USER:$ORIGINAL_USER "$SCRIPT_DIR/bot_data.db"
    echo "   ✅ Restored bot_data.db"
fi

# Step 7: Update systemd service if needed
echo "🔧 Updating systemd service..."
if [ -f "/etc/systemd/system/mtproxy-bot.service" ]; then
    # Recreate service file with current paths
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
    
    systemctl daemon-reload
    echo "   ✅ Systemd service updated"
else
    echo "   ⚠️  Systemd service not found - run setup.sh to create"
fi

# Step 8: Start bot service if it was running before
if [ "$BOT_WAS_RUNNING" = true ]; then
    echo "▶️  Starting bot service..."
    systemctl start mtproxy-bot
    sleep 3
    
    if systemctl is-active --quiet mtproxy-bot; then
        echo "   ✅ Bot service started successfully"
    else
        echo "   ❌ Bot service failed to start"
        echo "   Check logs: journalctl -u mtproxy-bot -f"
    fi
fi

# Step 9: Cleanup
echo "🧹 Cleaning up..."
rm -rf "$TEMP_DIR"
echo "   ✅ Temporary files cleaned"

# Step 10: Show update summary
echo ""
echo "🎉 Update completed successfully!"
echo "================================"
echo ""
echo "✅ Files updated: ${#UPDATE_FILES[@]} files"
echo "✅ Configuration preserved: .env"
echo "✅ Database preserved: bot_data.db"
echo "✅ Backup created: $BACKUP_DIR"

if [ "$BOT_WAS_RUNNING" = true ]; then
    if systemctl is-active --quiet mtproxy-bot; then
        echo "✅ Bot service: Running"
    else
        echo "❌ Bot service: Failed to start"
    fi
else
    echo "ℹ️  Bot service: Not started (was not running before update)"
fi

echo ""
echo "🔧 Management Commands:"
echo "   systemctl status mtproxy-bot     # Check status"
echo "   journalctl -u mtproxy-bot -f     # View logs"
echo "   systemctl restart mtproxy-bot    # Restart"
echo "   nano .env                        # Edit config"
echo ""
echo "📁 Backup location: $BACKUP_DIR"
echo "   (Remove this directory when you're sure the update works correctly)"