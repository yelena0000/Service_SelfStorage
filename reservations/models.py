from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError


# Пользователь
class User(models.Model):
    user_id = models.AutoField('id пользователя', primary_key=True)
    name = models.CharField(verbose_name='Имя пользователя', max_length=200)
    phone_number = models.CharField(verbose_name='Телефон', max_length=20)

    class Meta:
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.name

    def get_orders(self):
        # Возвращает все заказы пользователя
        return Order.objects.filter(user=self)


# Модель склада
class Warehouse(models.Model):
    warehouse_id = models.AutoField(primary_key=True, verbose_name='ID склада')
    name = models.CharField(max_length=255, verbose_name='Название склада')

    class Meta:
        verbose_name_plural = 'Склады'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Сохраняем склад
        super().save(*args, **kwargs)

        # Создаем ячейки хранения только если они еще не созданы
        if not StorageUnit.objects.filter(warehouse=self).exists():
            sizes = ['small', 'small', 'medium', 'medium', 'large', 'large']
            for size in sizes:
                StorageUnit.objects.create(warehouse=self, size=size, is_occupied=False)

    def get_free_storage_units_count(self):
        # Возвращает количество свободных ячеек на складе
        return StorageUnit.objects.filter(warehouse=self, is_occupied=False).count()


# Модель ячейки
class StorageUnit(models.Model):
    SIZE_CHOICES = [
        ('small', 'Маленькая (до 1 м³)'),
        ('medium', 'Средняя (1-5 м³)'),
        ('large', 'Большая (более 5 м³)'),
    ]

    unit_id = models.AutoField(
        primary_key=True,
        verbose_name='ID ячейки'
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        verbose_name='Склад'
    )
    size = models.CharField(
        max_length=10,
        choices=SIZE_CHOICES,
        verbose_name='Размер ячейки'
    )
    is_occupied = models.BooleanField(default=False, verbose_name='Занятость')

    class Meta:
        verbose_name_plural = 'Боксы хранения'

    def __str__(self):
        return f"{self.get_size_display()} - {'Занята' if self.has_active_orders() else 'Свободна'}"

    def has_active_orders(self):
        # Проверяет, есть ли активные заказы для данной ячейки
        return Order.objects.filter(storage_unit=self, status='active').exists()


# Заказ
class Order(models.Model):
    STATUS_CHOICES = [
        ('active', 'Активен'),
        ('expired', 'Просрочен'),
        ('completed', 'Закончен'),
    ]

    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Дата создания заказа',
    )
    order_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
    )
    storage_unit = models.ForeignKey(
        StorageUnit,
        on_delete=models.CASCADE,
        verbose_name='Ячейка хранения'
    )
    storage_duration = models.PositiveIntegerField(verbose_name='Срок хранения (дни)')
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name='Статус заказа'
    )

    class Meta:
        verbose_name_plural = 'Заказы'

    def __str__(self):
        return f"Заказ {self.order_id} от {self.user.name}"

    def is_expired(self):
        # Проверяет, просрочен ли заказ
        expiration_date = self.created_at + timedelta(days=self.storage_duration)
        return timezone.now() > expiration_date

    def save(self, *args, **kwargs):
        # Активные заказы для ячейки перед сохранением нового заказа
        if self.storage_unit.has_active_orders():
            raise ValidationError("Ошибка: Ячейка уже занята активным заказом.")

        # Статуса заказа
        if self.storage_duration <= 0:
            self.status = 'expired'
        else:
            expiration_date = self.created_at + timedelta(days=self.storage_duration)
            if timezone.now() > expiration_date:
                self.status = 'expired'
            else:
                self.status = 'active'

        super().save(*args, **kwargs)  # Сохраняем заказ

        # Занятость ячейки после успешного сохранения заказа
        self.storage_unit.is_occupied = True
        self.storage_unit.save()

    def release_storage_unit(self):
        # Освобождает ячейку хранения
        if self.storage_unit.is_occupied:
            self.storage_unit.is_occupied = False
            self.storage_unit.save()

    @property
    def calculated_total_cost(self):
        # Свойство возвращает общую стоимость хранения на основе размера ячейки и срока хранения
        if self.storage_unit.size == 'small':
            return self.storage_duration * 100  # 100 р/день
        elif self.storage_unit.size == 'medium':
            return self.storage_duration * 300  # 300 р/день
        elif self.storage_unit.size == 'large':
            return self.storage_duration * 500  # 500 р/день
        return 0

    def reminder_date(self):
        # Расчет даты напоминания о окончания срока хранения
        return self.created_at + timedelta(days=self.storage_duration-14)


# Сигналы для освобождения ячейки при удалении пользователя
@receiver(post_delete, sender=User)
def user_post_delete_handler(sender, instance, **kwargs):
    # Освобождает все ячейки хранения для заказов пользователя
    orders = Order.objects.filter(user=instance)

    for order in orders:
        order.release_storage_unit()
        order.delete()  # Удаляем заказ

























































# # Пользователь
# class User(models.Model):
#     user_id = models.AutoField('id пользователя', primary_key=True)
#     name = models.CharField(verbose_name='Имя пользователя', max_length=255)
#     phone_number = models.CharField(verbose_name='Тел.', max_length=20)
#     # consent_pdf = models.FileField(upload_to='consent_pdfs/')  # Путь к PDF с согласием

#     def __str__(self):
#         return self.name


# # Заказ
# class Order(models.Model):
#     STATUS_CHOICES = [
#         ('Тарифы хранения', 'Тарифы хранения'),
#         ('Забор курьером', 'Забор курьером'),
#         ('Самому привезти', 'Самому привезти'),
#         ('Мои заказы', 'Мои заказы'),
#     ]

#     order_id = models.AutoField(primary_key=True)
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     storage_volume = models.PositiveIntegerField()
#     storage_duration = models.PositiveIntegerField()
#     status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')

#     # some_new_field = models.CharField(max_length=100, null=True)

#     def __str__(self):
#         return f"Order {self.order_id} by {self.user.name}"


# class Warehouse(models.Model):
#     warehouse_id = models.AutoField(primary_key=True)


# # Напоминания
# class Reminder(models.Model):
#     reminder_id = models.AutoField(primary_key=True)  # Автоинкрементный ID
#     user = models.ForeignKey(User, on_delete=models.CASCADE)  # Связь с пользователем
#     message = models.TextField()  # Текст напоминания
#     reminder_date = models.DateTimeField()  # Дата отправки напоминания

#     def __str__(self):
#         return f"Reminder for {self.user.name}: {self.message}"
    
    
    
    
    
    
    
    
#     # Точка самовывоза        
# class PickupPoint(models.Model):
#     point_id = models.AutoField(primary_key=True)  # Автоинкрементный ID
#     address = models.CharField(max_length=255)

#     def __str__(self):
#         return self.address


# # Доставка
# class Delivery(models.Model):
#     delivery_id = models.AutoField(primary_key=True)  # Автоинкрементный ID
#     order = models.ForeignKey(Order, on_delete=models.CASCADE)  # Связь с заказом
#     delivery_address = models.CharField(max_length=255)

#     def __str__(self):
#         return f"Delivery for Order {self.order.order_id}"