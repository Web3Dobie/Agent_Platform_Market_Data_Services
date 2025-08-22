# services/telegram_notifier.py
"""
Enhanced Safe Telegram notifier for Market Data Service
Step 1: Add robust markdown handling while maintaining simplicity
"""
import logging
import requests
import re
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

try:
    from config.settings import settings
    BOT_TOKEN = settings.tg_bot_token
    CHAT_ID = settings.tg_chat_id
except (ImportError, AttributeError):
    # Fallback to environment
    import os
    BOT_TOKEN = os.getenv('TG_BOT_TOKEN')
    CHAT_ID = os.getenv('TG_CHAT_ID')

logger = logging.getLogger(__name__)

class NotificationLevel(Enum):
    """Notification levels with emojis"""
    INFO = "ℹ️"
    SUCCESS = "✅"
    WARNING = "⚠️"
    ERROR = "❌"
    START = "🚀"
    HEARTBEAT = "💓"

def escape_markdown_v2(text: str) -> str:
    """
    Safely escape text for Telegram MarkdownV2
    Handles all special characters that can break parsing
    """
    if not text:
        return ""
    
    # Convert to string and escape special MarkdownV2 characters
    text = str(text)
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def build_safe_message(emoji: str, title: str, body: Optional[str] = None, 
                      fields: Optional[Dict[str, Any]] = None) -> str:
    """
    Build a safely formatted message for Telegram
    Uses MarkdownV2 with proper escaping
    """
    parts = []
    
    # Add header with timestamp
    timestamp = datetime.now().strftime('%H:%M:%S')
    header = f"{emoji} *{escape_markdown_v2(timestamp)}* \\| *{escape_markdown_v2(title)}*"
    parts.append(header)
    
    # Add body if provided
    if body:
        parts.append(escape_markdown_v2(body))
    
    # Add fields if provided  
    if fields:
        for key, value in fields.items():
            safe_key = escape_markdown_v2(str(key))
            safe_value = escape_markdown_v2(str(value))
            parts.append(f"📊 {safe_key}: {safe_value}")
    
    return "\n".join(parts)

