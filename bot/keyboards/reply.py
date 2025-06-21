from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def cancel_fsm():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def get_keyboard(
    *buttons: str,
    placeholder: str = None,
    request_contact: bool = False,  # Изменено с int на bool
    request_location: bool = False,  # Изменено с int на bool
    sizes: tuple[int] = (2,)
):
    keyboard = ReplyKeyboardBuilder()

    for index, text in enumerate(buttons):
        if request_contact:
            keyboard.add(KeyboardButton(text=text, request_contact=True))
            request_contact = False  # Добавить только одну кнопку для отправки контакта
        elif request_location:
            keyboard.add(KeyboardButton(text=text, request_location=True))
            request_location = False  # Добавить только одну кнопку для отправки локации
        else:
            keyboard.add(KeyboardButton(text=text))

    return keyboard.adjust(*sizes).as_markup(
        resize_keyboard=True, input_field_placeholder=placeholder
    )
