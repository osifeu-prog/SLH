from telegram import ReplyKeyboardMarkup

def main_menu():
    kb = [
        ["💳 הזנת MetaMask", "📊 יתרה"],
        ["💸 העברה", "🧱 בניית עסקה"],
        ["ℹ️ עזרה"]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=False, is_persistent=True)