class MarketDataTelegramNotifier:
    """Enhanced but safe Telegram notifier"""
    
    def __init__(self):
        self.enabled = bool(BOT_TOKEN and CHAT_ID)
        self.base_url = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None
        self.total_requests = 0
        self.failed_requests = 0
        
        # Validate configuration on startup
        if self.enabled:
            self._validate_setup()
        else:
            logger.warning("⚠️ Telegram notifications disabled - missing TG_BOT_TOKEN or TG_CHAT_ID")
    
    def _validate_setup(self) -> bool:
        """Validate Telegram bot setup"""
        try:
            # Check chat_id format
            if not str(CHAT_ID).lstrip('-').isdigit():
                logger.error(f"❌ Invalid chat_id format: {CHAT_ID}")
                self.enabled = False
                return False
            
            logger.info("✅ Enhanced Telegram notifications enabled for Market Data Service")
            return True
            
        except Exception as e:
            logger.error(f"❌ Telegram setup validation failed: {e}")
            self.enabled = False
            return False
    
    def send_message(self, message: str, level: NotificationLevel = NotificationLevel.INFO) -> bool:
        """
        Send message with automatic fallback handling
        Tries MarkdownV2 first, falls back to plain text
        """
        if not self.enabled:
            logger.debug(f"Telegram disabled - would send {level.name}: {message[:50]}...")
            return False
        
        self.total_requests += 1
        
        # Try MarkdownV2 first
        if self._send_with_markdown(message):
            return True
        
        # Fallback to plain text
        logger.warning("⚠️ MarkdownV2 failed, using plain text fallback")
        return self._send_plain_text(message, level)
    
    def _send_with_markdown(self, message: str) -> bool:
        """Try sending with MarkdownV2 formatting"""
        try:
            payload = {
                'chat_id': CHAT_ID,
                'text': message,
                'parse_mode': 'MarkdownV2',
                'disable_web_page_preview': True
            }
            
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.debug("✅ MarkdownV2 message sent successfully")
                return True
            else:
                logger.debug(f"⚠️ MarkdownV2 failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.debug(f"⚠️ MarkdownV2 exception: {e}")
            return False
    
    def _send_plain_text(self, message: str, level: NotificationLevel) -> bool:
        """Send as plain text (guaranteed to work)"""
        try:
            # Strip markdown and add emoji
            plain_message = re.sub(r'[*_`\[\]()~>#+=|{}.!\\-]', '', message)
            plain_message = f"{level.value} {plain_message}"
            
            payload = {
                'chat_id': CHAT_ID,
                'text': plain_message,
                'disable_web_page_preview': True
            }
            
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.debug("✅ Plain text fallback sent successfully")
                return True
            else:
                self.failed_requests += 1
                logger.error(f"❌ Plain text also failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.failed_requests += 1
            logger.error(f"❌ Plain text fallback error: {e}")
            return False
    
    def notify_startup(self, host: str, port: int, providers: List[str]) -> bool:
        """Send enhanced startup notification"""
        try:
            message = build_safe_message(
                emoji=NotificationLevel.START.value,
                title="Market Data Service Started",
                fields={
                    "🌍 Endpoint": f"{host}:{port}",
                    "📊 Providers": f"{len(providers)} active",
                    "🔧 Provider List": ", ".join(providers[:3]) + ("..." if len(providers) > 3 else "")
                }
            )
            
            return self.send_message(message, NotificationLevel.START)
            
        except Exception as e:
            logger.error(f"❌ Error building startup notification: {e}")
            # Simple fallback
            simple_msg = f"🚀 Market Data Service Started - {len(providers)} providers on {host}:{port}"
            return self._send_plain_text(simple_msg, NotificationLevel.START)
    
    def notify_error(self, component: str, error: str) -> bool:
        """Send enhanced error notification"""
        try:
            # Truncate long errors
            safe_error = error[:200] + "..." if len(error) > 200 else error
            
            message = build_safe_message(
                emoji=NotificationLevel.ERROR.value,
                title=f"Error in {component}",
                body=safe_error
            )
            
            return self.send_message(message, NotificationLevel.ERROR)
            
        except Exception as e:
            logger.error(f"❌ Error building error notification: {e}")
            # Simple fallback
            simple_msg = f"❌ Error in {component}: {error[:100]}"
            return self._send_plain_text(simple_msg, NotificationLevel.ERROR)
    
    def notify_health_issue(self, status: str, details: str = "") -> bool:
        """Send enhanced health issue notification"""
        try:
            fields = {"🔍 Status": status}
            if details:
                fields["💡 Details"] = details
            
            message = build_safe_message(
                emoji=NotificationLevel.WARNING.value,
                title="Health Check Issue",
                fields=fields
            )
            
            return self.send_message(message, NotificationLevel.WARNING)
            
        except Exception as e:
            logger.error(f"❌ Error building health notification: {e}")
            # Simple fallback
            simple_msg = f"⚠️ Health Issue: {status} - {details}"
            return self._send_plain_text(simple_msg, NotificationLevel.WARNING)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get notifier statistics"""
        success_rate = 0
        if self.total_requests > 0:
            success_rate = ((self.total_requests - self.failed_requests) / self.total_requests * 100)
        
        return {
            "enabled": self.enabled,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "success_rate": f"{success_rate:.1f}%",
            "version": "enhanced_safe_v1.0",
            "features": {
                "markdown_v2": True,
                "automatic_fallback": True,
                "safe_escaping": True
            }
        }

# Global instance
_notifier = None

def get_notifier() -> MarketDataTelegramNotifier:
    """Get global notifier instance"""
    global _notifier
    if _notifier is None:
        _notifier = MarketDataTelegramNotifier()
    return _notifier

# Convenience functions
def notify_startup(host: str, port: int, providers: List[str]) -> bool:
    """Send startup notification"""
    return get_notifier().notify_startup(host, port, providers)

def notify_error(component: str, error: str) -> bool:
    """Send error notification"""
    return get_notifier().notify_error(component, error)

def notify_health_issue(status: str, details: str = "") -> bool:
    """Send health issue notification"""
    return get_notifier().notify_health_issue(status, details)