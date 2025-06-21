# bot/handlers/orders.py

import os

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InputMediaPhoto
from .object_detection import PPEPhotoDetector
from aiogram.types import BufferedInputFile

from bot.database.methods.get import (
    get_document_photos,
    get_employee_by_telegram_id,
    get_user_active_documents,
    get_document_details,
)
from bot.database.methods.update import update_work_status

from bot.database.methods.create import save_document_photo

from bot.keyboards import get_inline_keyboard

router = Router()


detector = PPEPhotoDetector(model_path="yolo11n.pt", confidence_threshold=0.4)


# Состояния для FSM
class WorkOrderStates(StatesGroup):
    waiting_start_photos = State()
    waiting_completion_photos = State()


def get_orders_keyboard(documents: list) -> InlineKeyboardBuilder:
    """
    Создает клавиатуру со списком нарядов

    Args:
        documents: список документов

    Returns:
        InlineKeyboardMarkup: клавиатура с кнопками нарядов
    """
    buttons = []

    # Добавляем кнопку для каждого наряда
    for doc in documents:
        # Формируем текст кнопки: номер наряда + краткое описание
        button_text = f"📄 №{doc['document_number'][:10]}"
        if len(doc["document_number"]) > 10:
            button_text = f"📄 №{doc['document_number'][:10]}..."

        # callback_data содержит префикс и номер документа
        callback_data = f"order_detail:{doc['document_number']}"

        buttons.append((button_text, callback_data))

    # Добавляем кнопку "Назад в меню"
    buttons.append(("🔙 Назад в меню", "back_to_menu"))

    # Размещаем наряды по 1 в строке, а "Назад" отдельно
    sizes = [1] * len(documents) + [1]

    return get_inline_keyboard(*buttons, sizes=tuple(sizes))


