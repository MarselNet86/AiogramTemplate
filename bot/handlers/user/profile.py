# bot/handlers/auth.py
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
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

from .filters import RoleFilter


router = Router()


class AuthStates(StatesGroup):
    waiting_for_token = State()


def get_main_menu_keyboard():
    """Главное меню для авторизованных пользователей"""
    return get_inline_keyboard(
        ("📬 Мои наряды", "my_orders"),
        ("👤 Профиль", "profile"),
        ("🔑 Мой токен", "my_token"),
        ("🚪 Выйти", "logout"),
        sizes=(2, 1, 1),
    )


def get_back_keyboard():
    """Клавиатура для профиля"""
    return get_inline_keyboard(("🔙 Назад", "back_to_menu"), sizes=(1,))


def get_logout_keyboard():
    """Клавиатура подтверждения выхода"""
    return get_inline_keyboard(
        ("✅ Да, выйти", "confirm_logout"), ("❌ Отмена", "back_to_menu"), sizes=(1, 1)
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Стартовая команда - проверяем авторизацию"""
    telegram_id = message.from_user.id

    # Проверяем, авторизован ли пользователь
    employee = await get_employee_by_telegram_id(telegram_id)

    if employee:
        # Проверяем роль пользователя
        if employee.role not in ("executor", "supervisor"):
            await message.answer(
                "❌ Доступ запрещен!\n\n"
                f"Этот бот доступен только для производителей и руководителей работ.\n"
                f"Ваша роль: {employee.get_role_display()}\n\n"
                f"Обратитесь к администратору для получения доступа."
            )
            return

        # Показываем главное меню
        await message.answer(
            f"👋 Привет, {employee.full_name}!\n"
            f"💼 {employee.position}\n"
            f"⚡ Группа ЭБ: {employee.get_eb_group_display()}\n"
            f"🛡️ Группа ОЗП: {employee.get_ozp_group_display()}\n\n"
            f"Выберите действие:",
            reply_markup=get_main_menu_keyboard(),
        )
    else:
        await message.answer(
            "🔐 Для использования бота необходима авторизация.\n\n"
            f"Отправьте ваш UUID токен доступа:\n"
            f"(Получите его у администратора)\n\n"
            f"⚠️ Внимание: доступ разрешен только производителям и руководителям работ."
        )
        await state.set_state(AuthStates.waiting_for_token)


@router.message(AuthStates.waiting_for_token)
async def process_token(message: Message, state: FSMContext):
    """Обработка UUID токена"""
    token = message.text.strip()
    telegram_id = message.from_user.id

    # Проверяем формат UUID
    try:
        uuid.UUID(token)  # Валидация UUID
    except ValueError:
        await message.answer(
            "❌ Неверный формат токена. UUID должен быть в формате: 12345678-1234-5678-9012-123456789abc"
        )
        return

    # Авторизуем пользователя
    result = await authorize_user_by_uuid(token, telegram_id)

    if result["success"]:
        employee = result["employee"]

        # Проверяем роль после успешной авторизации
        if employee.role not in ("executor", "supervisor"):
            # Отвязываем telegram_id если роль не подходит
            employee.telegram_id = None
            await sync_to_async(employee.save)()

            await message.answer(
                f"❌ Доступ запрещен!\n\n"
                f"Этот бот доступен только для производителей и руководителей работ.\n"
                f"Ваша роль: {employee.get_role_display()}\n\n"
                f"Обратитесь к администратору для получения доступа."
            )
            await state.clear()
            return

        await message.answer(
            f"✅ Авторизация успешна!\n\n"
            f"👤 {employee.full_name}\n"
            f"💼 {employee.position}\n"
            f"⚡ Группа ЭБ: {employee.get_eb_group_display()}\n"
            f"🛡️ Группа ОЗП: {employee.get_ozp_group_display()}\n\n"
            f"Выберите действие:",
            reply_markup=get_main_menu_keyboard(),
        )
        await state.clear()
    else:
        await message.answer(
            f"❌ {result['error']}\n\n"
            f"Попробуйте еще раз или обратитесь к администратору."
        )


# Callback handlers


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    employee = await get_employee_by_telegram_id(telegram_id)

    await callback.message.edit_text(
        f"👋 Привет, {employee.full_name}!\n"
        f"💼 {employee.position}\n"
        f"⚡ Группа ЭБ: {employee.get_eb_group_display()}\n"
        f"🛡️ Группа ОЗП: {employee.get_ozp_group_display()}\n\n"
        f"Выберите действие:",
        reply_markup=get_main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    employee = await get_employee_by_telegram_id(telegram_id)

    await callback.message.edit_text(
        f"👤 **Профиль сотрудника**\n\n"
        f"**ФИО:** {employee.full_name}\n"
        f"**Должность:** {employee.position}\n"
        f"**Группа ЭБ:** {employee.get_eb_group_display()}\n"
        f"**Группа ОЗП:** {employee.get_ozp_group_display()}\n"
        f"**Роль:** {employee.get_role_display()}\n"
        f"**UUID:** `{employee.id}`\n"
        f"**Дата регистрации:** {employee.created.strftime('%d.%m.%Y')}",
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "my_token")
async def show_my_token(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    employee = await get_employee_by_telegram_id(telegram_id)

    await callback.message.edit_text(
        f"🔑 **Ваш токен авторизации:**\n\n"
        f"`{employee.id}`\n\n"
        f"*Не передавайте этот токен другим лицам!*",
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "logout")
async def logout_confirmation(callback: CallbackQuery):
    await callback.message.edit_text(
        "🚪 **Выход из системы**\n\n"
        "Вы уверены, что хотите выйти?\n"
        "После выхода потребуется повторная авторизация.",
        reply_markup=get_logout_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "confirm_logout")
async def confirm_logout(callback: CallbackQuery):
    """Подтвержденный выход из системы"""
    telegram_id = callback.from_user.id

    result = await logout_user(telegram_id)

    if result:
        await callback.message.edit_text(
            "👋 Вы вышли из системы. \n\n"
            "Используйте /start для повторной авторизации."
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при выходе из системы.\n\n"
            "Попробуйте еще раз или обратитесь к администратору.",
            reply_markup=get_back_keyboard(),
        )
    await callback.answer()
