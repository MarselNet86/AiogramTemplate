from aiogram import F, Router
from aiogram.types import Message
from aiogram.filters import CommandStart

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Привет, белая задница!")


@router.message()  # Обрабатывает все сообщения
async def handle_all_messages(message: Message):
    await message.answer(
        "Я получил твое сообщение, но не знаю, что с ним делать. Напиши /start!"
    )
