from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject


class RoleFilter(BaseFilter):
    def __init__(self, *roles: str):
        self.roles = set(roles)

    async def __call__(self, event: TelegramObject, employee=None) -> bool:
        if not employee:
            return False
        return employee.role in self.roles
