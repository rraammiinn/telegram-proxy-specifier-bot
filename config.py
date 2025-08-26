import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    _RAW_CHANNEL_ID = os.getenv('CHANNEL_ID')
    ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0))  # Admin user ID
    BOT_LANGUAGE = os.getenv('BOT_LANGUAGE', 'en')  # Default to English
    VPS_HOST = os.getenv('VPS_HOST', 'localhost')  # Default to localhost
    VPS_USER = os.getenv('VPS_USER', 'root')
    SSH_KEY_PATH = os.getenv('SSH_KEY_PATH')
    MTPROXY_PATH = os.getenv('MTPROXY_PATH', '/opt/mtproto-proxy')
    MTPROXY_PORT = int(os.getenv('MTPROXY_PORT', 443))
    
    @classmethod
    def _normalize_channel_id(cls, channel_id: str) -> str:
        """
        Normalize channel ID to @username format from various input formats:
        - https://t.me/channel_name -> @channel_name
        - t.me/channel_name -> @channel_name  
        - @channel_name -> @channel_name
        - channel_name -> @channel_name
        - -1001234567890 -> -1001234567890 (numeric IDs stay as-is)
        """
        if not channel_id:
            return channel_id
            
        channel_id = channel_id.strip()
        
        # If it's already a numeric ID (starts with - and contains only digits)
        if channel_id.startswith('-') and channel_id[1:].isdigit():
            return channel_id
            
        # Remove https:// or http:// prefix
        if channel_id.startswith(('https://', 'http://')):
            channel_id = channel_id.split('://', 1)[1]
            
        # Remove t.me/ prefix
        if channel_id.startswith('t.me/'):
            channel_id = channel_id[5:]
            
        # Remove @ prefix if present (we'll add it back)
        if channel_id.startswith('@'):
            channel_id = channel_id[1:]
            
        # Add @ prefix for username format
        return f'@{channel_id}'
    
    @property
    def CHANNEL_ID(self) -> str:
        """Get normalized channel ID"""
        return self._normalize_channel_id(self._RAW_CHANNEL_ID)
    
    @property 
    def CHANNEL_USERNAME(self) -> str:
        """Get channel username without @ prefix for URL generation"""
        channel_id = self.CHANNEL_ID
        if channel_id and channel_id.startswith('@'):
            return channel_id[1:]
        return channel_id
    
    @classmethod
    def validate(cls):
        # Check required config
        if not cls.BOT_TOKEN:
            raise ValueError("Missing required config: BOT_TOKEN")
            
        if not cls._RAW_CHANNEL_ID:
            raise ValueError("Missing required config: CHANNEL_ID")
            
        # Only require SSH config if not running locally
        if cls.VPS_HOST not in ['localhost', '127.0.0.1', None, '']:
            missing = []
            if not cls.VPS_HOST:
                missing.append('VPS_HOST')
            if not cls.SSH_KEY_PATH:
                missing.append('SSH_KEY_PATH')
            if missing:
                raise ValueError(f"Missing required config for remote execution: {', '.join(missing)}")
        
        # Validate channel ID format
        try:
            normalized = cls._normalize_channel_id(cls._RAW_CHANNEL_ID)
            if not normalized:
                raise ValueError("CHANNEL_ID cannot be empty after normalization")
        except Exception as e:
            raise ValueError(f"Invalid CHANNEL_ID format '{cls._RAW_CHANNEL_ID}': {e}")