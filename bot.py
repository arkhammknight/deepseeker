import json
import requests
import sqlite3
from datetime import datetime
import pandas as pd
from sklearn.ensemble import IsolationForest
import time
import numpy as np
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from urllib3.exceptions import InsecureRequestWarning
import urllib3
import os
import asyncio
import logging
from dotenv import load_dotenv
from notifications.telegram_bot import TelegramBot
from notifications.telegram_notifications import TelegramNotifier

# Suppress only the single warning from urllib3 needed.
urllib3.disable_warnings(InsecureRequestWarning)

# Create a session with retry strategy
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=5,  # number of retries
        backoff_factor=1,  # wait 1, 2, 4, 8, 16 seconds between retries
        status_forcelist=[408, 429, 500, 502, 503, 504],  # HTTP status codes to retry on
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# Use the session for all requests
session = create_session()

# Load configuration
with open("config.json", "r") as config_file:
    config = json.load(config_file)

# Constants
DATABASE_NAME = config["database_name"]
CHAIN = config["chain"]
MIN_LIQUIDITY = config["filters"]["min_liquidity"]
EXCLUDED_CHAINS = config["filters"]["excluded_chains"]
MAX_VOLUME_TO_LIQUIDITY_RATIO = config["filters"]["max_volume_to_liquidity_ratio"]
COIN_BLACKLIST = config["blacklist"]["coins"]
DEV_BLACKLIST = config["blacklist"]["devs"]
TELEGRAM_BOT_TOKEN = config["telegram"]["bot_token"]
TELEGRAM_CHAT_ID = config["telegram"]["chat_id"]
SOLANA_RPC_URL = config["solana"]["rpc_url"]

# Analysis Parameters
MIN_PRICE = 0.000001  # Minimum price to consider
MIN_VOLUME_24H = 1000  # Minimum 24h volume in USD
MIN_MARKET_CAP = 100000  # Minimum market cap in USD
PRICE_CHANGE_THRESHOLD = 5  # Minimum price change percentage to trigger alert
VOLUME_SPIKE_THRESHOLD = 2  # Volume increase factor to consider as spike

async def send_telegram_notification(message: str, is_error: bool = False):
    """
    Send a notification to Telegram chat with retry logic.
    """
    try:
        # Initialize Telegram bot
        telegram_bot = TelegramBot(
            token=TELEGRAM_BOT_TOKEN,
            chat_id=TELEGRAM_CHAT_ID
        )
        
        await telegram_bot.setup()
        
        if is_error:
            message = f"⚠️ ERROR: {message}"
        await telegram_bot.send_alert(message)
        
    except Exception as e:
        print(f"Error in send_telegram_notification: {str(e)}")

def get_token_price_history(token_address: str):
    """
    Fetch token price history from Coingecko.
    """
    try:
        url = f"https://api.coingecko.com/api/v3/simple/token_price/solana"
        params = {
            "contract_addresses": token_address,
            "vs_currencies": "usd",
            "include_24hr_change": "true"
        }
        response = session.get(url, params=params, timeout=10, verify=False)
        if response.status_code == 200:
            data = response.json()
            return data.get(token_address.lower(), {})
        return {}
    except Exception as e:
        print(f"Error fetching price history: {str(e)}")
        return {}

def get_token_metadata(token_address: str):
    """
    Fetch additional token metadata from Jupiter API.
    """
    try:
        url = f"https://price.jup.ag/v4/price"
        params = {"ids": token_address}
        response = session.get(url, params=params, timeout=10, verify=False)
        if response.status_code == 200:
            data = response.json()
            return data.get("data", {}).get(token_address, {})
        return {}
    except Exception as e:
        print(f"Error fetching token metadata: {str(e)}")
        return {}

