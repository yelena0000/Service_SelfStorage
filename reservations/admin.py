from django.contrib import admin
from django.contrib import messages
from .models import User, Order, Warehouse, StorageUnit
from django.utils.html import format_html
from django.core.exceptions import ValidationError


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
        'reminder_date',                        # Дата когда нужно запустить напоминалку
    )
    list_filter = ('status', )

    def user_name(self, obj):
        return obj.user.name                    # Получаем имя пользователя из связанной модели
    user_name.short_description = 'ФИО'

    def user_phone(self, obj):
        return obj.user.phone_number            # Получаем телефон пользователя из связанной модели
    user_phone.short_description = 'Телефон'

    def storage_unit(self, obj):
        return obj.storage_unit                 # Получаем информацию о ячейке хранения
    storage_unit.short_description = 'Ячейка хранения'

    def total_cost(self, obj):
        return obj.calculated_total_cost
    total_cost.short_description = 'Стоимость'

    def get_warehouse(self, obj):
        return obj.storage_unit.warehouse.name if obj.storage_unit else "Нет склада"
    get_warehouse.short_description = 'Склад'

    def status_display(self, obj):
        # Отображает статус заказа с подсветкой для просроченных заказов
        if obj.is_expired():
            return format_html('<span style="color: red;">{}</span>', "Просрочен")
        status_mapping = {
            'active': 'Активен',
            'completed': 'Закончен'
        }
        return status_mapping.get(obj.status, obj.status)
    status_display.short_description = 'Статус заказа'

    def save_model(self, request, obj, form, change):
        try:
            super().save_model(request, obj, form, change)  # Пытаемся сохранить заказ
            messages.success(request, "Заказ успешно добавлен.")
        except ValidationError as e:
            messages.error(request, str(e))                 # Отображаем сообщение об ошибке

    def delete_model(self, request, obj):
        # Освобождает ячейку перед удалением заказа
        if obj.storage_unit.is_occupied:
            obj.release_storage_unit()                      # Освобождаем ячейку перед удалением
            messages.success(request, "Ячейка успешно освобождена.")
        super().delete_model(request, obj)                  # Удаляем заказ

    def reminder_date(self, obj):
        return obj.reminder_date()
    reminder_date.short_description = 'Дата напоминалки'

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('warehouse_id', 'name')


@admin.register(StorageUnit)
class StorageUnitAdmin(admin.ModelAdmin):
    list_display = (
        'unit_id',
        'warehouse',
        'size',
        'get_occupied_status',
        'get_user_name'
    )

    def get_occupied_status(self, obj):
        # Возвращает статус занятости ячейки
        return "Занята" if obj.has_active_orders() else "Свободна"

    get_occupied_status.short_description = 'Статус занятости'

    def get_user_name(self, obj):
        # Возвращает имя пользователя, если ячейка занята
        active_order = Order.objects.filter(
            storage_unit=obj, status='active'
        ).first()  # Получаем первый активный заказ
        return active_order.user.name if active_order else "Нет"

    get_user_name.short_description = 'Кем занята'




























