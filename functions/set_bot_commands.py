# set_bot_commands.py
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault


async def set_bot_commands(bot: Bot):
    """Установка команд меню бота"""
    commands = [
        BotCommand(command="start", description="Запуск/регистрация бота"),
        BotCommand(command="help", description="Помощь и инструкции"),
        BotCommand(command="funnel", description="📊 Воронка продаж (меню)"),
        BotCommand(command="yesterday", description="📅 Отчет за вчера"),
        BotCommand(command="products", description="📦 Управление продуктами"),
        BotCommand(command="settings", description="⚙️ Настройки магазинов"),
        BotCommand(command="reports", description="📁 Мои отчеты"),
    ]

    await bot.set_my_commands(commands, BotCommandScopeDefault())


async def remove_bot_commands(bot: Bot):
    """Удаление команд меню бота"""
    await bot.delete_my_commands(BotCommandScopeDefault())
