import requests
import json

def get_telegram_updates(bot_token):
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data["ok"] and data["result"]:
            # Get the most recent message
            latest_update = data["result"][-1]
            chat_id = latest_update["message"]["chat"]["id"]
            username = latest_update["message"]["chat"]["username"]
            print(f"\nFound chat ID: {chat_id}")
            print(f"Username: {username}")
            return chat_id
        else:
            print("\nNo messages found. Please:")
            print("1. Open Telegram")
            print("2. Find your bot by username")
            print("3. Send a message to your bot")
            print("4. Run this script again")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
    return None

if __name__ == "__main__":
    # Load config to get bot token
    with open("config.json", "r") as config_file:
        config = json.load(config_file)
    
    bot_token = config["telegram"]["bot_token"]
    chat_id = get_telegram_updates(bot_token)
    
    if chat_id:
        print("\nTo update your config.json, set your chat_id to:", chat_id)
