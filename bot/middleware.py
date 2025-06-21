from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Awaitable, Dict

from bot.database.methods.get import get_employee_by_telegram_id


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict], Awaitable],
        event: TelegramObject,
        data: Dict,
    ) -> Awaitable:
        user_id = event.from_user.id
        employee = await get_employee_by_telegram_id(user_id)

        if not employee:
            if hasattr(event, "answer"):
                await event.answer("🔐 Сначала авторизуйтесь!")
            return  # Прерываем цепочку

        data["employee"] = employee  # передаём в хендлер
        return await handler(event, data)
