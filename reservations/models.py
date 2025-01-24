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
    user_address = models.CharField(verbose_name='Адрес клиента', max_length=200, null=True, blank=True)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.name

    def get_orders(self):
        # Возвращает все заказы пользователя
        return Order.objects.filter(user=self)


# Модель склада
class Warehouse(models.Model):
    warehouse_id = models.AutoField(verbose_name='ID склада', primary_key=True)
    name = models.CharField(verbose_name='Название склада', max_length=255)
    warehouse_address = models.CharField(verbose_name='Адрес склада', max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = 'Склад'
        verbose_name_plural = 'Склады'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Сохраняем склад и создает ячейки хранения
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

    unit_id = models.AutoField(primary_key=True, verbose_name='ID ячейки')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name='Склад')
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, verbose_name='Размер ячейки')
    is_occupied = models.BooleanField(default=False, verbose_name='Занятость')

    class Meta:
        verbose_name = 'Бокс хранения'
        verbose_name_plural = 'Боксы хранения'

    def __str__(self):
        return f"{self.get_size_display()} - {'Занята' if self.has_active_orders() else 'Свободна'}"

    def has_active_orders(self):
        # Проверяет, есть ли активные заказы для данной ячейки
        return Order.objects.filter(storage_unit=self, status='active').exists()

    def is_available(self, start_date, duration):
        end_date = start_date + timedelta(days=duration)
        overlapping_orders = Order.objects.filter(
            storage_unit=self,
            start_date__lt=end_date,
            created_at__gt=start_date
        )
        return not overlapping_orders.exists()


# Заказ
class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('active', 'Активен'),
        ('expired', 'Просрочен'),
        ('completed', 'Закончен'),
    ]
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания заказа')
    order_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    storage_unit = models.ForeignKey(StorageUnit, on_delete=models.CASCADE, verbose_name='Ячейка хранения')
    storage_duration = models.PositiveIntegerField(verbose_name='Срок хранения (дни)')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active', verbose_name='Статус заказа')
    start_date = models.DateTimeField(verbose_name='Дата начала аренды', default=timezone.now)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'

    def __str__(self):
        return f"Заказ {self.order_id} от {self.user.name}"

    def is_expired(self):
        # Проверяет, просрочен ли заказ
        return timezone.now() > self.start_date + timedelta(days=self.storage_duration)

    def save(self, *args, **kwargs):
        # Активные заказы для ячейки перед сохранением нового заказа
        now = timezone.now()

        if not self.pk:  # Если это новый заказ
            # Проверяем, не занята ли ячейка на указанный период
            overlapping_orders = Order.objects.filter(
                storage_unit=self.storage_unit,
                start_date__lt=self.start_date + timedelta(days=self.storage_duration),
                status__in=['active', 'pending']
            )
            if overlapping_orders.exists():
                raise ValidationError("Ячейка уже забронирована на этот период.")

        # Если статус не задан вручную, определяем его автоматически
        if self.status not in ['completed', 'expired']:
            if self.start_date > now:
                self.status = 'pending'  # Если дата начала в будущем
            elif self.start_date <= now < self.start_date + timedelta(days=self.storage_duration):
                self.status = 'active'  # Если текущая дата в пределах срока аренды
            else:
                self.status = 'expired'  # Если текущая дата после окончания срока аренды

        super().save(*args, **kwargs)

        # Обновляем занятость ячейки
        self.storage_unit.is_occupied = self.status in ['active', 'pending']
        self.storage_unit.save()


    def release_storage_unit(self):
        # Освобождает ячейку хранения
        print(f"[DEBUG] Освобождение ячейки для заказа ID={self.order_id}. Текущий статус: {self.status}")
        if self.storage_unit.is_occupied:
            self.storage_unit.is_occupied = False
            self.storage_unit.save()
        print(f"[DEBUG] Освобождение ячейки для заказа ID={self.order_id}. Текущий статус: {self.status}")

    @property
    def calculated_total_cost(self):
        # Свойство возвращает общую стоимость хранения на основе размера ячейки и срока хранения
        costs = {'small': 100, 'medium': 300, 'large': 500}
        return self.storage_duration * costs.get(self.storage_unit.size, 0)

    def reminder_date(self):
        # Расчет даты напоминания о окончания срока хранения
        if self.storage_duration <= 14:
            return self.start_date
        return self.start_date + timedelta(days=self.storage_duration-14) if self.start_date else None


# Сигналы для освобождения ячейки при удалении пользователя
@receiver(post_delete, sender=User)
def user_post_delete_handler(sender, instance, **kwargs):
    orders = Order.objects.filter(user=instance)
    for order in orders:
        order.release_storage_unit()
        order.delete()  # Удаляем заказ


# Реклама
class Advertisement(models.Model):
    promo_id = models.AutoField(primary_key=True)
    promo_name = models.CharField(verbose_name='', max_length=200)

    class Meta:
        verbose_name_plural = 'Реклама'

    def __str__(self):
        return f" {self.promo_id}"