def setup_database(db_name: str):
    """
    Set up the SQLite database for storing token data.
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tokens (
        address TEXT PRIMARY KEY,
        symbol TEXT,
        name TEXT,
        price REAL,
        price_change_24h REAL,
        volume_24h REAL,
        market_cap REAL,
        liquidity REAL,
        holder_count INTEGER,
        timestamp DATETIME
    )
    ''')
    
    conn.commit()
    conn.close()

def save_token_data(token_data: dict, db_name: str):
    """
    Save token data to the database.
    """
    if not token_data:
        return
        
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        INSERT OR REPLACE INTO tokens 
        (address, symbol, name, price, price_change_24h, volume_24h, market_cap, liquidity, holder_count, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            token_data.get("address", ""),
            token_data.get("symbol", ""),
            token_data.get("name", ""),
            token_data.get("price", 0),
            token_data.get("price_change_24h", 0),
            token_data.get("volume_24h", 0),
            token_data.get("market_cap", 0),
            token_data.get("liquidity", 0),
            token_data.get("holder_count", 0),
            datetime.now().isoformat()
        ))
        conn.commit()
    except Exception as e:
        print(f"Error saving token data: {str(e)}")
    finally:
        conn.close()

def get_previous_token_data(token_address: str, db_name: str):
    """
    Get previous token data from database.
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    try:
        cursor.execute('''
        SELECT price, volume_24h, liquidity
        FROM tokens
        WHERE address = ?
        ORDER BY timestamp DESC
        LIMIT 1
        ''', (token_address,))
        result = cursor.fetchone()
        if result:
            return {
                "price": result[0],
                "volume_24h": result[1],
                "liquidity": result[2]
            }
        return None
    finally:
        conn.close()

def analyze_token(token_data: dict, db_name: str) -> tuple[bool, str]:
    """
    Analyze token data for potential opportunities.
    Returns (is_interesting, reason)
    """
    if not token_data:
        return False, ""
        
    try:
        # Basic validation
        required_fields = ["address", "symbol", "price"]
        if not all(field in token_data for field in required_fields):
            return False, "Missing required fields"
            
        # Check blacklist
        if token_data["address"] in COIN_BLACKLIST:
            return False, "Token is blacklisted"
            
        # Get previous data
        prev_data = get_previous_token_data(token_data["address"], db_name)
        
        # Price checks
        price = float(token_data.get("price", 0))
        if price < MIN_PRICE:
            return False, "Price too low"
            
        # Volume checks
        volume_24h = float(token_data.get("volume_24h", 0))
        if volume_24h < MIN_VOLUME_24H:
            return False, "Volume too low"
            
        # Market cap checks
        market_cap = float(token_data.get("market_cap", 0))
        if market_cap < MIN_MARKET_CAP:
            return False, "Market cap too low"
            
        # Price change analysis
        price_change_24h = float(token_data.get("price_change_24h", 0))
        
        # Volume spike analysis
        if prev_data and prev_data["volume_24h"] > 0:
            volume_change = volume_24h / prev_data["volume_24h"]
            if volume_change >= VOLUME_SPIKE_THRESHOLD:
                return True, f"Volume spike detected ({volume_change:.2f}x increase)"
        
        # Significant price change
        if abs(price_change_24h) >= PRICE_CHANGE_THRESHOLD:
            return True, f"Significant price change ({price_change_24h:.2f}%)"
            
        # Additional metadata checks
        metadata = get_token_metadata(token_data["address"])
        if metadata.get("liquidity", 0) > MIN_LIQUIDITY:
            return True, "High liquidity token"
            
        return False, "No significant signals"
        
    except Exception as e:
        print(f"Error analyzing token: {str(e)}")
        return False, f"Analysis error: {str(e)}"

def format_token_message(token: dict, reason: str) -> str:
    """
    Format token data for Telegram message.
    """
    price = float(token.get("price", 0))
    price_change = float(token.get("price_change_24h", 0))
    volume = float(token.get("volume_24h", 0))
    market_cap = float(token.get("market_cap", 0))
    
    emoji = "🚀" if price_change > 0 else "🔻"
    
    return (
        f"🔍 Trading Signal: {reason}\n\n"
        f"Token: {token.get('symbol', 'Unknown')} ({token.get('name', 'Unknown')})\n"
        f"Address: {token.get('address', 'Unknown')}\n"
        f"Price: ${price:.8f}\n"
        f"24h Change: {emoji} {price_change:.2f}%\n"
        f"24h Volume: ${volume:,.2f}\n"
        f"Market Cap: ${market_cap:,.2f}\n"
        f"Liquidity: ${float(token.get('liquidity', 0)):,.2f}\n\n"
        f"🔗 Trade on Jupiter: https://jup.ag/swap/{token.get('address', '')}"
    )