@router.callback_query(F.data == "my_orders")
async def show_my_orders(callback: CallbackQuery):
    """Показать список нарядов пользователя"""
    telegram_id = callback.from_user.id

    result = await get_user_active_documents(telegram_id)

    if not result["success"]:
        await callback.message.edit_text(
            f"❌ {result['error']}\n\n"
            "Попробуйте еще раз или обратитесь к администратору.",
            reply_markup=get_inline_keyboard(("🔙 Назад в меню", "back_to_menu")),
        )
        await callback.answer()
        return

    if result["documents_count"] == 0:
        await callback.message.edit_text(
            f"📋 <b>Мои наряды</b>\n\n"
            f"👤 {result['employee_name']}\n\n"
            f"📄 У вас нет действующих нарядов.\n\n"
            f'<i>Действующими считаются наряды со статусом "Ожидание"</i>',
            reply_markup=get_inline_keyboard(("🔙 Назад в меню", "back_to_menu")),
        )
        await callback.answer()
        return

    # Формируем HTML-текст
    text = f"📊 <b>Всего нарядов: {result['documents_count']}</b>\n\n"

    for i, doc in enumerate(result["documents"], 1):
        task_short = doc["task_description"][:50]
        if len(doc["task_description"]) > 50:
            task_short += "..."

        text += (
            f"<b>{i}. 📬Наряд №{doc['document_number']}</b>\n"
            f"⏰ Сроки: {doc['start_datetime']} - {doc['end_datetime']}\n"
            f"📝 Описание: {task_short}\n\n"
        )

    text += "<i>Нажмите на наряд для подробной информации</i>"

    await callback.message.edit_text(
        text,
        reply_markup=get_orders_keyboard(result["documents"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("order_detail:"))
async def show_order_detail(callback: CallbackQuery, state: FSMContext):
    """Показать детальную информацию о наряде"""
    telegram_id = callback.from_user.id

    # Извлекаем номер документа из callback_data
    document_number = callback.data.split(":", 1)[1]

    # Получаем детальную информацию о документе
    result = await get_document_details(document_number, telegram_id)

    if not result["success"]:
        await callback.message.edit_text(
            f"❌ {result['error']}",
            reply_markup=get_inline_keyboard(
                ("🔙 К списку нарядов", "my_orders"),
                ("🏠 Главное меню", "back_to_menu"),
                sizes=(1, 1),
            ),
        )
        await callback.answer()
        return

    doc = result["document"]
    employee = await get_employee_by_telegram_id(telegram_id)

    text = f"📄 Наряд №{doc['document_number']}\n\n"

    # Основная информация
    text += f"🏢 Филиал: {doc['branch']}\n"
    text += f"🏭 Подразделение: {doc['department']}\n"
    text += f"⚙️ Вид работы: {doc['work_type']}\n\n"

    # Описание работ
    text += f"📝 Описание работ:\n{doc['task_description']}\n\n"

    # Участники
    text += f"👥 Участники наряда:\n"
    participants = doc["participants"]

    if participants["supervisor"]:
        text += f"• Руководитель работ: {participants['supervisor']}\n"
    if participants["approver"]:
        text += f"• Допускающий: {participants['approver']}\n"
    if participants["executor"]:
        text += f"• Производитель работ: {participants['executor']}\n"
    if participants["observer"]:
        text += f"• Наблюдающий: {participants['observer']}\n"
    if participants["crew_members"]:
        crew_list = ", ".join(participants["crew_members"])
        text += f"• Члены бригады: {crew_list}\n"

    # Временные рамки
    text += f"\n⏰ Период выполнения:\n"
    text += f"🕐 Начало: {doc['start_datetime']}\n"
    text += f"🕕 Окончание: {doc['end_datetime']}\n"

    # Фактические времена работ
    if doc.get("actual_start_datetime"):
        text += f"🕐 Фактическое начало: {doc['actual_start_datetime']}\n"
    if doc.get("actual_end_datetime"):
        text += f"🕕 Фактическое завершение: {doc['actual_end_datetime']}\n"

    # Статус
    text += f"\n📊 Статус: {doc['status']}\n"

    # Информация о файле
    if doc["file_exists"]:
        text += f"\n📎 К наряду прикреплен файл\n"

    # Даты создания и обновления
    text += f"\n📅 Создан: {doc['created']}"
    if doc["updated"] != doc["created"]:
        text += f"\n📅 Обновлен: {doc['updated']}"

    # Создаем кнопки в зависимости от статуса и роли пользователя
    buttons = []

    # Кнопки для производителя работ
    if employee.role == "executor":
        if doc["status"] == "Создано":
            buttons.append(("🚀 СТАРТ РАБОТ", f"start_work:{document_number}"))
        elif doc["status"] == "В работе":
            buttons.append(("🏁 ЗАВЕРШИТЬ РАБОТЫ", f"complete_work:{document_number}"))

    # Кнопки для руководителя работ (согласование)
    if employee.role == "supervisor":
        if doc["status"] == "Согласование начала":
            buttons.append(
                ("✅ Согласовать начало", f"approve_start:{document_number}")
            )
            buttons.append(("❌ Отклонить", f"reject_start:{document_number}"))
        elif doc["status"] == "Согласование завершения":
            buttons.append(
                ("✅ Согласовать завершение", f"approve_completion:{document_number}")
            )
            buttons.append(("❌ Отклонить", f"reject_completion:{document_number}"))

    # Стандартные кнопки навигации
    buttons.extend(
        [("🔙 К списку нарядов", "my_orders"), ("🏠 Главное меню", "back_to_menu")]
    )

    # Определяем размеры кнопок
    if employee.role in ["executor", "supervisor"] and doc["status"] in [
        "Создано",
        "В работе",
        "Согласование начала",
        "Согласование завершения",
    ]:
        if doc["status"] in ["Согласование начала", "Согласование завершения"]:
            sizes = (2, 1, 1)  # 2 кнопки согласования, потом по 1
        else:
            sizes = (1, 1, 1)  # по 1 кнопке в ряду
    else:
        sizes = (1, 1)

    await callback.message.edit_text(
        text,
        reply_markup=get_inline_keyboard(*buttons, sizes=sizes),
    )
    await callback.answer()


# Обработчик старта работ
@router.callback_query(F.data.startswith("start_work:"))
async def start_work_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик начала работ"""
    document_number = callback.data.split(":", 1)[1]

    await state.set_state(WorkOrderStates.waiting_start_photos)
    await state.update_data(
        document_number=document_number,
        photo_type="start",
    )

    await callback.message.edit_text(
        "📸 Пожалуйста, отправьте фотографии для подтверждения начала работ.",
        reply_markup=get_inline_keyboard(
            ("❌ Отмена", "cancel_photo_upload"),
            sizes=(1,),
        ),
    )
    await callback.answer()


# Обработчик завершения работ
@router.callback_query(F.data.startswith("complete_work:"))
async def complete_work_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик завершения работ"""
    document_number = callback.data.split(":", 1)[1]

    await state.set_state(WorkOrderStates.waiting_completion_photos)
    await state.update_data(
        document_number=document_number,
        photo_type="completion",
    )

    await callback.message.edit_text(
        "📸 Пожалуйста, отправьте фотографии для подтверждения завершения работ.",
        reply_markup=get_inline_keyboard(
            ("❌ Отмена", "cancel_photo_upload"),
            sizes=(1,),
        ),
    )
    await callback.answer()


@router.message(F.photo, WorkOrderStates.waiting_start_photos)
@router.message(F.photo, WorkOrderStates.waiting_completion_photos)
async def handle_work_photos(message: Message, state: FSMContext):
    """Обработчик получения фотографий для работ"""
    data = await state.get_data()
    document_number = data.get("document_number")
    photo_type = data.get("photo_type")
    first_photo = data.get("first_photo", True)
    photos_count = data.get("photos_count", 0)

    # Ограничение на количество фото
    MAX_PHOTOS = 10
    if photos_count >= MAX_PHOTOS:
        await message.answer(f"❌ Превышен лимит фотографий ({MAX_PHOTOS})")
        return

    # Получаем лучшее качество фото
    best_photo = message.photo[-1]

    # Сохраняем фото
    result = await save_document_photo(
        message.bot,
        best_photo.file_id,
        document_number,
        photo_type,
        message.from_user.id,
    )

    if result["success"]:
        photos_count += 1
        await state.update_data(first_photo=False, photos_count=photos_count)

        if first_photo:
            await message.answer(
                f"📸 Фото получено ({photos_count}/{MAX_PHOTOS}). "
                "Когда прикрепите все фотографии, нажмите кнопку ниже.",
                reply_markup=get_inline_keyboard(
                    ("✅ Завершить загрузку", "finish_photo_upload"),
                    ("❌ Отмена", "cancel_photo_upload"),
                    sizes=(1, 1),
                ),
            )
        else:
            await message.answer(f"📸 Фото получено ({photos_count}/{MAX_PHOTOS}).")
    else:
        await message.answer(f"❌ Ошибка сохранения фотографии: {result['error']}")


@router.callback_query(F.data == "finish_photo_upload")
async def finish_photo_upload(callback: CallbackQuery, state: FSMContext):
    """Завершение загрузки фотографий"""
    data = await state.get_data()
    photos_count = data.get("photos_count", 0)
    document_number = data.get("document_number")
    photo_type = data.get("photo_type")

    if photo_type == "start":
        await update_work_status(
            document_number, "pending_start", callback.from_user.id
        )
        text = (
            f"✅ Фотографии для начала работ по документу №{document_number} успешно прикреплены!"
            f"📸 Сохранено {photos_count} фото"
        )
    else:
        await update_work_status(
            document_number, "pending_completion", callback.from_user.id
        )
        text = (
            f"✅ Фотографии для завершения работ по документу №{document_number} успешно прикреплены!"
            f"📸 Сохранено {photos_count} фото"
        )

    await callback.message.edit_text(
        text,
        reply_markup=get_inline_keyboard(
            ("🔙 Вернуться к наряду", f"back_to_order:{document_number}"),
            sizes=(1,),
        ),
    )

    await state.clear()
    await callback.answer()


# Обработчик возврата к наряду
@router.callback_query(F.data.startswith("back_to_order:"))
async def back_to_order_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик возврата к наряду"""
    document_number = callback.data.split(":", 1)[1]

    # Очищаем состояние
    await state.clear()
    await show_order_detail(callback, state)


# Обработчик отмены загрузки фото
@router.callback_query(F.data == "cancel_photo_upload")
async def cancel_photo_upload_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик отмены загрузки фотографий"""
    await callback.message.edit_text("❌ Загрузка фотографий отменена.")
    await state.clear()
    await callback.answer("Загрузка отменена")


# Согласование начала работ
@router.callback_query(F.data.startswith("approve_start:"))
async def handle_approve_start(callback: CallbackQuery, state: FSMContext):
    """Показать фотографии для согласования начала работ"""
    document_number = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id

    # Получаем фотографии начала работ
    photos = await get_document_photos(document_number, "start")

    if not photos:
        await callback.answer("❌ Фотографии не найдены", show_alert=True)
        return

    # Удаляем текущее сообщение
    await callback.message.delete()

    # Создаем медиа группу
    media_group = []
    for photo in photos:
        media_group.append(
            InputMediaPhoto(
                media=photo["file_id"], caption="📸 Фотографии начала работ"
            )
        )

    # Отправляем группу фотографий
    await callback.message.answer_media_group(media=media_group)

    # Отправляем отдельное сообщение с кнопками
    await callback.message.answer(
        f"📄 Согласование начала работ по наряду №{document_number}\n"
        f"📸 Всего фотографий: {len(photos)}",
        reply_markup=get_inline_keyboard(
            ("✅ Согласовать", f"confirm_approve_start:{document_number}"),
            ("❌ Отклонить", f"confirm_reject_start:{document_number}"),
            ("🔬 Анализ СИЗ", f"analyze_ppe_start:{document_number}"),
            ("🔙 К наряду", f"order_detail:{document_number}"),
            sizes=(2, 1, 1),
        ),
    )

    await callback.answer()


# Согласование завершения работ
@router.callback_query(F.data.startswith("approve_completion:"))
async def handle_approve_completion(callback: CallbackQuery, state: FSMContext):
    """Показать фотографии для согласования завершения работ"""
    document_number = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id

    # Получаем фотографии завершения работ
    photos = await get_document_photos(document_number, "completion")

    if not photos:
        await callback.answer("❌ Фотографии не найдены", show_alert=True)
        return

    # Удаляем текущее сообщение
    await callback.message.delete()

    # Создаем медиа группу
    media_group = []
    for photo in photos:
        media_group.append(
            InputMediaPhoto(
                media=photo["file_id"], caption="📸 Фотографии завершения работ"
            )
        )

    # Отправляем группу фотографий
    await callback.message.answer_media_group(media=media_group)

    # Отправляем отдельное сообщение с кнопками
    await callback.message.answer(
        f"📄 Согласование завершения работ по наряду №{document_number}\n"
        f"📸 Всего фотографий: {len(photos)}",
        reply_markup=get_inline_keyboard(
            ("✅ Согласовать", f"confirm_approve_completion:{document_number}"),
            ("❌ Отклонить", f"confirm_reject_completion:{document_number}"),
            ("🔬 Анализ СИЗ", f"analyze_ppe_completion:{document_number}"),
            ("🔙 К наряду", f"order_detail:{document_number}"),
            sizes=(2, 1, 1),
        ),
    )

    await callback.answer()


@router.callback_query(F.data.startswith("analyze_ppe_start:"))
async def analyze_ppe_start(callback: CallbackQuery, state: FSMContext):
    document_number = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id

    # (1) Проверка, что юзер — supervisor (замени на свою проверку)
    employee = await get_employee_by_telegram_id(telegram_id)
    if employee.role != "supervisor":
        await callback.answer("Нет доступа", show_alert=True)
        return

    photos = await get_document_photos(document_number, "start")
    if not photos:
        await callback.answer("❌ Фотографии не найдены", show_alert=True)
        return

    # Показываем пользователю, что анализ начался
    await callback.message.edit_text(
        "🔄 Анализ СИЗ в процессе...\nПожалуйста, подождите."
    )

    verdicts = []
    media_group = []

    for idx, photo in enumerate(photos):
        try:
            # --- Загрузка файла
            # Скачиваем файл из Telegram на диск
            file_info = await callback.bot.get_file(photo["file_id"])

            # Используем file_id вместо несуществующего 'id'
            local_path = f"temp_photo_{idx}_{photo['file_id'][-10:]}.jpg"
            result_path = f"result_{idx}_{photo['file_id'][-10:]}.jpg"

            await callback.bot.download_file(file_info.file_path, local_path)

            # --- Детекция
            result_img, detections, analysis = detector.process_photo(
                local_path, output_path=result_path
            )
            verdict = analysis["safety_status"]

            # Добавим как отдельное фото с подписью
            with open(result_path, "rb") as f:
                buf = BufferedInputFile(f.read(), filename=f"result_{idx}.jpg")
                media_group.append(
                    InputMediaPhoto(
                        media=buf, caption=f"📊 Результат анализа {idx+1}\n{verdict}"
                    )
                )

            verdicts.append(verdict)

        except Exception as e:
            print(f"Ошибка при обработке фото {idx}: {e}")
            verdicts.append("Ошибка обработки")

        finally:
            # --- Очистка временных файлов
            try:
                if os.path.exists(local_path):
                    os.remove(local_path)
                if os.path.exists(result_path):
                    os.remove(result_path)
            except Exception as e:
                print(f"Ошибка при удалении файлов: {e}")

    # Отправляем результат только если есть обработанные фото
    if media_group:
        await callback.message.answer_media_group(media_group)

        # Формируем общий вердикт
        safe_count = sum(
            1
            for v in verdicts
            if "не обнаружено" in v.lower() or "соблюдены" in v.lower()
        )
        total_count = len(verdicts)

        if safe_count == total_count:
            verdict_text = "✅ СИЗ соблюдены на всех фотографиях!"
            verdict_emoji = "✅"
        elif safe_count > 0:
            verdict_text = (
                f"⚠️ СИЗ соблюдены на {safe_count} из {total_count} фотографий"
            )
            verdict_emoji = "⚠️"
        else:
            verdict_text = "❌ Нарушения СИЗ обнаружены на всех фотографиях!"
            verdict_emoji = "❌"

        # Отправляем итоговый вердикт
        await callback.message.answer(
            f"<b>🔬 Результат анализа СИЗ:</b>\n\n"
            f"{verdict_emoji} {verdict_text}\n\n"
            f"📊 Проанализировано фотографий: {total_count}",
            reply_markup=get_inline_keyboard(
                ("🔙 К согласованию", f"approve_start:{document_number}"),
                ("📋 К наряду", f"order_detail:{document_number}"),
                sizes=(2,),
            ),
        )
    else:
        await callback.message.answer(
            "❌ Не удалось обработать ни одной фотографии",
            reply_markup=get_inline_keyboard(
                ("🔙 К согласованию", f"approve_start:{document_number}"), sizes=(1,)
            ),
        )

    await callback.answer()


@router.callback_query(F.data.startswith("analyze_ppe_completion:"))
async def analyze_ppe_completion(callback: CallbackQuery, state: FSMContext):
    document_number = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id

    # (1) Проверка, что юзер — supervisor
    employee = await get_employee_by_telegram_id(telegram_id)
    if employee.role != "supervisor":
        await callback.answer("Нет доступа", show_alert=True)
        return

    photos = await get_document_photos(document_number, "completion")
    if not photos:
        await callback.answer("❌ Фотографии не найдены", show_alert=True)
        return

    # Показываем пользователю, что анализ начался
    await callback.message.edit_text(
        "🔄 Анализ СИЗ в процессе...\nПожалуйста, подождите."
    )

    verdicts = []
    media_group = []

    for idx, photo in enumerate(photos):
        try:
            # --- Загрузка файла
            file_info = await callback.bot.get_file(photo["file_id"])

            # Используем индекс и часть file_id для уникальности
            local_path = f"temp_photo_{idx}_{photo['file_id'][-10:]}.jpg"
            result_path = f"result_{idx}_{photo['file_id'][-10:]}.jpg"

            await callback.bot.download_file(file_info.file_path, local_path)

            # --- Детекция
            result_img, detections, analysis = detector.process_photo(
                local_path, output_path=result_path
            )
            verdict = analysis["safety_status"]

            # Добавим как отдельное фото с подписью
            with open(result_path, "rb") as f:
                buf = BufferedInputFile(f.read(), filename=f"result_{idx}.jpg")
                media_group.append(
                    InputMediaPhoto(
                        media=buf, caption=f"📊 Результат анализа {idx+1}\n{verdict}"
                    )
                )

            verdicts.append(verdict)

        except Exception as e:
            print(f"Ошибка при обработке фото {idx}: {e}")
            verdicts.append("Ошибка обработки")

        finally:
            # --- Очистка временных файлов
            try:
                if os.path.exists(local_path):
                    os.remove(local_path)
                if os.path.exists(result_path):
                    os.remove(result_path)
            except Exception as e:
                print(f"Ошибка при удалении файлов: {e}")

    # Отправляем результат только если есть обработанные фото
    if media_group:
        await callback.message.answer_media_group(media_group)

        # Формируем общий вердикт
        safe_count = sum(
            1
            for v in verdicts
            if "не обнаружено" in v.lower() or "соблюдены" in v.lower()
        )
        total_count = len(verdicts)

        if safe_count == total_count:
            verdict_text = "✅ СИЗ соблюдены на всех фотографиях!"
            verdict_emoji = "✅"
        elif safe_count > 0:
            verdict_text = (
                f"⚠️ СИЗ соблюдены на {safe_count} из {total_count} фотографий"
            )
            verdict_emoji = "⚠️"
        else:
            verdict_text = "❌ Нарушения СИЗ обнаружены на всех фотографиях!"
            verdict_emoji = "❌"

        # Отправляем итоговый вердикт
        await callback.message.answer(
            f"<b>🔬 Результат анализа СИЗ:</b>\n\n"
            f"{verdict_emoji} {verdict_text}\n\n"
            f"📊 Проанализировано фотографий: {total_count}",
            reply_markup=get_inline_keyboard(
                ("🔙 К согласованию", f"approve_completion:{document_number}"),
                ("📋 К наряду", f"order_detail:{document_number}"),
                sizes=(2,),
            ),
        )
    else:
        await callback.message.answer(
            "❌ Не удалось обработать ни одной фотографии",
            reply_markup=get_inline_keyboard(
                ("🔙 К согласованию", f"approve_completion:{document_number}"),
                sizes=(1,),
            ),
        )

    await callback.answer()


# Остальные обработчики подтверждения остаются без изменений
@router.callback_query(F.data.startswith("confirm_approve_start:"))
async def confirm_approve_start(callback: CallbackQuery, state: FSMContext):
    """Подтверждение согласования начала работ"""
    document_number = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id

    # Обновляем статус на "В работе"
    result = await update_work_status(document_number, "in_progress", telegram_id)

    if result["success"]:
        await callback.message.edit_text(
            f"✅ Начало работ по наряду №{document_number} согласовано!\n"
            f"Статус изменен на: В работе",
            reply_markup=get_inline_keyboard(
                ("🔙 К наряду", f"order_detail:{document_number}"),
                ("🏠 Главное меню", "back_to_menu"),
                sizes=(1, 1),
            ),
        )
    else:
        await callback.answer(f"❌ Ошибка: {result['error']}", show_alert=True)


@router.callback_query(F.data.startswith("confirm_approve_completion:"))
async def confirm_approve_completion(callback: CallbackQuery, state: FSMContext):
    """Подтверждение согласования завершения работ"""
    document_number = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id

    # Обновляем статус на "Завершено"
    result = await update_work_status(document_number, "completed", telegram_id)

    if result["success"]:
        await callback.message.edit_text(
            f"✅ Завершение работ по наряду №{document_number} согласовано!\n"
            f"Статус изменен на: Завершено",
            reply_markup=get_inline_keyboard(
                ("🔙 К наряду", f"order_detail:{document_number}"),
                ("🏠 Главное меню", "back_to_menu"),
                sizes=(1, 1),
            ),
        )
    else:
        await callback.answer(f"❌ Ошибка: {result['error']}", show_alert=True)


@router.callback_query(F.data.startswith("confirm_reject_start:"))
async def confirm_reject_start(callback: CallbackQuery, state: FSMContext):
    """Подтверждение отклонения начала работ"""
    document_number = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id

    # Возвращаем статус на "Создано"
    result = await update_work_status(document_number, "created", telegram_id)

    if result["success"]:
        await callback.message.edit_text(
            f"❌ Начало работ по наряду №{document_number} отклонено!\n"
            f"Статус возвращен на: Создано",
            reply_markup=get_inline_keyboard(
                ("🔙 К наряду", f"order_detail:{document_number}"),
                ("🏠 Главное меню", "back_to_menu"),
                sizes=(1, 1),
            ),
        )
    else:
        await callback.answer(f"❌ Ошибка: {result['error']}", show_alert=True)


@router.callback_query(F.data.startswith("confirm_reject_completion:"))
async def confirm_reject_completion(callback: CallbackQuery, state: FSMContext):
    """Подтверждение отклонения завершения работ"""
    document_number = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id

    # Возвращаем статус на "В работе"
    result = await update_work_status(document_number, "in_progress", telegram_id)

    if result["success"]:
        await callback.message.edit_text(
            f"❌ Завершение работ по наряду №{document_number} отклонено!\n"
            f"Статус возвращен на: В работе",
            reply_markup=get_inline_keyboard(
                ("🔙 К наряду", f"order_detail:{document_number}"),
                ("🏠 Главное меню", "back_to_menu"),
                sizes=(1, 1),
            ),
        )
    else:
        await callback.answer(f"❌ Ошибка: {result['error']}", show_alert=True)


# Отмена загрузки фото
@router.callback_query(F.data == "cancel_photo_upload")
async def cancel_photo_upload(callback: CallbackQuery, state: FSMContext):
    """Отмена загрузки фотографий"""
    await state.clear()

    await callback.message.edit_text(
        "❌ Загрузка фотографий отменена.",
        reply_markup=get_inline_keyboard(
            ("🔙 К списку нарядов", "my_orders"),
            ("🏠 Главное меню", "back_to_menu"),
            sizes=(1, 1),
        ),
    )
    await callback.answer()
