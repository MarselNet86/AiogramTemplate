from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton


def get_inline_keyboard(
    *buttons, sizes: tuple[int] = (1,)  # Может быть строка, tuple или dict
):
    """
    Билдер инлайн-клавиатуры для Aiogram

    Args:
        *buttons: Кнопки в различных форматах:
            - str: текст кнопки (callback_data = текст)
            - tuple: (текст, callback_data)
            - dict: {"text": "текст", "callback_data": "данные"} или
                   {"text": "текст", "url": "ссылка"}
        sizes: tuple размеров строк (по умолчанию (1,) - по одной кнопке в строке)

    Returns:
        InlineKeyboardMarkup: готовая инлайн-клавиатура
    """
    keyboard = InlineKeyboardBuilder()

    for button in buttons:
        if isinstance(button, str):
            # Простая кнопка: текст = callback_data
            keyboard.add(InlineKeyboardButton(text=button, callback_data=button))

        elif isinstance(button, tuple) and len(button) == 2:
            # Кнопка с отдельным callback_data: (текст, callback_data)
            text, callback_data = button
            keyboard.add(InlineKeyboardButton(text=text, callback_data=callback_data))

        elif isinstance(button, dict):
            # Кнопка из словаря
            if "url" in button:
                # URL-кнопка
                keyboard.add(
                    InlineKeyboardButton(text=button["text"], url=button["url"])
                )
            elif "callback_data" in button:
                # Callback-кнопка
                keyboard.add(
                    InlineKeyboardButton(
                        text=button["text"], callback_data=button["callback_data"]
                    )
                )
            else:
                # Если нет url или callback_data, используем text как callback_data
                keyboard.add(
                    InlineKeyboardButton(
                        text=button["text"],
                        callback_data=button.get("callback_data", button["text"]),
                    )
                )

        else:
            raise ValueError(f"Неподдерживаемый формат кнопки: {button}")

    return keyboard.adjust(*sizes).as_markup()
