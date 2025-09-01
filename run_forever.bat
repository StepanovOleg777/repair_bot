@echo off
chcp 65001 >nul
title 🤖 Repair Bot 24/7

:start
echo [%date% %time%] Запускаем бота...
python bot.py

echo [%date% %time%] Бот остановился, перезапуск через 10 секунд...
timeout /t 10 /nobreak
goto start