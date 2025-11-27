# set_bot_commands.py
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault


async def set_bot_commands(bot: Bot):
    """Установка команд меню бота"""
    commands = [
        BotCommand(command="start", description="Рестрат бота"),
    ]

    await bot.set_my_commands(commands, BotCommandScopeDefault())

async def remove_bot_commands(bot: Bot):
    """Удаление команд меню бота"""
    await bot.delete_my_commands(BotCommandScopeDefault())
