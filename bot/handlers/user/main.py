from aiogram import Dispatcher
from bot.handlers.user import register

def register_user_handlers(dp: Dispatcher):
    dp.include_router(register.router)

