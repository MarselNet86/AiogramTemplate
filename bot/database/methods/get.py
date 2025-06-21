from bot.django_setup import *
from users.models import Employee
from orders.models import Document, DocumentPhoto
from asgiref.sync import sync_to_async
from django.db.models import Q
from typing import List, Dict, Optional
from datetime import datetime


# Вспомогательные функции
async def get_employee_by_telegram_id(telegram_id: int):
    """Получить сотрудника по Telegram ID"""
    try:
        return await sync_to_async(Employee.objects.get)(telegram_id=telegram_id)
    except Employee.DoesNotExist:
        return None


async def authorize_user_by_uuid(uuid_token: str, telegram_id: int):
    """Авторизация по UUID"""
    try:
        # Ищем сотрудника по UUID
        employee = await sync_to_async(Employee.objects.get)(id=uuid_token)

        # Проверяем, не привязан ли уже к другому Telegram
        if employee.telegram_id and employee.telegram_id != telegram_id:
            return {
                "success": False,
                "error": "Этот токен уже привязан к другому Telegram аккаунту.",
            }

        # Привязываем Telegram ID к сотруднику
        employee.telegram_id = telegram_id
        await sync_to_async(employee.save)()

        return {"success": True, "employee": employee}

    except Employee.DoesNotExist:
        return {"success": False, "error": "Неверный токен доступа."}
    except Exception as e:
        return {"success": False, "error": f"Ошибка авторизации: {str(e)}"}


async def logout_user(telegram_id: int):
    """Выход из системы"""
    try:
        employee = await sync_to_async(Employee.objects.get)(telegram_id=telegram_id)
        employee.telegram_id = None
        await sync_to_async(employee.save)()
        return True
    except Employee.DoesNotExist:
        return False
    except Exception:
        return False


async def get_user_active_documents(telegram_id: int) -> Dict:
    """
    Получить все действующие наряды пользователя по его Telegram ID
    Право просмотра имеют только executor и supervisor

    Args:
        telegram_id (int): Telegram ID пользователя

    Returns:
        Dict: Словарь с результатом операции
    """
    try:
        # Находим сотрудника по Telegram ID
        employee = await get_employee_by_telegram_id(telegram_id)
        if not employee:
            return {
                "success": False,
                "error": "Пользователь не найден. Необходима авторизация.",
                "documents": [],
            }

        # Получаем все документы где пользователь является supervisor или executor
        # и статус документа "pending" (действующие)
        documents = await sync_to_async(list)(
            Document.objects.filter(
                (
                    Q(supervisor=employee)  # Руководитель работ
                    | Q(executor=employee)  # Производитель работ
                )
            )
            .distinct()
            .select_related("supervisor", "approver", "executor", "observer")
            .prefetch_related("crew_members")
        )

        # Формируем детальную информацию о документах
        documents_data = []
        for doc in documents:
            # Определяем роль пользователя в документе (только supervisor и executor)
            user_roles = []
            if doc.supervisor_id == employee.id:
                user_roles.append("Руководитель работ")
            if doc.executor_id == employee.id:
                user_roles.append("Производитель работ")

            # Получаем список всех участников для отображения
            crew_members = await sync_to_async(list)(doc.crew_members.all())

            # Получаем список всех участников
            crew_names = [member.full_name for member in crew_members]

            doc_data = {
                "id": doc.id,
                "document_number": doc.document_number,
                "branch": doc.get_branch_display(),
                "department": doc.get_department_display(),
                "work_type": doc.get_work_type_display(),
                "task_description": doc.task_description,
                "start_datetime": doc.start_datetime.strftime("%d.%m.%Y %H:%M"),
                "end_datetime": doc.end_datetime.strftime("%d.%m.%Y %H:%M"),
                "status": doc.get_status_display(),
                "created": doc.created.strftime("%d.%m.%Y %H:%M"),
                "user_roles": user_roles,  # Роли текущего пользователя
                "participants": {
                    "supervisor": doc.supervisor.full_name if doc.supervisor else None,
                    "approver": doc.approver.full_name if doc.approver else None,
                    "executor": doc.executor.full_name if doc.executor else None,
                    "observer": doc.observer.full_name if doc.observer else None,
                    "crew_members": crew_names,
                },
                "file_exists": bool(doc.file),
            }
            documents_data.append(doc_data)

        return {
            "success": True,
            "employee_name": employee.full_name,
            "documents_count": len(documents_data),
            "documents": documents_data,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Ошибка при получении нарядов: {str(e)}",
            "documents": [],
        }


async def get_user_documents_by_role(telegram_id: int, role: str) -> Dict:
    """
    Получить действующие наряды пользователя по конкретной роли
    Право просмотра имеют только executor и supervisor

    Args:
        telegram_id (int): Telegram ID пользователя
        role (str): Роль ('supervisor', 'executor')

    Returns:
        Dict: Словарь с результатом операции
    """
    try:
        employee = await get_employee_by_telegram_id(telegram_id)
        if not employee:
            return {
                "success": False,
                "error": "Пользователь не найден.",
                "documents": [],
            }

        # Фильтр по роли (только supervisor и executor)
        filter_map = {
            "supervisor": Q(supervisor=employee),
            "executor": Q(executor=employee),
        }

        if role not in filter_map:
            return {
                "success": False,
                "error": "Неверная роль. Доступные: supervisor, executor",
                "documents": [],
            }

        documents = await sync_to_async(list)(
            Document.objects.filter(filter_map[role]).distinct()
        )

        documents_data = []
        for doc in documents:
            doc_data = {
                "id": doc.id,
                "document_number": doc.document_number,
                "task_description": doc.task_description,
                "start_datetime": doc.start_datetime.strftime("%d.%m.%Y %H:%M"),
                "end_datetime": doc.end_datetime.strftime("%d.%m.%Y %H:%M"),
                "status": doc.get_status_display(),
            }
            documents_data.append(doc_data)

        return {
            "success": True,
            "role": role,
            "documents_count": len(documents_data),
            "documents": documents_data,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Ошибка при получении нарядов по роли: {str(e)}",
            "documents": [],
        }


