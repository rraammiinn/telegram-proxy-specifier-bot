#!/usr/bin/env python3

# Multi-language support for MTProxy Bot
# Logs remain in English, only user messages are translated

LANGUAGES = {
    'en': {
        # Welcome messages
        'welcome_back': "🎉 **Welcome back!** Your MTProxy is ready:",
        'welcome_new': "🎉 **Welcome!** Your MTProxy is ready:",
        'welcome_auto_back': "🎉 **Welcome back to the channel!**\n\nYour MTProxy has been reactivated:",
        'welcome_auto_new': "🎉 **Welcome to the channel!**\n\nYour free MTProxy is ready:",
        
        # Instructions
        'how_to_connect': "📱 **How to connect:**",
        'step_tap_button': "1. Tap the button below to get your proxy",
        'step_telegram_ask': "2. Telegram will ask to use this proxy",
        'step_connect': "3. Tap 'Connect Proxy'",
        
        # Warnings and tips
        'stay_in_channel': "⚠️ **Important:** Stay in the channel to keep your proxy active!",
        'security_notice': "🔒 **Security:** Don't share your proxy with others!",
        'tip_stay_active': "💡 **Tip:** Stay in the channel to keep your proxy active!",
        
        # Buttons
        'btn_get_proxy': "🔗 Get My Proxy",
        'btn_connect_proxy': "🔗 Connect to Proxy",
        'btn_join_channel': "📢 Join Channel",
        'btn_create_proxy': "🆕 Create New Proxy",
        'btn_proxy_status': "📊 Proxy Status",
        'btn_help': "ℹ️ How to Use",
        'btn_back_menu': "🔙 Back to Menu",
        'btn_main_menu': "🎛️ Main Menu",
        
        # Access and errors
        'access_required': "🔒 **Access Required**",
        'join_first': "To get your free MTProxy, you need to join our channel first!",
        'auto_receive': "🎁 **You'll automatically receive your proxy when you join!**",
        'error_membership': "❌ Error checking channel membership. Please try again later.",
        'error_saving': "❌ Error saving your proxy. Please try again.",
        'error_creating': "❌ Error creating proxy. Please try again later.",
        'only_own_proxy': "❌ You can only access your own proxy!",
        'must_join_first': "❌ You must join the channel first!",
        'no_active_proxy': "❌ No active proxy found. Use /menu to create one.",
        
        # Menu and status
        'menu_title': "🎛️ **MTProxy Bot Menu**",
        'menu_welcome': "Welcome {name}! Choose an option:",
        'proxy_status_title': "📊 **Your Proxy Status**",
        'status_active': "✅ **Status:** Active",
        'created_date': "📅 **Created:** {date}",
        'username_label': "👤 **Username:** @{username}",
        'personal_proxy': "🔐 **Your Personal MTProxy:**",
        'tap_to_connect': "📱 **Tap the button below to connect:**",
        
        # Security notices
        'security_notice_title': "⚠️ **Security Notice:**",
        'security_personal': "• This proxy is personal to you",
        'security_no_share': "• Don't share it with others",
        'security_stay_active': "• Stay in the channel to keep it active",
        'use_start_new': "🔄 Use /start to get a new button if needed",
        
        # Notifications
        'proxy_deactivated': "❌ Your MTProxy has been deactivated because you left the channel.\n\nJoin the channel again to automatically get a new proxy!",
        'proxy_ready': "🎉 **Your proxy is ready!**\n\n📱 Tap the button below to connect:",
        'new_proxy_created': "🎉 **New proxy created!**\n\n📱 Tap the button below to connect:",
        
        # Help
        'help_title': "ℹ️ **MTProxy Bot Help**",
        'help_quick_start': "**🚀 Quick Start:**",
        'help_step1': "1. Join our channel",
        'help_step2': "2. You'll automatically get your proxy!",
        'help_commands': "**📱 Commands:**",
        'help_start': "• `/start` - Get your proxy",
        'help_menu': "• `/menu` - Show main menu",
        'help_help': "• `/help` - Show this help",
        'help_security': "**🔒 Security:**",
        'help_unique': "• Each user gets a unique proxy",
        'help_no_share': "• Don't share your proxy with others",
        'help_stay_channel': "• Stay in the channel to keep it active",
        'help_tip_menu': "**💡 Tip:** Use the Menu button next to the text input for easy access!",
        
        # Detailed help
        'detailed_help_title': "ℹ️ **How to Use MTProxy**",
        'detailed_step1': "**Step 1:** Join our channel",
        'detailed_step2': "**Step 2:** Get your proxy automatically or use /menu",
        'detailed_step3': "**Step 3:** Tap 'Connect to Proxy' button",
        'detailed_step4': "**Step 4:** Telegram will ask to use the proxy",
        'detailed_step5': "**Step 5:** Tap 'Connect Proxy' to activate",
        
        # Commands for menu button
        'cmd_start_desc': "🚀 Get your MTProxy",
        'cmd_menu_desc': "🎛️ Show main menu",
        'cmd_help_desc': "ℹ️ How to use MTProxy",
        'cmd_pin_desc': "📌 Pin channel menu (admin)",
        'cmd_unpin_desc': "📌 Unpin all messages (admin)",
        'cmd_restart_proxy_desc': "🔄 Restart MTProxy service (admin)",
        'cmd_reboot_vps_desc': "🚨 Reboot VPS server (admin)",
        'cmd_stats_desc': "📊 Show bot statistics (admin)",
        
        # Admin commands
        'access_denied': "❌ Access denied.",
        'admin_restart_proxy_progress': "🔄 Restarting MTProxy service...",
        'admin_restart_proxy_success': "✅ **MTProxy Restart Successful**\n\n🔄 Service restarted by admin: @{username}\n⏰ Time: {time}\n📊 Status: Active\n\nAll user proxies should be working normally.",
        'admin_restart_proxy_failed': "❌ **MTProxy Restart Failed**\n\n⚠️ Service may not be running properly\n📝 Error details: {error}\n\nPlease check service manually:\n`systemctl status MTProxy`",
        'admin_restart_proxy_timeout': "⏰ **MTProxy Restart Timeout**\n\nThe restart operation timed out. Please check manually:\n`systemctl status MTProxy`",
        'admin_restart_proxy_error': "❌ **MTProxy Restart Error**\n\nUnexpected error: {error}\n\nPlease check service manually:\n`systemctl status MTProxy`",
        'admin_reboot_vps_warning': "⚠️ **DANGEROUS COMMAND - VPS REBOOT**\n\nThis will reboot the entire VPS server!\nAll services will be temporarily unavailable.\n\nTo confirm, use:\n`/reboot_vps CONFIRM`\n\n⚠️ **Use with extreme caution!**",
        'admin_reboot_vps_initiated': "🚨 **VPS REBOOT INITIATED**\n\n👤 Admin: @{username}\n⏰ Time: {time}\n\n⚠️ Server will reboot in 10 seconds...\n🔄 All services will restart automatically\n⏱️ Expected downtime: 2-5 minutes",
        'admin_reboot_vps_now': "🚨 **REBOOTING NOW...**\n\nServer is shutting down.\nBot will be back online after reboot.",
        'admin_reboot_vps_failed': "❌ **Reboot Failed**\n\nError: {error}\n\nPlease check system manually or use:\n`sudo reboot`",
        'admin_reboot_vps_confirm_dialog': "⚠️ **Confirm VPS Reboot**\n\n🚨 This will reboot the entire VPS server!\nAll services will be temporarily unavailable.\n\n⏱️ Expected downtime: 2-5 minutes\n🔄 All services will restart automatically\n\n⚠️ **Use with extreme caution!**",
        'btn_confirm_reboot': "✅ Confirm Reboot",
        'btn_cancel': "❌ Cancel",
        'btn_back': "🔙 Back",
        
        # Menu button text
        'menu_button_text': "Menu",
        
        # Location selection
        'choose_location': "🌍 Choose Server Location",
        'location_title': "🌍 **Select Your Preferred Server Location:**",
        'location_description': "Choose a server location for better connection speed and performance:",
        'location_auto': "🌐 Auto (Best Performance)",
        'location_us': "🇺🇸 United States",
        'location_uk': "🇬🇧 United Kingdom", 
        'location_de': "🇩🇪 Germany",
        'location_nl': "🇳🇱 Netherlands",
        'location_fr': "🇫🇷 France",
        'location_ca': "🇨🇦 Canada",
        'location_sg': "🇸🇬 Singapore",
        'location_jp': "🇯🇵 Japan",
        'location_updated': "✅ **Location updated to {location}!**\n\nYour next proxy will use this location.",
        'current_location': "📍 **Current Location:** {location}",
        'btn_change_location': "🌍 Change Location",
    },
    
    'fa': {
        # Welcome messages
        'welcome_back': "🎉 **خوش آمدید!** پروکسی شما آماده است:",
        'welcome_new': "🎉 **خوش آمدید!** پروکسی شما آماده است:",
        'welcome_auto_back': "🎉 **به کانال خوش آمدید!**\n\nپروکسی شما مجدداً فعال شد:",
        'welcome_auto_new': "🎉 **به کانال خوش آمدید!**\n\nپروکسی رایگان شما آماده است:",
        
        # Instructions
        'how_to_connect': "📱 **نحوه اتصال:**",
        'step_tap_button': "۱. روی دکمه زیر کلیک کنید تا پروکسی خود را دریافت کنید",
        'step_telegram_ask': "۲. تلگرام از شما می‌پرسد که از این پروکسی استفاده کنید",
        'step_connect': "۳. روی 'اتصال پروکسی' کلیک کنید",
        
        # Warnings and tips
        'stay_in_channel': "⚠️ **مهم:** برای فعال نگه داشتن پروکسی در کانال بمانید!",
        'security_notice': "🔒 **امنیت:** پروکسی خود را با دیگران به اشتراک نگذارید!",
        'tip_stay_active': "💡 **نکته:** برای فعال نگه داشتن پروکسی در کانال بمانید!",
        
        # Buttons
        'btn_get_proxy': "🔗 دریافت پروکسی من",
        'btn_connect_proxy': "🔗 اتصال به پروکسی",
        'btn_join_channel': "📢 عضویت در کانال",
        'btn_create_proxy': "🆕 ایجاد پروکسی جدید",
        'btn_proxy_status': "📊 وضعیت پروکسی",
        'btn_help': "ℹ️ راهنما",
        'btn_back_menu': "🔙 بازگشت به منو",
        'btn_main_menu': "🎛️ منوی اصلی",
        
        # Access and errors
        'access_required': "🔒 **دسترسی مورد نیاز**",
        'join_first': "برای دریافت پروکسی رایگان، ابتدا باید در کانال ما عضو شوید!",
        'auto_receive': "🎁 **پس از عضویت، پروکسی را به صورت خودکار دریافت خواهید کرد!**",
        'error_membership': "❌ خطا در بررسی عضویت کانال. لطفاً دوباره تلاش کنید.",
        'error_saving': "❌ خطا در ذخیره پروکسی. لطفاً دوباره تلاش کنید.",
        'error_creating': "❌ خطا در ایجاد پروکسی. لطفاً بعداً تلاش کنید.",
        'only_own_proxy': "❌ شما فقط می‌توانید به پروکسی خود دسترسی داشته باشید!",
        'must_join_first': "❌ ابتدا باید در کانال عضو شوید!",
        'no_active_proxy': "❌ پروکسی فعالی یافت نشد. از /menu برای ایجاد استفاده کنید.",
        
        # Menu and status
        'menu_title': "🎛️ **منوی ربات پروکسی**",
        'menu_welcome': "{name} عزیز خوش آمدید! یک گزینه انتخاب کنید:",
        'proxy_status_title': "📊 **وضعیت پروکسی شما**",
        'status_active': "✅ **وضعیت:** فعال",
        'created_date': "📅 **تاریخ ایجاد:** {date}",
        'username_label': "👤 **نام کاربری:** @{username}",
        'personal_proxy': "🔐 **پروکسی شخصی شما:**",
        'tap_to_connect': "📱 **برای اتصال روی دکمه زیر کلیک کنید:**",
        
        # Security notices
        'security_notice_title': "⚠️ **اطلاعیه امنیتی:**",
        'security_personal': "• این پروکسی مخصوص شماست",
        'security_no_share': "• آن را با دیگران به اشتراک نگذارید",
        'security_stay_active': "• برای فعال نگه داشتن در کانال بمانید",
        'use_start_new': "🔄 از /start برای دریافت دکمه جدید استفاده کنید",
        
        # Notifications
        'proxy_deactivated': "❌ پروکسی شما به دلیل خروج از کانال غیرفعال شد.\n\nمجدداً در کانال عضو شوید تا پروکسی جدید به صورت خودکار دریافت کنید!",
        'proxy_ready': "🎉 **پروکسی شما آماده است!**\n\n📱 برای اتصال روی دکمه زیر کلیک کنید:",
        'new_proxy_created': "🎉 **پروکسی جدید ایجاد شد!**\n\n📱 برای اتصال روی دکمه زیر کلیک کنید:",
        
        # Help
        'help_title': "ℹ️ **راهنمای ربات پروکسی**",
        'help_quick_start': "**🚀 شروع سریع:**",
        'help_step1': "۱. در کانال ما عضو شوید",
        'help_step2': "۲. پروکسی را به صورت خودکار دریافت خواهید کرد!",
        'help_commands': "**📱 دستورات:**",
        'help_start': "• `/start` - دریافت پروکسی",
        'help_menu': "• `/menu` - نمایش منوی اصلی",
        'help_help': "• `/help` - نمایش راهنما",
        'help_security': "**🔒 امنیت:**",
        'help_unique': "• هر کاربر پروکسی منحصر به فرد دریافت می‌کند",
        'help_no_share': "• پروکسی خود را با دیگران به اشتراک نگذارید",
        'help_stay_channel': "• برای فعال نگه داشتن در کانال بمانید",
        'help_tip_menu': "**💡 نکته:** از دکمه منو کنار ورودی متن برای دسترسی آسان استفاده کنید!",
        
        # Detailed help
        'detailed_help_title': "ℹ️ **نحوه استفاده از پروکسی**",
        'detailed_step1': "**مرحله ۱:** در کانال ما عضو شوید",
        'detailed_step2': "**مرحله ۲:** پروکسی را به صورت خودکار دریافت کنید یا از /menu استفاده کنید",
        'detailed_step3': "**مرحله ۳:** روی دکمه 'اتصال به پروکسی' کلیک کنید",
        'detailed_step4': "**مرحله ۴:** تلگرام از شما می‌پرسد که از پروکسی استفاده کنید",
        'detailed_step5': "**مرحله ۵:** روی 'اتصال پروکسی' کلیک کنید تا فعال شود",
        
        # Commands for menu button
        'cmd_start_desc': "🚀 دریافت پروکسی",
        'cmd_menu_desc': "🎛️ نمایش منوی اصلی",
        'cmd_help_desc': "ℹ️ راهنمای استفاده",
        'cmd_pin_desc': "📌 پین منوی کانال (ادمین)",
        'cmd_unpin_desc': "📌 حذف همه پین‌ها (ادمین)",
        'cmd_restart_proxy_desc': "🔄 راه‌اندازی مجدد سرویس پروکسی (ادمین)",
        'cmd_reboot_vps_desc': "🚨 راه‌اندازی مجدد سرور (ادمین)",
        'cmd_stats_desc': "📊 نمایش آمار ربات (ادمین)",
        
        # Admin commands
        'access_denied': "❌ دسترسی مجاز نیست.",
        'admin_restart_proxy_progress': "🔄 در حال راه‌اندازی مجدد سرویس MTProxy...",
        'admin_restart_proxy_success': "✅ **راه‌اندازی مجدد MTProxy موفق**\n\n🔄 سرویس توسط ادمین راه‌اندازی شد: @{username}\n⏰ زمان: {time}\n📊 وضعیت: فعال\n\nهمه پروکسی‌های کاربران باید به طور عادی کار کنند.",
        'admin_restart_proxy_failed': "❌ **راه‌اندازی مجدد MTProxy ناموفق**\n\n⚠️ سرویس ممکن است به درستی کار نکند\n📝 جزئیات خطا: {error}\n\nلطفاً سرویس را به صورت دستی بررسی کنید:\n`systemctl status MTProxy`",
        'admin_restart_proxy_timeout': "⏰ **زمان راه‌اندازی مجدد MTProxy تمام شد**\n\nعملیات راه‌اندازی مجدد زمان زیادی برد. لطفاً به صورت دستی بررسی کنید:\n`systemctl status MTProxy`",
        'admin_restart_proxy_error': "❌ **خطا در راه‌اندازی مجدد MTProxy**\n\nخطای غیرمنتظره: {error}\n\nلطفاً سرویس را به صورت دستی بررسی کنید:\n`systemctl status MTProxy`",
        'admin_reboot_vps_warning': "⚠️ **دستور خطرناک - راه‌اندازی مجدد سرور**\n\nاین عمل کل سرور VPS را راه‌اندازی مجدد می‌کند!\nهمه سرویس‌ها موقتاً غیرفعال خواهند شد.\n\nبرای تأیید، استفاده کنید:\n`/reboot_vps CONFIRM`\n\n⚠️ **با احتیاط کامل استفاده کنید!**",
        'admin_reboot_vps_initiated': "🚨 **راه‌اندازی مجدد سرور آغاز شد**\n\n👤 ادمین: @{username}\n⏰ زمان: {time}\n\n⚠️ سرور در ۱۰ ثانیه راه‌اندازی مجدد خواهد شد...\n🔄 همه سرویس‌ها به صورت خودکار راه‌اندازی خواهند شد\n⏱️ زمان تخمینی قطعی: ۲-۵ دقیقه",
        'admin_reboot_vps_now': "🚨 **در حال راه‌اندازی مجدد...**\n\nسرور در حال خاموش شدن است.\nربات پس از راه‌اندازی مجدد آنلاین خواهد شد.",
        'admin_reboot_vps_failed': "❌ **راه‌اندازی مجدد ناموفق**\n\nخطا: {error}\n\nلطفاً به صورت دستی بررسی کنید یا از دستور زیر استفاده کنید:\n`sudo reboot`",
        'admin_reboot_vps_confirm_dialog': "⚠️ **تأیید راه‌اندازی مجدد سرور**\n\n🚨 این عمل کل سرور VPS را راه‌اندازی مجدد می‌کند!\nهمه سرویس‌ها موقتاً غیرفعال خواهند شد.\n\n⏱️ زمان تخمینی قطعی: ۲-۵ دقیقه\n🔄 همه سرویس‌ها به صورت خودکار راه‌اندازی خواهند شد\n\n⚠️ **با احتیاط کامل استفاده کنید!**",
        'btn_confirm_reboot': "✅ تأیید راه‌اندازی مجدد",
        'btn_cancel': "❌ لغو",
        'btn_back': "🔙 بازگشت",
        
        # Menu button text
        'menu_button_text': "منو",
    }
}

def get_text(key: str, language: str = 'en', **kwargs) -> str:
    """Get translated text for the specified language"""
    if language not in LANGUAGES:
        language = 'en'  # Fallback to English
    
    text = LANGUAGES[language].get(key, LANGUAGES['en'].get(key, f"Missing: {key}"))
    
    # Format with provided arguments
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass  # Ignore missing format arguments
    
    return text