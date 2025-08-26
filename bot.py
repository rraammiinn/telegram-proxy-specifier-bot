#!/usr/bin/env python3

import logging
import subprocess
import secrets
import re
import asyncio
import time
from collections import defaultdict, deque
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ChatMemberHandler, ContextTypes
from telegram.constants import ChatMemberStatus
from config import Config
from database import Database
from languages import get_text

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class WorkingMTProxyBot:
    def __init__(self):
        Config.validate()
        self.config = Config()
        self.db = Database()
        self.service_file = "/etc/systemd/system/MTProxy.service"
        self.language = self.config.BOT_LANGUAGE
        
        # Rate limiting and load management
        self.user_rate_limit = defaultdict(lambda: deque(maxlen=10))  # Track user actions
        self.mtproxy_operations = asyncio.Queue(maxsize=50)  # Queue MTProxy operations
        self.operation_lock = asyncio.Lock()  # Prevent concurrent MTProxy operations
        self.last_mtproxy_restart = 0  # Track last restart time
        self.restart_cooldown = 5  # Minimum seconds between restarts
        
        # Statistics
        self.stats = {
            'joins': 0,
            'leaves': 0,
            'proxies_created': 0,
            'proxies_removed': 0,
            'errors': 0,
            'rate_limited': 0
        }
    
    def t(self, key: str, **kwargs) -> str:
        """Get translated text"""
        return get_text(key, self.language, **kwargs)
    
    async def get_channel_chat_id(self, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Get numeric chat ID for the configured channel"""
        channel_id = self.config.CHANNEL_ID
        
        # If it's already a numeric ID, return it as int
        if channel_id.startswith('-') and channel_id[1:].isdigit():
            return int(channel_id)
            
        # If it's a username, resolve it to numeric ID
        try:
            chat = await context.bot.get_chat(channel_id)
            return chat.id
        except Exception as e:
            logger.error(f"❌ Could not resolve channel ID '{channel_id}': {e}")
            raise
    
    async def is_channel_admin(self, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
        """Check if user is admin of the channel"""
        try:
            member = await context.bot.get_chat_member(self.config.CHANNEL_ID, user_id)
            return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
        except Exception as e:
            logger.error(f"Error checking admin status for user {user_id}: {e}")
            return False
    
    def is_rate_limited(self, user_id: int) -> bool:
        """Check if user is rate limited"""
        now = time.time()
        user_actions = self.user_rate_limit[user_id]
        
        # Remove old actions (older than 60 seconds)
        while user_actions and now - user_actions[0] > 60:
            user_actions.popleft()
        
        # Check if user has too many recent actions
        if len(user_actions) >= 5:  # Max 5 actions per minute
            self.stats['rate_limited'] += 1
            return True
        
        # Add current action
        user_actions.append(now)
        return False
        
    def generate_secret(self):
        """Generate 32-char hex secret"""
        return secrets.token_hex(16)
    
    def _parse_service_file(self):
        """Parse the current MTProxy service file"""
        try:
            with open(self.service_file, 'r') as f:
                content = f.read()
            
            # Extract ExecStart line
            exec_match = re.search(r'ExecStart=(.+)', content)
            if not exec_match:
                return None
                
            exec_line = exec_match.group(1)
            
            # Parse parameters
            config = {
                'secrets': [],
                'port': '8888',
                'tag': '',
                'tls_domain': 'www.cloudflare.com',
                'workers': '1'
            }
            
            # Extract port
            port_match = re.search(r'-H (\d+)', exec_line)
            if port_match:
                config['port'] = port_match.group(1)
            
            # Extract secrets
            secret_matches = re.findall(r'-S ([a-f0-9]{32})', exec_line)
            config['secrets'] = secret_matches
            
            # Extract tag
            tag_match = re.search(r'-P ([a-f0-9]{32})', exec_line)
            if tag_match:
                config['tag'] = tag_match.group(1)
            
            # Extract TLS domain
            domain_match = re.search(r'-D ([^\s]+)', exec_line)
            if domain_match:
                config['tls_domain'] = domain_match.group(1)
            
            # Extract workers
            worker_match = re.search(r'-M (\d+)', exec_line)
            if worker_match:
                config['workers'] = worker_match.group(1)
            
            return config
            
        except Exception as e:
            logger.error(f"Error parsing service file: {e}")
            return None
    
    def _write_service_file(self, config):
        """Write updated service file"""
        try:
            # Build ExecStart command
            secrets_str = ' '.join([f'-S {s}' for s in config['secrets']])
            tag_str = f'-P {config["tag"]} ' if config['tag'] else ''
            domain_str = f'-D {config["tls_domain"]} ' if config['tls_domain'] else ''
            
            exec_start = (f"/opt/MTProxy/objs/bin/mtproto-proxy -u nobody "
                         f"-H {config['port']} {secrets_str} {tag_str}{domain_str}"
                         f"-M {config['workers']} --aes-pwd proxy-secret proxy-multi.conf")
            
            service_content = f"""[Unit]
Description=MTProxy
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/MTProxy/objs/bin
ExecStart={exec_start}
Restart=on-failure
StartLimitBurst=0

[Install]
WantedBy=multi-user.target"""
            
            with open(self.service_file, 'w') as f:
                f.write(service_content)
            
            return True
            
        except Exception as e:
            logger.error(f"Error writing service file: {e}")
            return False
    
    async def add_secret(self, secret):
        """Add secret to MTProxy with rate limiting and error handling"""
        try:
            async with self.operation_lock:
                # Check if we need to wait for cooldown
                now = time.time()
                if now - self.last_mtproxy_restart < self.restart_cooldown:
                    wait_time = self.restart_cooldown - (now - self.last_mtproxy_restart)
                    logger.info(f"Waiting {wait_time:.1f}s for MTProxy cooldown")
                    await asyncio.sleep(wait_time)
                
                config = self._parse_service_file()
                if not config:
                    logger.error("Failed to parse service file")
                    self.stats['errors'] += 1
                    return False
                
                # Add secret if not already present
                if secret not in config['secrets']:
                    config['secrets'].append(secret)
                    
                    # Stop service
                    subprocess.run(['systemctl', 'stop', 'MTProxy'], check=False)
                    
                    # Write new service file
                    if not self._write_service_file(config):
                        self.stats['errors'] += 1
                        return False
                    
                    # Reload and start
                    subprocess.run(['systemctl', 'daemon-reload'], check=True)
                    result = subprocess.run(['systemctl', 'start', 'MTProxy'], check=True)
                    
                    self.last_mtproxy_restart = time.time()
                    self.stats['proxies_created'] += 1
                    logger.info(f"✅ Added secret: {secret[:8]}...")
                    return True
                else:
                    logger.info(f"✅ Secret already exists: {secret[:8]}...")
                    return True
                    
        except Exception as e:
            logger.error(f"❌ Error adding secret: {e}")
            self.stats['errors'] += 1
            return False
    
    async def remove_secret(self, secret):
        """Remove secret from MTProxy with rate limiting"""
        try:
            async with self.operation_lock:
                # Check if we need to wait for cooldown
                now = time.time()
                if now - self.last_mtproxy_restart < self.restart_cooldown:
                    wait_time = self.restart_cooldown - (now - self.last_mtproxy_restart)
                    logger.info(f"Waiting {wait_time:.1f}s for MTProxy cooldown")
                    await asyncio.sleep(wait_time)
                
                config = self._parse_service_file()
                if not config:
                    self.stats['errors'] += 1
                    return False
                
                if secret in config['secrets']:
                    config['secrets'].remove(secret)
                    
                    # Stop service
                    subprocess.run(['systemctl', 'stop', 'MTProxy'], check=False)
                    
                    # Write new service file
                    if not self._write_service_file(config):
                        self.stats['errors'] += 1
                        return False
                    
                    # Reload and start
                    subprocess.run(['systemctl', 'daemon-reload'], check=True)
                    subprocess.run(['systemctl', 'start', 'MTProxy'], check=True)
                    
                    self.last_mtproxy_restart = time.time()
                    self.stats['proxies_removed'] += 1
                    logger.info(f"✅ Removed secret: {secret[:8]}...")
                    return True
                else:
                    logger.info(f"✅ Secret not found: {secret[:8]}...")
                    return True
                    
        except Exception as e:
            logger.error(f"❌ Error removing secret: {e}")
            self.stats['errors'] += 1
            return False
    
    def get_proxy_link(self, secret):
        """Generate proxy link"""
        try:
            config = self._parse_service_file()
            if not config:
                # Fallback values
                port = "8888"
                tls_domain = "www.cloudflare.com"
            else:
                port = config['port']
                tls_domain = config['tls_domain']
            
            # Get public IP
            try:
                result = subprocess.run(['curl', 'https://api.ipify.org', '-sS'], 
                                      capture_output=True, text=True, timeout=10)
                public_ip = result.stdout.strip() if result.returncode == 0 else "130.185.123.84"
            except:
                public_ip = "130.185.123.84"
            
            # Generate link exactly like your working example
            if tls_domain and tls_domain != '""':
                hex_domain = tls_domain.encode('utf-8').hex().lower()
                full_secret = f"ee{secret}{hex_domain}"
            else:
                full_secret = f"dd{secret}"
            
            return f"https://t.me/proxy?server={public_ip}&port={port}&secret={full_secret}"
            
        except Exception as e:
            logger.error(f"Error generating link: {e}")
            return f"https://t.me/proxy?server=130.185.123.84&port=8888&secret=ee{secret}77772e636c6f7564666c6172652e636f6d"
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        try:
            member = await context.bot.get_chat_member(self.config.CHANNEL_ID, user.id)
            if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                await self._provide_proxy(update, context, user)
            else:
                await self._request_join(update, context)
        except Exception as e:
            logger.error(f"Error checking membership: {e}")
            await update.message.reply_text(self.t('error_membership'))
    
    async def _provide_proxy(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user):
        """Provide MTProxy to user with rate limiting"""
        # Check rate limiting
        if self.is_rate_limited(user.id):
            await update.message.reply_text("⚠️ Please wait before requesting another proxy.")
            return
            
        existing_user = self.db.get_user(user.id)
        
        if existing_user and existing_user['is_active']:
            # Create button that requires confirmation
            keyboard = [[InlineKeyboardButton(self.t('btn_get_proxy'), callback_data=f"get_proxy_{user.id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"{self.t('welcome_back')}\n\n"
                f"{self.t('how_to_connect')}\n"
                f"{self.t('step_tap_button')}\n"
                f"{self.t('step_telegram_ask')}\n"
                f"{self.t('step_connect')}\n\n"
                f"{self.t('stay_in_channel')}\n"
                f"{self.t('security_notice')}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            secret = self.generate_secret()
            
            if await self.add_secret(secret):
                username = user.username or f"user_{user.id}"
                if self.db.add_user(user.id, username, secret):
                    # Create button that requires confirmation
                    keyboard = [[InlineKeyboardButton(self.t('btn_get_proxy'), callback_data=f"get_proxy_{user.id}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        f"{self.t('welcome_new')}\n\n"
                        f"{self.t('how_to_connect')}\n"
                        f"{self.t('step_tap_button')}\n"
                        f"{self.t('step_telegram_ask')}\n"
                        f"{self.t('step_connect')}\n\n"
                        f"{self.t('stay_in_channel')}\n"
                        f"{self.t('security_notice')}",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(self.t('error_saving'))
            else:
                await update.message.reply_text(self.t('error_creating'))
    
    async def handle_proxy_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle proxy button callback"""
        query = update.callback_query
        await query.answer()
        
        # Extract user ID from callback data
        callback_data = query.data
        if not callback_data.startswith("get_proxy_"):
            return
            
        requested_user_id = int(callback_data.split("_")[2])
        actual_user_id = query.from_user.id
        
        # Security check: only the user can get their own proxy
        if requested_user_id != actual_user_id:
            await query.edit_message_text(self.t('only_own_proxy'))
            return
        
        # Get user's proxy
        user_data = self.db.get_user(actual_user_id)
        if user_data and user_data['is_active']:
            proxy_link = self.get_proxy_link(user_data['secret'])
            
            # Create button with actual proxy link
            keyboard = [[InlineKeyboardButton(self.t('btn_connect_proxy'), url=proxy_link)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"{self.t('personal_proxy')}\n\n"
                f"{self.t('tap_to_connect')}\n\n"
                f"{self.t('security_notice_title')}\n"
                f"{self.t('security_personal')}\n"
                f"{self.t('security_no_share')}\n"
                f"{self.t('security_stay_active')}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    async def _request_join(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Request user to join channel"""
        keyboard = [[InlineKeyboardButton(self.t('btn_join_channel'), url=f"https://t.me/{self.config.CHANNEL_USERNAME}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"{self.t('access_required')}\n\n"
            f"{self.t('join_first')}\n\n"
            f"👆 {self.t('auto_receive')}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def handle_member_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle channel member updates with rate limiting and error handling"""
        try:
            # Check if this update is for our channel
            chat_id = update.chat_member.chat.id
            
            # Get our target channel's numeric ID
            try:
                target_chat_id = await self.get_channel_chat_id(context)
            except Exception as e:
                logger.error(f"❌ Could not resolve target channel ID: {e}")
                return
            
            # Only process updates for our target channel
            if chat_id != target_chat_id:
                return
                
            user_id = update.chat_member.new_chat_member.user.id
            username = update.chat_member.new_chat_member.user.username or "no_username"
            old_status = update.chat_member.old_chat_member.status
            new_status = update.chat_member.new_chat_member.status
            
            # Rate limiting check
            if self.is_rate_limited(user_id):
                logger.warning(f"⚠️ Rate limited user {user_id}, skipping action")
                return
            
            logger.info(f"👤 Member update for user {user_id} (@{username}): {old_status} -> {new_status}")
            
            # User joined the channel
            if (old_status == ChatMemberStatus.LEFT and 
                new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]):
                
                self.stats['joins'] += 1
                logger.info(f"🎉 User {user_id} joined the channel! (Total joins: {self.stats['joins']})")
                
                # Automatically provide proxy to new member
                await self._auto_provide_proxy(context, user_id, username)
            
            # User left the channel
            elif (old_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER] and 
                  new_status == ChatMemberStatus.LEFT):
                
                self.stats['leaves'] += 1
                logger.info(f"🚪 User {user_id} left the channel! (Total leaves: {self.stats['leaves']})")
                
                user_data = self.db.get_user(user_id)
                if user_data and user_data['is_active']:
                    logger.info(f"🔑 Found active proxy for user {user_id}, secret: {user_data['secret'][:8]}...")
                    logger.info(f"🗑️ Removing proxy access for user {user_id}")
                    
                    if await self.remove_secret(user_data['secret']):
                        self.db.deactivate_user(user_id)
                        logger.info(f"✅ Successfully deactivated proxy for user {user_id}")
                        
                        # Try to notify user (optional) - but don't block on it
                        asyncio.create_task(self._notify_user_deactivation(context, user_id))
                    else:
                        logger.error(f"❌ Failed to remove secret for user {user_id}")
                else:
                    logger.info(f"ℹ️ User {user_id} left but had no active proxy")
            else:
                logger.info(f"ℹ️ Status change not relevant: {old_status} -> {new_status}")
                
        except Exception as e:
            logger.error(f"❌ Error in handle_member_update: {e}")
            import traceback
            traceback.print_exc()
    
    async def _notify_user_deactivation(self, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Notify user about proxy deactivation (non-blocking)"""
        try:
            await context.bot.send_message(user_id, self.t('proxy_deactivated'))
            logger.info(f"📨 Notified user {user_id} about deactivation")
        except Exception as e:
            logger.info(f"📨 Could not notify user {user_id}: {e}")
    
    async def _auto_provide_proxy(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, username: str):
        """Automatically provide proxy to new channel member"""
        try:
            # Check if user already has an active proxy
            existing_user = self.db.get_user(user_id)
            
            if existing_user and existing_user['is_active']:
                logger.info(f"User {user_id} rejoined - reactivating existing proxy")
                # User rejoined, just send them their existing proxy
                keyboard = [[InlineKeyboardButton(self.t('btn_get_proxy'), callback_data=f"get_proxy_{user_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    user_id,
                    f"{self.t('welcome_auto_back')}\n\n"
                    f"{self.t('how_to_connect')}\n"
                    f"{self.t('step_tap_button')}\n"
                    f"{self.t('step_telegram_ask')}\n"
                    f"{self.t('step_connect')}\n\n"
                    f"{self.t('security_notice')}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                logger.info(f"Creating new proxy for user {user_id}")
                # Create new proxy for new user
                secret = self.generate_secret()
                
                if await self.add_secret(secret):
                    user_name = username or f"user_{user_id}"
                    if self.db.add_user(user_id, user_name, secret):
                        keyboard = [[InlineKeyboardButton(self.t('btn_get_proxy'), callback_data=f"get_proxy_{user_id}")]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await context.bot.send_message(
                            user_id,
                            f"{self.t('welcome_auto_new')}\n\n"
                            f"{self.t('how_to_connect')}\n"
                            f"{self.t('step_tap_button')}\n"
                            f"{self.t('step_telegram_ask')}\n"
                            f"{self.t('step_connect')}\n\n"
                            f"{self.t('stay_in_channel')}\n"
                            f"{self.t('security_notice')}",
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        )
                        logger.info(f"✅ Sent auto-proxy to user {user_id}")
                    else:
                        logger.error(f"Failed to save user {user_id} to database")
                else:
                    logger.error(f"Failed to add secret for user {user_id}")
                    
        except Exception as e:
            logger.error(f"Error auto-providing proxy to user {user_id}: {e}")
                
        except Exception as e:
            logger.error(f"❌ Error in handle_member_update: {e}")
            import traceback
            traceback.print_exc()
    
    async def menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main menu"""
        user = update.effective_user
        
        # Check if user is in channel
        try:
            member = await context.bot.get_chat_member(self.config.CHANNEL_ID, user.id)
            if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                # User is in channel - show proxy options
                user_data = self.db.get_user(user.id)
                
                if user_data and user_data['is_active']:
                    keyboard = [
                        [InlineKeyboardButton(self.t('btn_get_proxy'), callback_data=f"get_proxy_{user.id}")],
                        [InlineKeyboardButton(self.t('btn_proxy_status'), callback_data=f"status_{user.id}")],
                        [InlineKeyboardButton(self.t('btn_help'), callback_data="help")]
                    ]
                else:
                    keyboard = [
                        [InlineKeyboardButton(self.t('btn_create_proxy'), callback_data=f"create_proxy_{user.id}")],
                        [InlineKeyboardButton(self.t('btn_help'), callback_data="help")]
                    ]
                
                # Add admin controls for channel admins
                if await self.is_channel_admin(context, user.id):
                    keyboard.append([InlineKeyboardButton("📌 پین منوی کانال", callback_data="admin_pin_menu")])
                    keyboard.append([InlineKeyboardButton("🗑️ حذف همه پین‌ها", callback_data="admin_unpin_all")])
                    keyboard.append([InlineKeyboardButton("📊 آمار ربات", callback_data="admin_stats")])
                    keyboard.append([InlineKeyboardButton("🔄 راه‌اندازی مجدد پروکسی", callback_data="admin_restart_proxy")])
                    keyboard.append([InlineKeyboardButton("🚨 راه‌اندازی مجدد سرور", callback_data="admin_reboot_vps")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"{self.t('menu_title')}\n\n"
                    f"{self.t('menu_welcome', name=user.first_name)}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                # User not in channel
                keyboard = [
                    [InlineKeyboardButton(self.t('btn_join_channel'), url=f"https://t.me/{self.config.CHANNEL_USERNAME}")],
                    [InlineKeyboardButton(self.t('btn_help'), callback_data="help")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"{self.t('access_required')}\n\n"
                    f"{self.t('join_first')}\n\n"
                    f"{self.t('auto_receive')}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error in menu: {e}")
            await update.message.reply_text(self.t('error_membership'))
    
    async def handle_menu_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu button callbacks"""
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        user_id = query.from_user.id
        
        if callback_data.startswith("status_"):
            # Show proxy status
            user_data = self.db.get_user(user_id)
            if user_data and user_data['is_active']:
                keyboard = [
                    [InlineKeyboardButton(self.t('btn_get_proxy'), callback_data=f"get_proxy_{user_id}")],
                    [InlineKeyboardButton(self.t('btn_back_menu'), callback_data="back_to_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"{self.t('proxy_status_title')}\n\n"
                    f"{self.t('status_active')}\n"
                    f"{self.t('created_date', date=user_data['created_at'])}\n"
                    f"{self.t('username_label', username=user_data['username'])}\n\n"
                    f"{self.t('tip_stay_active')}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(self.t('no_active_proxy'))
        
        elif callback_data.startswith("create_proxy_"):
            # Create new proxy
            await self._provide_proxy_via_callback(query, context)
        
        elif callback_data == "help":
            # Show help
            keyboard = [[InlineKeyboardButton(self.t('btn_back_menu'), callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"{self.t('detailed_help_title')}\n\n"
                f"{self.t('detailed_step1')}\n"
                f"{self.t('detailed_step2')}\n"
                f"{self.t('detailed_step3')}\n"
                f"{self.t('detailed_step4')}\n"
                f"{self.t('detailed_step5')}\n\n"
                f"{self.t('help_security')}\n"
                f"{self.t('help_unique')}\n"
                f"{self.t('help_no_share')}\n"
                f"{self.t('help_stay_channel')}\n\n"
                f"{self.t('help_commands')}\n"
                f"{self.t('help_menu')}\n"
                f"{self.t('help_start')}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        elif callback_data == "admin_pin_menu":
            # Admin: Create channel pin menu
            if await self.is_channel_admin(context, user_id):
                await self._handle_admin_pin_callback(query, context)
            else:
                await query.edit_message_text(self.t('access_denied'))
        
        elif callback_data == "admin_unpin_all":
            # Admin: Unpin all messages
            if await self.is_channel_admin(context, user_id):
                await self._handle_admin_unpin_callback(query, context)
            else:
                await query.edit_message_text(self.t('access_denied'))
        
        elif callback_data == "admin_stats":
            # Admin: Show stats
            if await self.is_channel_admin(context, user_id):
                await self._handle_admin_stats_callback(query, context)
            else:
                await query.edit_message_text(self.t('access_denied'))
        
        elif callback_data == "admin_restart_proxy":
            # Admin: Restart MTProxy
            if await self.is_channel_admin(context, user_id):
                await self._handle_admin_restart_proxy_callback(query, context)
            else:
                await query.edit_message_text(self.t('access_denied'))
        
        elif callback_data == "admin_reboot_vps":
            # Admin: Reboot VPS
            if await self.is_channel_admin(context, user_id):
                await self._handle_admin_reboot_vps_callback(query, context)
            else:
                await query.edit_message_text(self.t('access_denied'))
        
        elif callback_data == "admin_reboot_confirm":
            # Admin: Confirm VPS reboot
            if await self.is_channel_admin(context, user_id):
                await self._handle_admin_reboot_confirm_callback(query, context)
            else:
                await query.edit_message_text(self.t('access_denied'))
        
        elif callback_data == "back_to_menu":
            # Go back to main menu
            await self._show_main_menu_callback(query, context)
    
    async def _handle_admin_pin_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin pin menu callback"""
        try:
            # Get bot username for links
            bot_info = await context.bot.get_me()
            bot_username = bot_info.username
            
            # Create single button for proxy access
            keyboard = [
                [InlineKeyboardButton("🔗 دریافت پروکسی", url=f"https://t.me/{bot_username}?start=proxy")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Message text in Persian
            menu_text = (
                "🔗 **دریافت پروکسی رایگان MTProxy**\n\n"
                "🎁 **برای اعضای کانال کاملاً رایگان!**\n\n"
                "📱 **نحوه دریافت:**\n"
                "👆 روی دکمه 'دریافت پروکسی' کلیک کنید\n\n"
                "⚠️ **مهم:** فقط اعضای کانال پروکسی دریافت می‌کنند\n"
                "🔒 **امنیت:** پروکسی خود را با دیگران به اشتراک نگذارید"
            )
            
            # Get channel ID
            channel_id = self.config.CHANNEL_ID
            if channel_id.startswith('@'):
                chat = await context.bot.get_chat(channel_id)
                channel_chat_id = chat.id
            else:
                channel_chat_id = int(channel_id)
            
            # Send message with buttons to channel
            message = await context.bot.send_message(
                chat_id=channel_chat_id,
                text=menu_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            # Pin the message
            await context.bot.pin_chat_message(
                chat_id=channel_chat_id,
                message_id=message.message_id,
                disable_notification=True
            )
            
            # Update admin message
            await query.edit_message_text(
                f"✅ پیام دسترسی سریع ایجاد شد!\n\n"
                f"📌 پیام در کانال پین شد\n"
                f"🔗 شامل دکمه‌های کلیکی\n"
                f"👥 کاربران می‌توانند مستقیماً ربات را شروع کنند\n\n"
                f"کانال: {self.config.CHANNEL_ID}\n"
                f"شناسه پیام: {message.message_id}"
            )
            
            logger.info(f"✅ Channel menu created and pinned via callback")
            
        except Exception as e:
            logger.error(f"❌ Error in admin pin callback: {e}")
            await query.edit_message_text(
                f"❌ خطا در ایجاد پیام کانال:\n\n"
                f"{str(e)}\n\n"
                f"بررسی کنید:\n"
                f"• ربات ادمین کانال باشد\n"
                f"• مجوز ارسال و پین پیام داشته باشد\n"
                f"• شناسه کانال صحیح باشد"
            )
    
    async def _handle_admin_unpin_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin unpin all messages callback"""
        try:
            # Get channel ID
            channel_id = self.config.CHANNEL_ID
            if channel_id.startswith('@'):
                chat = await context.bot.get_chat(channel_id)
                channel_chat_id = chat.id
            else:
                channel_chat_id = int(channel_id)
            
            # Unpin all messages
            await context.bot.unpin_all_chat_messages(chat_id=channel_chat_id)
            
            # Update admin message
            await query.edit_message_text(
                f"✅ همه پیام‌های پین شده حذف شد!\n\n"
                f"📌 تمام پیام‌های پین شده در کانال حذف شدند\n"
                f"🧹 کانال اکنون بدون پیام پین شده است\n\n"
                f"کانال: {self.config.CHANNEL_ID}"
            )
            
            logger.info(f"✅ All pinned messages unpinned via callback")
            
        except Exception as e:
            logger.error(f"❌ Error in admin unpin callback: {e}")
            await query.edit_message_text(
                f"❌ خطا در حذف پین پیام‌ها:\n\n"
                f"{str(e)}\n\n"
                f"بررسی کنید:\n"
                f"• ربات ادمین کانال باشد\n"
                f"• مجوز مدیریت پیام‌ها داشته باشد\n"
                f"• شناسه کانال صحیح باشد"
            )
    
    async def _handle_admin_stats_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin stats callback"""
        total_users = len(self.db.get_all_active_users())
        uptime = time.time() - getattr(self, 'start_time', time.time())
        
        stats_text = (
            f"📊 **آمار ربات**\n\n"
            f"👥 **کاربران:** {total_users} فعال\n"
            f"📈 **فعالیت:**\n"
            f"   • عضویت: {self.stats['joins']}\n"
            f"   • خروج: {self.stats['leaves']}\n"
            f"   • پروکسی ایجاد شده: {self.stats['proxies_created']}\n"
            f"   • پروکسی حذف شده: {self.stats['proxies_removed']}\n\n"
            f"⚠️ **مشکلات:**\n"
            f"   • خطاها: {self.stats['errors']}\n"
            f"   • محدود شده: {self.stats['rate_limited']}\n\n"
            f"⏱️ **مدت کار:** {uptime/3600:.1f} ساعت\n"
            f"🔄 **آخرین ریستارت MTProxy:** {time.time() - self.last_mtproxy_restart:.1f}s پیش"
        )
        
        keyboard = [[InlineKeyboardButton(self.t('btn_back'), callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def _handle_admin_restart_proxy_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin restart proxy callback"""
        try:
            # Send initial message
            await query.edit_message_text("🔄 در حال راه‌اندازی مجدد سرویس MTProxy...")
            
            # Stop MTProxy service
            stop_result = subprocess.run(['systemctl', 'stop', 'MTProxy'], 
                                       capture_output=True, text=True, timeout=30)
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Start MTProxy service
            start_result = subprocess.run(['systemctl', 'start', 'MTProxy'], 
                                        capture_output=True, text=True, timeout=30)
            
            # Check service status
            status_result = subprocess.run(['systemctl', 'is-active', 'MTProxy'], 
                                         capture_output=True, text=True, timeout=10)
            
            keyboard = [[InlineKeyboardButton(self.t('btn_back'), callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if status_result.returncode == 0 and status_result.stdout.strip() == 'active':
                await query.edit_message_text(
                    "✅ **راه‌اندازی مجدد MTProxy موفق**\n\n"
                    f"🔄 سرویس توسط ادمین راه‌اندازی شد: @{query.from_user.username or 'Unknown'}\n"
                    f"⏰ زمان: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📊 وضعیت: فعال\n\n"
                    f"همه پروکسی‌های کاربران باید به طور عادی کار کنند.",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                logger.info(f"✅ MTProxy restarted successfully via callback by admin {query.from_user.id}")
                self.last_mtproxy_restart = time.time()
            else:
                error_info = f"Stop: {stop_result.stderr}\nStart: {start_result.stderr}" if (stop_result.stderr or start_result.stderr) else "خطای نامشخص"
                await query.edit_message_text(
                    "❌ **راه‌اندازی مجدد MTProxy ناموفق**\n\n"
                    f"⚠️ سرویس ممکن است به درستی کار نکند\n"
                    f"📝 جزئیات خطا: {error_info[:200]}...\n\n"
                    f"لطفاً سرویس را به صورت دستی بررسی کنید:\n"
                    f"`systemctl status MTProxy`",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                logger.error(f"❌ MTProxy restart failed via callback by admin {query.from_user.id}: {error_info}")
                
        except subprocess.TimeoutExpired:
            keyboard = [[InlineKeyboardButton(self.t('btn_back'), callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "⏰ **زمان راه‌اندازی مجدد MTProxy تمام شد**\n\n"
                "عملیات راه‌اندازی مجدد زمان زیادی برد. لطفاً به صورت دستی بررسی کنید:\n"
                "`systemctl status MTProxy`",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            logger.error(f"❌ MTProxy restart timeout via callback by admin {query.from_user.id}")
        except Exception as e:
            keyboard = [[InlineKeyboardButton(self.t('btn_back'), callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"❌ **خطا در راه‌اندازی مجدد MTProxy**\n\n"
                f"خطای غیرمنتظره: {str(e)[:200]}\n\n"
                f"لطفاً سرویس را به صورت دستی بررسی کنید:\n"
                f"`systemctl status MTProxy`",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            logger.error(f"❌ MTProxy restart error via callback by admin {query.from_user.id}: {e}")

    async def _handle_admin_reboot_vps_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin reboot VPS callback"""
        # Show confirmation dialog
        keyboard = [
            [InlineKeyboardButton(self.t('btn_confirm_reboot'), callback_data="admin_reboot_confirm")],
            [InlineKeyboardButton(self.t('btn_cancel'), callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            self.t('admin_reboot_vps_confirm_dialog'),
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def _handle_admin_reboot_confirm_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin reboot VPS confirmation callback"""
        try:
            # Send warning message
            await query.edit_message_text(
                "🚨 **راه‌اندازی مجدد سرور آغاز شد**\n\n"
                f"👤 ادمین: @{query.from_user.username or 'Unknown'}\n"
                f"⏰ زمان: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                "⚠️ سرور در ۱۰ ثانیه راه‌اندازی مجدد خواهد شد...\n"
                "🔄 همه سرویس‌ها به صورت خودکار راه‌اندازی خواهند شد\n"
                "⏱️ زمان تخمینی قطعی: ۲-۵ دقیقه",
                parse_mode='Markdown'
            )
            
            logger.warning(f"🚨 VPS REBOOT initiated via callback by admin {query.from_user.id} (@{query.from_user.username})")
            
            # Wait 10 seconds to allow message to be sent
            await asyncio.sleep(10)
            
            # Final warning
            await query.edit_message_text(
                "🚨 **در حال راه‌اندازی مجدد...**\n\n"
                "سرور در حال خاموش شدن است.\n"
                "ربات پس از راه‌اندازی مجدد آنلاین خواهد شد.",
                parse_mode='Markdown'
            )
            
            # Wait a moment for message to be sent
            await asyncio.sleep(2)
            
            # Execute reboot command
            subprocess.run(['systemctl', 'reboot'], timeout=5)
            
        except subprocess.TimeoutExpired:
            # This is expected as the system will reboot
            logger.info("Reboot command executed via callback, system shutting down...")
        except Exception as e:
            keyboard = [[InlineKeyboardButton(self.t('btn_back'), callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"❌ **راه‌اندازی مجدد ناموفق**\n\n"
                f"خطا: {str(e)[:200]}\n\n"
                f"لطفاً به صورت دستی بررسی کنید یا از دستور زیر استفاده کنید:\n"
                f"`sudo reboot`",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            logger.error(f"❌ VPS reboot failed via callback by admin {query.from_user.id}: {e}")

    async def _provide_proxy_via_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Provide proxy via callback query"""
        user = query.from_user
        
        # Check if user is in channel
        try:
            member = await context.bot.get_chat_member(self.config.CHANNEL_ID, user.id)
            if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                await query.edit_message_text(self.t('must_join_first'))
                return
        except Exception as e:
            await query.edit_message_text(self.t('error_membership'))
            return
        
        # Create proxy
        existing_user = self.db.get_user(user.id)
        
        if existing_user and existing_user['is_active']:
            keyboard = [[InlineKeyboardButton(self.t('btn_get_proxy'), callback_data=f"get_proxy_{user.id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                self.t('proxy_ready'),
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            secret = self.generate_secret()
            
            if await self.add_secret(secret):
                username = user.username or f"user_{user.id}"
                if self.db.add_user(user.id, username, secret):
                    keyboard = [[InlineKeyboardButton(self.t('btn_get_proxy'), callback_data=f"get_proxy_{user.id}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await query.edit_message_text(
                        self.t('new_proxy_created'),
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                else:
                    await query.edit_message_text(self.t('error_saving'))
            else:
                await query.edit_message_text(self.t('error_creating'))
    
    async def _show_main_menu_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Show main menu via callback query"""
        user = query.from_user
        
        # Check if user is in channel
        try:
            member = await context.bot.get_chat_member(self.config.CHANNEL_ID, user.id)
            if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                # User is in channel - show proxy options
                user_data = self.db.get_user(user.id)
                
                if user_data and user_data['is_active']:
                    keyboard = [
                        [InlineKeyboardButton(self.t('btn_get_proxy'), callback_data=f"get_proxy_{user.id}")],
                        [InlineKeyboardButton(self.t('btn_proxy_status'), callback_data=f"status_{user.id}")],
                        [InlineKeyboardButton(self.t('btn_help'), callback_data="help")]
                    ]
                else:
                    keyboard = [
                        [InlineKeyboardButton(self.t('btn_create_proxy'), callback_data=f"create_proxy_{user.id}")],
                        [InlineKeyboardButton(self.t('btn_help'), callback_data="help")]
                    ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    f"{self.t('menu_title')}\n\n"
                    f"{self.t('menu_welcome', name=user.first_name)}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                # User not in channel
                keyboard = [
                    [InlineKeyboardButton(self.t('btn_join_channel'), url=f"https://t.me/{self.config.CHANNEL_USERNAME}")],
                    [InlineKeyboardButton(self.t('btn_help'), callback_data="help")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"{self.t('access_required')}\n\n"
                    f"{self.t('join_first')}\n\n"
                    f"{self.t('auto_receive')}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error in menu callback: {e}")
            await query.edit_message_text(self.t('error_membership'))
    
    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help information"""
        keyboard = [[InlineKeyboardButton(self.t('btn_main_menu'), callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"{self.t('help_title')}\n\n"
            f"{self.t('help_quick_start')}\n"
            f"{self.t('help_step1')}\n"
            f"{self.t('help_step2')}\n\n"
            f"{self.t('help_commands')}\n"
            f"{self.t('help_start')}\n"
            f"{self.t('help_menu')}\n"
            f"{self.t('help_help')}\n\n"
            f"{self.t('help_security')}\n"
            f"{self.t('help_unique')}\n"
            f"{self.t('help_no_share')}\n"
            f"{self.t('help_stay_channel')}\n\n"
            f"{self.t('help_tip_menu')}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def pin_channel_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create and pin channel access menu (admin only)"""
        user_id = update.effective_user.id
        
        # Admin check
        if not await self.is_channel_admin(context, user_id):
            await update.message.reply_text(self.t('access_denied'))
            return
        
        try:
            # Get bot username for links
            bot_info = await context.bot.get_me()
            bot_username = bot_info.username
            
            # Create single button for proxy access
            keyboard = [
                [InlineKeyboardButton("🔗 دریافت پروکسی", url=f"https://t.me/{bot_username}?start=proxy")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Message text in Persian
            menu_text = (
                "🔗 **دریافت پروکسی رایگان MTProxy**\n\n"
                "🎁 **برای اعضای کانال کاملاً رایگان!**\n\n"
                "📱 **نحوه دریافت:**\n"
                "👆 روی دکمه 'دریافت پروکسی' کلیک کنید\n\n"
                "⚠️ **مهم:** فقط اعضای کانال پروکسی دریافت می‌کنند\n"
                "🔒 **امنیت:** پروکسی خود را با دیگران به اشتراک نگذارید"
            )
            
            # Get channel ID
            channel_id = self.config.CHANNEL_ID
            if channel_id.startswith('@'):
                chat = await context.bot.get_chat(channel_id)
                channel_chat_id = chat.id
            else:
                channel_chat_id = int(channel_id)
            
            # Send message with buttons to channel
            message = await context.bot.send_message(
                chat_id=channel_chat_id,
                text=menu_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            # Pin the message
            await context.bot.pin_chat_message(
                chat_id=channel_chat_id,
                message_id=message.message_id,
                disable_notification=True
            )
            
            # Confirm to admin
            await update.message.reply_text(
                f"✅ پیام دسترسی سریع ایجاد شد!\n\n"
                f"📌 پیام در کانال پین شد\n"
                f"🔗 شامل دکمه‌های کلیکی\n"
                f"👥 کاربران می‌توانند مستقیماً ربات را شروع کنند\n\n"
                f"کانال: {self.config.CHANNEL_ID}\n"
                f"شناسه پیام: {message.message_id}"
            )
            
            logger.info(f"✅ Channel menu created and pinned by admin {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Error creating channel menu: {e}")
            await update.message.reply_text(
                f"❌ خطا در ایجاد پیام کانال:\n\n"
                f"{str(e)}\n\n"
                f"بررسی کنید:\n"
                f"• ربات ادمین کانال باشد\n"
                f"• مجوز ارسال و پین پیام داشته باشد\n"
                f"• شناسه کانال صحیح باشد"
            )

    async def unpin_channel_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unpin all messages in channel (admin only)"""
        user_id = update.effective_user.id
        
        # Admin check
        if not await self.is_channel_admin(context, user_id):
            await update.message.reply_text(self.t('access_denied'))
            return
        
        try:
            # Get channel ID
            channel_id = self.config.CHANNEL_ID
            if channel_id.startswith('@'):
                chat = await context.bot.get_chat(channel_id)
                channel_chat_id = chat.id
            else:
                channel_chat_id = int(channel_id)
            
            # Unpin all messages
            await context.bot.unpin_all_chat_messages(chat_id=channel_chat_id)
            
            # Confirm to admin
            await update.message.reply_text(
                f"✅ همه پیام‌های پین شده حذف شد!\n\n"
                f"📌 تمام پیام‌های پین شده در کانال حذف شدند\n"
                f"🧹 کانال اکنون بدون پیام پین شده است\n\n"
                f"کانال: {self.config.CHANNEL_ID}"
            )
            
            logger.info(f"✅ All pinned messages unpinned by admin {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Error unpinning messages: {e}")
            await update.message.reply_text(
                f"❌ خطا در حذف پین پیام‌ها:\n\n"
                f"{str(e)}\n\n"
                f"بررسی کنید:\n"
                f"• ربات ادمین کانال باشد\n"
                f"• مجوز مدیریت پیام‌ها داشته باشد\n"
                f"• شناسه کانال صحیح باشد"
            )

    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show bot statistics (admin only)"""
        user_id = update.effective_user.id
        
        # Admin check
        if not await self.is_channel_admin(context, user_id):
            await update.message.reply_text(self.t('access_denied'))
            return
        
        total_users = len(self.db.get_all_active_users())
        uptime = time.time() - getattr(self, 'start_time', time.time())
        
        stats_text = (
            f"📊 **Bot Statistics**\n\n"
            f"👥 **Users:** {total_users} active\n"
            f"📈 **Activity:**\n"
            f"   • Joins: {self.stats['joins']}\n"
            f"   • Leaves: {self.stats['leaves']}\n"
            f"   • Proxies created: {self.stats['proxies_created']}\n"
            f"   • Proxies removed: {self.stats['proxies_removed']}\n\n"
            f"⚠️ **Issues:**\n"
            f"   • Errors: {self.stats['errors']}\n"
            f"   • Rate limited: {self.stats['rate_limited']}\n\n"
            f"⏱️ **Uptime:** {uptime/3600:.1f} hours\n"
            f"🔄 **Last MTProxy restart:** {time.time() - self.last_mtproxy_restart:.1f}s ago"
        )
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')

    async def restart_mtproxy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Restart MTProxy service (admin only)"""
        user_id = update.effective_user.id
        
        # Admin check
        if not await self.is_channel_admin(context, user_id):
            await update.message.reply_text(self.t('access_denied'))
            return
        
        try:
            # Send initial message
            status_msg = await update.message.reply_text(self.t('admin_restart_proxy_progress'))
            
            # Stop MTProxy service
            stop_result = subprocess.run(['systemctl', 'stop', 'MTProxy'], 
                                       capture_output=True, text=True, timeout=30)
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Start MTProxy service
            start_result = subprocess.run(['systemctl', 'start', 'MTProxy'], 
                                        capture_output=True, text=True, timeout=30)
            
            # Check service status
            status_result = subprocess.run(['systemctl', 'is-active', 'MTProxy'], 
                                         capture_output=True, text=True, timeout=10)
            
            if status_result.returncode == 0 and status_result.stdout.strip() == 'active':
                await status_msg.edit_text(
                    self.t('admin_restart_proxy_success', 
                           username=update.effective_user.username or 'Unknown',
                           time=time.strftime('%Y-%m-%d %H:%M:%S')),
                    parse_mode='Markdown'
                )
                logger.info(f"✅ MTProxy restarted successfully by admin {user_id}")
                self.last_mtproxy_restart = time.time()
            else:
                error_info = f"Stop: {stop_result.stderr}\nStart: {start_result.stderr}" if (stop_result.stderr or start_result.stderr) else "Unknown error"
                await status_msg.edit_text(
                    self.t('admin_restart_proxy_failed', error=error_info[:200]),
                    parse_mode='Markdown'
                )
                logger.error(f"❌ MTProxy restart failed by admin {user_id}: {error_info}")
                
        except subprocess.TimeoutExpired:
            await status_msg.edit_text(
                self.t('admin_restart_proxy_timeout'),
                parse_mode='Markdown'
            )
            logger.error(f"❌ MTProxy restart timeout by admin {user_id}")
        except Exception as e:
            await status_msg.edit_text(
                self.t('admin_restart_proxy_error', error=str(e)[:200]),
                parse_mode='Markdown'
            )
            logger.error(f"❌ MTProxy restart error by admin {user_id}: {e}")

    async def reboot_vps(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reboot VPS system (admin only) - DANGEROUS COMMAND"""
        user_id = update.effective_user.id
        
        # Admin check
        if not await self.is_channel_admin(context, user_id):
            await update.message.reply_text(self.t('access_denied'))
            return
        
        # Double confirmation for this dangerous command
        if len(context.args) == 0 or context.args[0] != "CONFIRM":
            await update.message.reply_text(
                self.t('admin_reboot_vps_warning'),
                parse_mode='Markdown'
            )
            return
        
        try:
            # Send warning message
            warning_msg = await update.message.reply_text(
                self.t('admin_reboot_vps_initiated',
                       username=update.effective_user.username or 'Unknown',
                       time=time.strftime('%Y-%m-%d %H:%M:%S')),
                parse_mode='Markdown'
            )
            
            logger.warning(f"🚨 VPS REBOOT initiated by admin {user_id} (@{update.effective_user.username})")
            
            # Wait 10 seconds to allow message to be sent
            await asyncio.sleep(10)
            
            # Final warning
            await warning_msg.edit_text(
                self.t('admin_reboot_vps_now'),
                parse_mode='Markdown'
            )
            
            # Wait a moment for message to be sent
            await asyncio.sleep(2)
            
            # Execute reboot command
            subprocess.run(['systemctl', 'reboot'], timeout=5)
            
        except subprocess.TimeoutExpired:
            # This is expected as the system will reboot
            logger.info("Reboot command executed, system shutting down...")
        except Exception as e:
            await update.message.reply_text(
                self.t('admin_reboot_vps_failed', error=str(e)[:200]),
                parse_mode='Markdown'
            )
            logger.error(f"❌ VPS reboot failed by admin {user_id}: {e}")

    async def post_init(self, application):
        """Setup menu button after bot starts"""
        try:
            from telegram import MenuButtonCommands
            
            # Set bot commands with translated descriptions
            commands = [
                ("start", self.t('cmd_start_desc')),
                ("menu", self.t('cmd_menu_desc')),
                ("help", self.t('cmd_help_desc')),
                ("pin", self.t('cmd_pin_desc')),
                ("unpin", self.t('cmd_unpin_desc')),
                ("stats", self.t('cmd_stats_desc')),
                ("restart_proxy", self.t('cmd_restart_proxy_desc')),
                ("reboot_vps", self.t('cmd_reboot_vps_desc')),
            ]
            
            await application.bot.set_my_commands(commands)
            
            # Set menu button to show commands
            # The "Menu" text will be in user's Telegram language automatically
            # The command descriptions will be in our configured language
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonCommands()
            )
            
            logger.info("✅ Menu button configured successfully")
            
        except Exception as e:
            logger.error(f"❌ Error setting up menu button: {e}")

    def run(self):
        """Start the bot"""
        application = Application.builder().token(self.config.BOT_TOKEN).build()
        
        # Setup post-init callback for menu button
        application.post_init = self.post_init
        
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("menu", self.menu))
        application.add_handler(CommandHandler("help", self.show_help))
        application.add_handler(CommandHandler("pin", self.pin_channel_menu))  # Admin-only pin command
        application.add_handler(CommandHandler("unpin", self.unpin_channel_message))  # Admin-only unpin command
        application.add_handler(CommandHandler("stats", self.show_stats))
        application.add_handler(CommandHandler("restart_proxy", self.restart_mtproxy))  # Admin-only MTProxy restart
        application.add_handler(CommandHandler("reboot_vps", self.reboot_vps))  # Admin-only VPS reboot
        application.add_handler(CallbackQueryHandler(self.handle_proxy_callback, pattern="^get_proxy_"))
        application.add_handler(CallbackQueryHandler(self.handle_menu_callbacks, pattern="^(status_|create_proxy_|help|back_to_menu|admin_)"))
        application.add_handler(ChatMemberHandler(self.handle_member_update, ChatMemberHandler.CHAT_MEMBER))
        
        # Track start time for statistics
        self.start_time = time.time()
        
        logger.info("Working MTProxy bot started with load management!")
        logger.info(f"Monitoring channel: {self.config.CHANNEL_ID}")
        logger.info("Features: Rate limiting, async operations, error handling")
        logger.info("Bot will receive ALL update types including chat member updates")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    bot = WorkingMTProxyBot()
    bot.run()