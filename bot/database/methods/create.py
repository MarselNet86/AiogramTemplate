# Django и асинхронная инициализация
from bot.django_setup import *  # настройка Django окружения

# Django ORM-модели
from users.models import Employee
from orders.models import Document, DocumentPhoto

# Django утилиты
from django.core.files.base import ContentFile
from django.db.models import Q
from django.utils import timezone

# Асинхронный доступ к синхронному ORM
from asgiref.sync import sync_to_async

# Типизация
from typing import List, Dict, Optional

# Работа с датой
from datetime import datetime

# Aiogram
from aiogram import Bot


async def save_document_photo(
    bot: Bot, file_id: str, document_number: str, photo_type: str, telegram_id: int
):
    """Сохранение фотографии документа с file_id"""
    try:
        # Проверяем, не сохранена ли уже эта фотография
        existing_photo = await sync_to_async(
            DocumentPhoto.objects.filter(file_id=file_id).exists
        )()
        if existing_photo:
            return {"success": False, "error": "Фотография уже была загружена"}

        # Получаем файл от Telegram
        file = await bot.get_file(file_id)
        file_path = file.file_path

        # Скачиваем файл
        file_content = await bot.download_file(file_path)

        # Прочитать файл СИНХРОННО
        content = await sync_to_async(file_content.read)()

        # Находим документ и сотрудника
        document = await sync_to_async(Document.objects.get)(
            document_number=document_number
        )
        employee = await sync_to_async(Employee.objects.get)(telegram_id=telegram_id)

        # Создаем уникальное имя файла
        file_extension = file_path.split(".")[-1] if "." in file_path else "jpg"
        filename = f"{document_number}_{photo_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"

        # Создаем объект DocumentPhoto
        photo = DocumentPhoto(
            document=document,
            photo_type=photo_type,
            uploaded_by=employee,
            file_id=file_id,  # Сохраняем file_id
        )

        # Сохраняем файл (это строго синхронно)
        await sync_to_async(photo.photo.save)(filename, ContentFile(content), save=True)

        return {"success": True, "photo_id": photo.id, "filename": filename}

    except Document.DoesNotExist:
        return {"success": False, "error": f"Документ {document_number} не найден"}
    except Employee.DoesNotExist:
        return {"success": False, "error": "Сотрудник не найден"}
    except Exception as e:
        return {"success": False, "error": str(e)}
