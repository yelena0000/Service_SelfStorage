from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from reservations.models import (Advertisement, Order, StorageUnit, User,
                                 Warehouse)


class OrderInline(admin.TabularInline):
    model = Order
    extra = 1                           # Количество пустых форм для добавления новых заказов
    fields = (
        'storage_unit',                 # Ячейка хранения
        'storage_duration',             # Срок хранения
    )


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'name', 'phone_number')  # Отображаем ФИО и тел
    inlines = [OrderInline]                             # Отображение связанных заказов в форме другой модели


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'user_name',                            # ФИО пользователя
        'user_phone',                           # Телефон пользователя
        'created_at',                           # Дата создания заказа
        'get_warehouse',                        # Склад
        'storage_unit',                         # Ячейка хранения
        'storage_duration',                     # Срок хранения
        'status_display',                       # Статус заказа
        'total_cost',                           # Стоимость заказа
        'reminder_date',                        # Дата напоминалки
        'start_date',                           # Дата начала аренды
        'is_unit_occupied'                      # Ячейка занята
    )
    list_filter = ('status', )

    def is_unit_occupied(self, obj):
        # Проверяет, занята ли ячейка хранения.
        return obj.storage_unit.has_active_orders()
    is_unit_occupied.boolean = True
    is_unit_occupied.short_description = 'Ячейка занята'

    def user_name(self, obj):
        # Возвращает полное имя пользователя.
        return obj.user.name
    user_name.short_description = 'ФИО'

    def user_phone(self, obj):
        # Возвращает телефон пользователя.
        return obj.user.phone_number
    user_phone.short_description = 'Телефон'

    def storage_unit(self, obj):
        # Возвращает ячейку хранения для заказа.
        return obj.storage_unit
    storage_unit.short_description = 'Ячейка хранения'

    def total_cost(self, obj):
        # Возвращает общую стоимость заказа.
        return obj.calculated_total_cost
    total_cost.short_description = 'Стоимость'

    def get_warehouse(self, obj):
        # Возвращает склад, к которому относится ячейка хранения.
        return obj.storage_unit.warehouse.name if obj.storage_unit else "Нет склада"
    get_warehouse.short_description = 'Склад'

    def status_display(self, obj):
        # Возвращает статус заказа, выделяя просрочку.
        if obj.is_expired():
            return format_html('<span style="color: red;">{}</span>', 'Просрочен')
        return obj.get_status_display()
    status_display.short_description = 'Статус заказа'

    def save_model(self, request, obj, form, change):
        # Сохраняет заказ и отображает соответствующие сообщения.
        try:
            super().save_model(request, obj, form, change)
            messages.success(request, "Заказ успешно добавлен.")
        except ValidationError as e:
            messages.error(request, str(e))

    def delete_model(self, request, obj):
        # Освобождает ячейку перед удалением заказа. 
        if obj.storage_unit.is_occupied:
            obj.release_storage_unit()
            messages.success(request, "Ячейка успешно освобождена.")
        super().delete_model(request, obj)

    def reminder_date(self, obj):
        # Возвращает дату напоминания для заказа.
        return obj.reminder_date()
    reminder_date.short_description = 'Дата напоминалки'


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    ordering = ('warehouse_id', 'name',)


@admin.register(StorageUnit)
class StorageUnitAdmin(admin.ModelAdmin):
    list_display = (
        'unit_id',
        'warehouse',
        'size',
        'get_occupied_status',
        'get_user_name',
    )

    def get_occupied_status(self, obj):
        # Возвращает статус занятости ячейки.
        return "Занята" if obj.has_active_orders() else "Свободна"

    get_occupied_status.short_description = 'Статус занятости'

    def get_user_name(self, obj):
        # Возвращает имя пользователя, если ячейка занята.
        active_order = Order.objects.filter(
            storage_unit=obj, status='active'
        ).first()
        return active_order.user.name if active_order else "Нет"

    get_user_name.short_description = 'Кем занята'


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ('promo_name',)




















