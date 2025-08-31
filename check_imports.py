# check_imports.py
from telegram.ext import *
import telegram.ext
print("Доступные атрибуты в telegram.ext:")
for attr in dir(telegram.ext):
    if not attr.startswith('_'):
        print(f"  {attr}")