async def get_document_details(document_number: str, telegram_id: int) -> Dict:
    """
    Получить детальную информацию о конкретном наряде

    Args:
        document_number (str): Номер наряда
        telegram_id (int): Telegram ID пользователя (для проверки доступа)

    Returns:
        Dict: Детальная информация о наряде
    """
    try:
        employee = await get_employee_by_telegram_id(telegram_id)
        if not employee:
            return {"success": False, "error": "Пользователь не найден."}

        # Получаем документ
        document = await sync_to_async(
            Document.objects.select_related(
                "supervisor", "approver", "executor", "observer"
            )
            .prefetch_related("crew_members")
            .get
        )(document_number=document_number)

        # Проверяем, имеет ли пользователь доступ к этому документу
        # Право просмотра только у supervisor и executor
        crew_members = await sync_to_async(list)(document.crew_members.all())
        has_access = (
            document.supervisor_id == employee.id or document.executor_id == employee.id
        )

        if not has_access:
            return {
                "success": False,
                "error": "У вас нет прав для просмотра этого наряда. Доступ имеют только руководители работ и производители работ.",
            }

        # Определяем роли пользователя (только supervisor и executor)
        user_roles = []
        if document.supervisor_id == employee.id:
            user_roles.append("Руководитель работ")
        if document.executor_id == employee.id:
            user_roles.append("Производитель работ")

        crew_names = [member.full_name for member in crew_members]

        return {
            "success": True,
            "document": {
                "id": document.id,
                "document_number": document.document_number,
                "branch": document.get_branch_display(),
                "department": document.get_department_display(),
                "work_type": document.get_work_type_display(),
                "task_description": document.task_description,
                "start_datetime": document.start_datetime.strftime("%d.%m.%Y %H:%M"),
                "end_datetime": document.end_datetime.strftime("%d.%m.%Y %H:%M"),
                "status": document.get_status_display(),
                "created": document.created.strftime("%d.%m.%Y %H:%M"),
                "updated": document.updated.strftime("%d.%m.%Y %H:%M"),
                "user_roles": user_roles,
                "participants": {
                    "supervisor": (
                        document.supervisor.full_name
                        if document.supervisor
                        else "Не назначен"
                    ),
                    "approver": (
                        document.approver.full_name
                        if document.approver
                        else "Не назначен"
                    ),
                    "executor": (
                        document.executor.full_name
                        if document.executor
                        else "Не назначен"
                    ),
                    "observer": (
                        document.observer.full_name
                        if document.observer
                        else "Не назначен"
                    ),
                    "crew_members": crew_names if crew_names else ["Не назначены"],
                },
                "file_exists": bool(document.file),
                "file_url": document.file.url if document.file else None,
            },
        }

    except Document.DoesNotExist:
        return {"success": False, "error": "Наряд не найден."}
    except Exception as e:
        return {
            "success": False,
            "error": f"Ошибка при получении деталей наряда: {str(e)}",
        }


async def get_document_photos(document_number: str, photo_type: str):
    """Получить фотографии документа по типу"""
    try:
        # Получаем документ
        document = await sync_to_async(Document.objects.get)(
            document_number=document_number
        )

        # Получаем фотографии нужного типа
        photos = await sync_to_async(list)(
            DocumentPhoto.objects.filter(
                document=document, photo_type=photo_type
            ).order_by("created")
        )

        # Возвращаем список с file_id из поля file_id, а не из photo.name
        photo_list = []
        for photo in photos:
            if photo.file_id:  # Проверяем, что file_id существует
                photo_list.append({"file_id": photo.file_id})
            else:
                # Если file_id отсутствует, можно попробовать использовать путь к файлу
                # Но это будет работать только если файл доступен по URL
                print(f"Warning: photo {photo.id} has no file_id")
        
        return photo_list

    except Exception as e:
        print(f"Ошибка получения фотографий: {e}")
        return []

# Дополнительные утилиты для работы с file_id
async def get_photo_by_file_id(file_id: str) -> Optional[DocumentPhoto]:
    """Получить фото по file_id"""
    try:
        return await sync_to_async(DocumentPhoto.objects.get)(file_id=file_id)
    except DocumentPhoto.DoesNotExist:
        return None


async def get_document_photos_stats(document_number: str) -> Dict:
    """Получить статистику по фотографиям документа"""
    try:
        document = await sync_to_async(Document.objects.get)(
            document_number=document_number
        )

        photos = await sync_to_async(list)(
            DocumentPhoto.objects.filter(document=document).values(
                "photo_type", "created", "uploaded_by__name"
            )
        )

        start_photos = [p for p in photos if p["photo_type"] == "start"]
        completion_photos = [p for p in photos if p["photo_type"] == "completion"]

        return {
            "total": len(photos),
            "start_count": len(start_photos),
            "completion_count": len(completion_photos),
            "has_start_photos": len(start_photos) > 0,
            "has_completion_photos": len(completion_photos) > 0,
        }
    except Document.DoesNotExist:
        return {"error": "Документ не найден"}
