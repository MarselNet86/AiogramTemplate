import os
import sys
import django
from django.conf import settings

# Добавляем путь к Django проекту
sys.path.append(r"C:\Users\daimo\web\DocumentHelper\documenthelper")

# Настраиваем Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "documenthelper.settings")
django.setup()
