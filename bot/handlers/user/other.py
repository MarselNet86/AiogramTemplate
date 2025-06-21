# bot/handlers/auth.py
from aiogram import F, Router
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from asgiref.sync import sync_to_async
import uuid
from bot.keyboards import get_inline_keyboard

from bot.database.methods.get import (
    get_employee_by_telegram_id,
    authorize_user_by_uuid,
    logout_user,
)


router = Router()


def get_main_menu_keyboard():
    """Главное меню для авторизованных пользователей"""
    return get_inline_keyboard(
        ("📬 Мои наряды", "my_orders"),
        ("👤 Профиль", "profile"),
        ("🔑 Мой токен", "my_token"),
        ("🚪 Выйти", "logout"),
        sizes=(2, 1, 1),
    )


@router.message(F.text)
async def handle_unauthorized_message(message: Message):
    """Обработка сообщений от неавторизованных пользователей или не-executor'ов"""
    telegram_id = message.from_user.id
    employee = await get_employee_by_telegram_id(telegram_id)

    if not employee:
        await message.answer(
            "🔐 Для использования бота необходима авторизация.\n"
            "Используйте команду /start для начала."
        )
    elif employee.role not in ("executor", "supervisor"):
        await message.answer(
            "❌ Доступ запрещен!\n\n"
            f"Этот бот доступен только для производителей работ (executor).\n"
            f"Ваша роль: {employee.get_role_display()}"
        )

    else:
        await message.answer(
            f"👋 Привет, {employee.full_name}!\n"
            f"💼 {employee.position}\n"
            f"⚡ Группа ЭБ: {employee.get_eb_group_display()}\n"
            f"🛡️ Группа ОЗП: {employee.get_ozp_group_display()}\n\n",
            reply_markup=get_main_menu_keyboard(),
        )