def fetch_solana_token_data():
    """
    Fetch token data from Jupiter API for Solana tokens.
    """
    try:
        # Try multiple endpoints in case one fails
        endpoints = [
            "https://token.jup.ag/all",
            "https://cache.jup.ag/tokens",  # Backup endpoint
            "https://cache.jup.ag/strict-tokens"  # Another backup
        ]
        
        last_error = None
        for endpoint in endpoints:
            try:
                response = session.get(endpoint, timeout=10, verify=False)
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                last_error = e
                continue
        
        if last_error:
            print(f"Error fetching Jupiter token data from all endpoints: {str(last_error)}")
        return None
    except Exception as e:
        print(f"Error in fetch_solana_token_data: {str(e)}")
        return None

async def run_bot():
    """
    Main bot loop that continuously monitors and analyzes Solana tokens.
    """
    print("Starting Solana trading bot...")
    await send_telegram_notification("🚀 Solana trading bot started!\n\nMonitoring for:\n" + 
                             f"- Price changes > {PRICE_CHANGE_THRESHOLD}%\n" +
                             f"- Volume spikes > {VOLUME_SPIKE_THRESHOLD}x\n" +
                             f"- Minimum liquidity: ${MIN_LIQUIDITY:,}\n" +
                             f"- Minimum volume: ${MIN_VOLUME_24H:,}")
    
    consecutive_errors = 0
    while True:
        try:
            # Fetch token data
            print("Fetching Solana token data...")
            tokens_data = fetch_solana_token_data()
            
            if tokens_data and "tokens" in tokens_data:
                consecutive_errors = 0  # Reset error counter on success
                for token in tokens_data["tokens"]:
                    try:
                        # Enrich token data with additional information
                        price_data = get_token_price_history(token.get("address", ""))
                        token.update(price_data)
                        
                        # Save to database
                        save_token_data(token, DATABASE_NAME)
                        
                        # Analyze token
                        is_interesting, reason = analyze_token(token, DATABASE_NAME)
                        if is_interesting:
                            message = format_token_message(token, reason)
                            await send_telegram_notification(message)
                    except Exception as e:
                        print(f"Error processing token {token.get('symbol', 'Unknown')}: {str(e)}")
                        continue
            else:
                consecutive_errors += 1
                error_msg = f"Failed to fetch token data (attempt {consecutive_errors})"
                print(error_msg)
                if consecutive_errors >= 5:  # After 5 consecutive errors
                    await send_telegram_notification(error_msg, is_error=True)
                    consecutive_errors = 0  # Reset counter after notification
            
            # Adaptive sleep based on error count
            sleep_time = min(60 * (2 ** (consecutive_errors - 1)), 300) if consecutive_errors > 0 else 60
            print(f"Sleeping for {sleep_time} seconds...")
            await asyncio.sleep(sleep_time)
            
        except Exception as e:
            error_message = f"Error in bot execution: {str(e)}"
            print(error_message)
            await send_telegram_notification(error_message, is_error=True)
            await asyncio.sleep(60)  # Wait before retrying

def main():
    """Main entry point for the bot."""
    try:
        # Set up logging first
        from config.logging_config import setup_logging
        setup_logging()
        
        # Load configuration
        config = load_config()
        if not validate_config(config):
            logger.error("Invalid configuration. Please check your settings and try again.")
            return

        # Initialize components with secure configuration
        telegram_bot = TelegramBot(
            token=config['telegram']['bot_token'],
            chat_id=config['telegram']['chat_id']
        )
        
        # Continue with rest of initialization...
        setup_database(DATABASE_NAME)
        asyncio.run(run_bot())
        
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()