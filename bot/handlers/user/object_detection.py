import cv2
import numpy as np
from ultralytics import YOLO
import os
from PIL import Image, ImageDraw, ImageFont

class PPEPhotoDetector:
    def __init__(self, model_path='yolo11n.pt', confidence_threshold=0.5):
        """
        Детектор СИЗ для фотографий
        
        Args:
            model_path (str): Путь к модели YOLO (по умолчанию best.pt)
            confidence_threshold (float): Порог уверенности для детекции
        """
        # Загружаем модель YOLO
        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold
        
        # Классы СИЗ с переводом
        self.ppe_classes = {
            'person': 'Человек',
            'car': 'Автомобиль',
            'truck': 'Грузовик',
            'bus': 'Автобус',
            'motorcycle': 'Мотоцикл',
            'bicycle': 'Велосипед',
            'backpack': 'Рюкзак',
            'umbrella': 'Зонт',
            'suitcase': 'Чемодан',
            'helmet': 'Каска',  # если есть в кастомных классах
            'sports ball': 'Каска',
        }

        
        # Цвета для разных объектов (RGB для PIL)
        self.colors = {
            'person': (0, 102, 255),        # белый        # синий
            'truck': (255, 51, 0),            # красный
            'bus': (255, 165, 0),             # оранжевый
            'motorcycle': (204, 0, 204),      # фиолетовый
            'bicycle': (0, 255, 0),           # зелёный
            'backpack': (255, 255, 0),        # жёлтый
            'umbrella': (102, 0, 204),        # тёмно-фиолетовый
            'suitcase': (0, 153, 153),        # бирюзовый
            'helmet': (0, 255, 255),          # голубой (если появится)
            'sports ball': (0, 255, 255),          # голубой (если появится)
            'unknown': (128, 128, 128)        # серый (по умолчанию)
        }

        
        # Пытаемся загрузить шрифт для кириллицы
        self.font_path = self._find_cyrillic_font()
        
        print(f"Модель загружена: {model_path}")
        print(f"Шрифт для кириллицы: {self.font_path}")
        print(f"Доступные классы: {list(self.model.names.values())}")
    
    def _find_cyrillic_font(self):
        """Поиск шрифта, поддерживающего кириллицу"""
        font_paths = [
            # Windows
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            # macOS
            "/System/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                return font_path
        
        # Если системный шрифт не найден, используем шрифт по умолчанию PIL
        return None
    
    def detect_objects(self, image_path):
        """
        Детекция объектов на фотографии
        
        Args:
            image_path (str): Путь к изображению
            
        Returns:
            dict: Результаты детекции
        """
        # Проверяем существование файла
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Файл не найден: {image_path}")
        
        # Загружаем изображение
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Не удалось загрузить изображение: {image_path}")
        
        # Выполняем детекцию
        results = self.model(image, conf=self.confidence_threshold)
        
        detected_objects = []
        
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    # Получаем данные детекции
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = box.conf[0].cpu().numpy()
                    class_id = int(box.cls[0].cpu().numpy())
                    
                    # Получаем название класса из модели
                    class_name = self.model.names[class_id]

                    detection = {
                        'class': class_name,
                        'class_ru': self.ppe_classes.get(class_name, class_name),
                        'confidence': float(confidence),
                        'bbox': [int(x1), int(y1), int(x2), int(y2)],
                        'area': int((x2-x1) * (y2-y1))
                    }
                    
                    detected_objects.append(detection)
        
        return {
            'image_path': image_path,
            'image_shape': image.shape,
            'detected_objects': detected_objects,
            'total_detections': len(detected_objects)
        }
    
    def analyze_safety_compliance(self, detections):
        """
        Анализ соблюдения требований безопасности на основе нарушений
        """
        detected = detections['detected_objects']
        violations = [obj for obj in detected if obj['class'].startswith("NO-")]

        analysis = {
            'total_violations': len(violations),
            'violations_details': violations,
            'safety_status': 'Нарушений СИЗ не обнаружено' if len(violations) == 0 else 'Обнаружены нарушения СИЗ',
            'recommendations': []
        }

        if violations:
            for v in violations:
                analysis['recommendations'].append(f"Нарушение: {v['class_ru']}")

        return analysis

    def draw_detections(self, image_path, detections, analysis):
        """
        Отрисовка результатов детекции на изображении с поддержкой кириллицы
        
        Args:
            image_path (str): Путь к исходному изображению
            detections: Результаты детекции
            analysis: Анализ безопасности
            
        Returns:
            np.array: Изображение с отмеченными объектами
        """
        # Загружаем изображение через PIL для работы с текстом
        pil_image = Image.open(image_path).convert('RGB')
        draw = ImageDraw.Draw(pil_image)
        
        # Загружаем шрифты
        try:
            if self.font_path:
                font_large = ImageFont.truetype(self.font_path, 24)
                font_medium = ImageFont.truetype(self.font_path, 16)
                font_small = ImageFont.truetype(self.font_path, 12)
            else:
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Отрисовываем все детекции
        for obj in detections['detected_objects']:
            x1, y1, x2, y2 = obj['bbox']
            class_name = obj['class']
            class_ru = obj['class_ru']
            confidence = obj['confidence']
            
            # Определяем цвет
            color = self.colors.get(class_name, self.colors['unknown'])
            
            # Рисуем прямоугольник
            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
            
            # Подготавливаем текст
            label = f"{class_ru}: {confidence:.2f}"
            
            # Получаем размер текста
            try:
                bbox = draw.textbbox((0, 0), label, font=font_medium)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            except:
                # Для старых версий PIL
                text_width, text_height = draw.textsize(label, font=font_medium)
            
            # Рисуем фон для текста
            draw.rectangle([x1, y1 - text_height - 10, x1 + text_width + 10, y1], 
                         fill=color, outline=color)
            
            # Рисуем текст
            draw.text((x1 + 5, y1 - text_height - 5), label, 
                     fill='white', font=font_medium)
        
        # Конвертируем обратно в OpenCV формат
        result_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        
        return result_image
    
    def _draw_info_panel_pil(self, draw, image_size, analysis, font_large, font_medium, font_small):
        """Отрисовка информационной панели с помощью PIL"""
        width, height = image_size
        
        # Размеры панели
        panel_width = 450
        panel_height = 120
        panel_x = width - panel_width - 10
        panel_y = 10
        
        # Рисуем фон панели
        draw.rectangle([panel_x, panel_y, panel_x + panel_width, panel_y + panel_height], 
                      fill=(0, 0, 0), outline=(255, 255, 255), width=2)
        
        # Текст панели
        y_offset = panel_y + 15
        
        # Заголовок
        draw.text((panel_x + 10, y_offset), "АНАЛИЗ БЕЗОПАСНОСТИ", 
                 fill=(0, 255, 255), font=font_medium)
        
        y_offset += 25
        
        # Количество нарушений
        draw.text((panel_x + 10, y_offset), f"Нарушений: {analysis['total_violations']}", 
                 fill=(255, 255, 255), font=font_small)
        
        y_offset += 20
        
        # Статус
        status_color = (0, 255, 0) if analysis['total_violations'] == 0 else (255, 0, 0)
        status_text = f"Статус: {analysis['safety_status'][:25]}"
        if len(analysis['safety_status']) > 25:
            status_text += "..."
        
        draw.text((panel_x + 10, y_offset), status_text, 
                 fill=status_color, font=font_small)
        
        y_offset += 20
        
        # Рекомендации (первая)
        if analysis['recommendations']:
            rec_text = analysis['recommendations'][0][:35]
            if len(analysis['recommendations'][0]) > 35:
                rec_text += "..."
            draw.text((panel_x + 10, y_offset), rec_text, 
                     fill=(255, 255, 0), font=font_small)
        
        y_offset += 15
        
        # Напоминание
        draw.text((panel_x + 10, y_offset), "Автоматическая проверка СИЗ", 
                 fill=(0, 255, 255), font=font_small)
    
    def process_photo(self, input_path, output_path=None):
        """
        Полная обработка фотографии
        
        Args:
            input_path (str): Путь к входному изображению
            output_path (str): Путь для сохранения результата (опционально)
            
        Returns:
            tuple: (результирующее_изображение, детекции, анализ)
        """
        try:
            # Детекция объектов
            print(f"Обработка изображения: {input_path}")
            detections = self.detect_objects(input_path)
            
            # Анализ безопасности
            analysis = self.analyze_safety_compliance(detections)
            
            # Отрисовка результатов
            result_image = self.draw_detections(input_path, detections, analysis)
            
            # Сохранение результата
            if output_path:
                success = cv2.imwrite(output_path, result_image)
                if success:
                    print(f"Результат сохранен: {output_path}")
                else:
                    print(f"Ошибка сохранения: {output_path}")
            
            # Вывод отчета
            self._print_report(detections, analysis)
            
            return result_image, detections, analysis
            
        except Exception as e:
            print(f"Ошибка обработки: {str(e)}")
            return None, None, None
    
    def _print_report(self, detections, analysis):
        """Вывод текстового отчета"""
        print("\n" + "="*60)
        print("ОТЧЕТ ПО ДЕТЕКЦИИ СИЗ НА ФОТО")
        print("="*60)
        
        print(f"Изображение: {detections['image_path']}")
        print(f"Размер: {detections['image_shape'][1]}x{detections['image_shape'][0]} пикселей")
        print(f"Всего обнаружено объектов: {detections['total_detections']}")
        
        if detections['detected_objects']:
            print("\nДетали обнаруженных объектов:")
            for i, obj in enumerate(detections['detected_objects'], 1):
                print(f"  {i}. {obj['class_ru']} (уверенность: {obj['confidence']:.2f})")
        
        print(f"\nСтатус безопасности: {analysis['safety_status']}")
        
        if analysis['recommendations']:
            print("\nРекомендации:")
            for rec in analysis['recommendations']:
                print(f"  • {rec}")
        
        print("="*60)