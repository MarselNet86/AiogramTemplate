from aiogram import Dispatcher
from bot.handlers.user import profile, orders, other

def register_user_handlers(dp: Dispatcher):
    dp.include_router(profile.router)
    dp.include_router(orders.router)
    dp.include_router(other.router)

