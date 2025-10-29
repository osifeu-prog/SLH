from telegram import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    rows = [
        [KeyboardButton("💳 Set Wallet"), KeyboardButton("📊 Balance")],
        [KeyboardButton("💸 Send")]
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)
