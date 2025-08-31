try:
    from telegram import Update
    from telegram.ext import Updater, CommandHandler
    print("✅ Все импорты работают!")
except ImportError as e:
    print(f"❌ Ошибка: {e}")