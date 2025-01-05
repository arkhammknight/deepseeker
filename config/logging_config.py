"""
Logging configuration module.
"""
import logging
import logging.handlers
import os
from pathlib import Path
from typing import List, Pattern
import re

class SensitiveDataFilter(logging.Filter):
    """Filter to redact sensitive data from logs."""
    
    def __init__(self):
        super().__init__()
        # Patterns to match sensitive data
        self.patterns: List[Pattern] = [
            re.compile(r'token=[\w-]+:[\w-]+'),  # Telegram tokens
            re.compile(r'chat_id=\d+'),          # Chat IDs
            re.compile(r'api_key=[\w-]+'),       # API keys
            re.compile(r'secret=[\w-]+'),        # API secrets
            re.compile(r'passphrase=[\w-]+'),    # Passphrases
        ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log records to redact sensitive information.
        
        Args:
            record: The log record
            
        Returns:
            bool: Always True (allows the record through with modifications)
        """
        if isinstance(record.msg, str):
            msg = record.msg
            for pattern in self.patterns:
                msg = pattern.sub('[REDACTED]', msg)
            record.msg = msg
        return True

def setup_logging():
    """Configure logging with sensitive data filtering."""
    
    # Create logs directory if it doesn't exist
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Console handler with sensitive data filter
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.addFilter(SensitiveDataFilter())
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with sensitive data filter
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / 'bot.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_handler.addFilter(SensitiveDataFilter())
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Set third-party loggers to WARNING to reduce noise
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    
    # Log startup message
    root_logger.info('Logging system initialized')
