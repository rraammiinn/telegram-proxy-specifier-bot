# MTProxy Telegram Bot

A Telegram bot that automatically provides MTProxy access to channel members and revokes access when they leave.

## Features

- 🔐 Automatic proxy generation for channel members
- 🚫 Automatic proxy revocation when users leave
- 💾 SQLite database for user management
- 🔒 SSH-based MTProxy server management
- 📱 Easy-to-use Telegram interface

## Installation

Run this one-line command to install the bot:

```bash
[ ! -d "telegram-proxy-specifier-bot-main" ] && curl -L https://github.com/rraammiinn/telegram-proxy-specifier-bot/archive/refs/heads/main.tar.gz | tar -xz; sudo bash telegram-proxy-specifier-bot-main/setup.sh
```

## Update

To update the bot to the latest version while preserving your configuration and database:

```bash
sudo ./update.sh
```

The update script will:
- ✅ Backup your `.env` configuration and `bot_data.db` database
- ✅ Download and install the latest bot files
- ✅ Update Python dependencies
- ✅ Preserve your settings and user data
- ✅ Restart the bot service automatically

**Note:** Your bot token, channel settings, and user database will be preserved during the update.
