from bot.django_setup import *
from users.models import Employee
from orders.models import Document
from asgiref.sync import sync_to_async
from django.db.models import Q
from typing import List, Dict, Optional
from datetime import datetime
from django.utils import timezone


async def update_work_status(
    document_number: str,
    new_status: str,
    telegram_id: int,
    actual_start_time: bool = False,
    actual_end_time: bool = False,
):
    """Обновление статуса работ"""
    try:
        # Получаем документ с предзагрузкой связанных объектов
        document = await sync_to_async(
            Document.objects.select_related("executor", "supervisor").get
        )(document_number=document_number)

        employee = await sync_to_async(Employee.objects.get)(telegram_id=telegram_id)

        # Проверка прав - сравниваем по ID, чтобы избежать дополнительных запросов
        if (
            new_status in ["pending_start", "pending_completion"]
            and document.executor_id != employee.id
        ):
            return {"success": False, "error": "Нет прав для изменения статуса"}

        if (
            new_status in ["in_progress", "completed"]
            and document.supervisor_id != employee.id
        ):
            return {"success": False, "error": "Нет прав для согласования"}

        # Обновляем поля документа
        if actual_start_time:
            document.actual_start_datetime = timezone.now()

        if actual_end_time:
            document.actual_end_datetime = timezone.now()

        document.status = new_status

        # Сохраняем документ асинхронно
        await sync_to_async(document.save)()

        return {"success": True}

    except Document.DoesNotExist:
        return {"success": False, "error": "Документ не найден"}
    except Employee.DoesNotExist:
        return {"success": False, "error": "Сотрудник не найден"}
    except Exception as e:
        return {"success": False, "error": str(e)}
