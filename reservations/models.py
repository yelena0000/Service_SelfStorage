from django.db import models
from django.utils import timezone
from datetime import timedelta


class OrderType(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class Client(models.Model):
    STORAGE_CHOICES = [
        (15, '15 дней'),
        (30, '30 дней'),
        (45, '45 дней'),
        (60, '60 дней'),
        (75, '75 дней'),
        (90, '90 дней'),
        (115, '115 дней'),
        (130, '130 дней'),
        (150, '150 дней'),
    ]

    ORDER_TYPE_CHOICES = [
        ('storage_rates', 'Тарифы хранения'),
        ('courier_pickup', 'Забор курьером'),
        ('self_delivery', 'Самому привезти'),
        ('my_orders', 'Мои заказы')
    ]

    full_name = models.CharField('ФИО заказчика', max_length=100)
    phone_number = models.CharField('Номер тел.', max_length=20)
    is_processed = models.BooleanField(default=False, verbose_name='Обработан')
    order_type = models.CharField(
        max_length=50,
        choices=ORDER_TYPE_CHOICES,
        verbose_name='Тип заказа',
        null=True,
        blank=True)
    storage_duration = models.PositiveIntegerField(
        choices=STORAGE_CHOICES,
        verbose_name='Срок хранения',
        null=True,
        blank=True)
    order_date = models.DateTimeField(
        default=timezone.now,
        verbose_name='Дата заказа')

    def get_order_status(self):
        """Определяет статус заказа."""
        if self.storage_duration is None:
            return "Не указано"  # статус для случая отсутствия срока хранения

        expiration_date = self.order_date + timedelta(
            days=self.storage_duration)  # Дата окончания хранения

        if self.is_processed:
            return "Закончен"
        elif timezone.now() > expiration_date:
            return "Просрочен"
        else:
            return "Активен"

    def __str__(self):
        return f"{self.full_name} - {self.phone_number}"
