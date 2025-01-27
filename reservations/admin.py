from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from reservations.models import Link, Order, StorageUnit, User, Warehouse


class OrderInline(admin.TabularInline):
    """Inline для отображения заказов в админке.

    Этот класс представляет собой inline-форму для добавления и редактирования
    заказов, связанных с определенной сущностью в админке Django.

    Атрибуты:
        model (Model): Модель, к которой применяется этот inline.
        extra (int): Количество пустых форм для добавления новых заказов.
        fields (tuple): Поля, которые будут отображаться в форме inline.
    Содержит:
        - storage_unit (StorageUnit): Ячейка хранения, связанная с заказом.
        - storage_duration (int): Срок хранения в днях для заказов.
    """
    model = Order
    extra = 1
    fields = (
        'storage_unit',
        'storage_duration',
    )


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Админ-интерфейс для модели пользователя.

    Атрибуты:
        list_display (tuple): Поля для отображения в списке пользователей.
        inlines (list): Связанные заказы, отображаемые в форме пользователя.
    """
    list_display: tuple = ('user_id', 'name', 'user_address', 'phone_number')
    inlines: list = [OrderInline]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Админ-интерфейс для модели заказа.

    Атрибуты:
        list_display (tuple): Поля для отображения в списке заказов.
        list_filter (tuple): Поля для фильтрации заказов.
    """
    list_display: tuple = (
        'user_name',
        'user_phone',
        'created_at',
        'get_warehouse',
        'storage_unit',
        'storage_duration',
        'status_display',
        'total_cost',
        'reminder_date',
        'start_date',
        'is_unit_occupied'
    )
    list_filter: tuple = ('status', )

    def is_unit_occupied(self, obj: Order) -> bool:
        """Проверяет, занята ли ячейка хранения.

        Args:
            obj (Order): Объект заказа.

        Returns:
            bool: True, если ячейка занята; иначе False.
        """
        return obj.storage_unit.has_active_orders()
    is_unit_occupied.boolean = True
    is_unit_occupied.short_description = 'Ячейка занята'

    def user_name(self, obj: Order) -> str:
        """Возвращает полное имя пользователя.

        Args:
            obj (Order): Объект заказа.

        Returns:
            str: Полное имя пользователя.
        """
        return obj.user.name
    user_name.short_description = 'ФИО'

    def user_phone(self, obj: Order) -> str:
        """Возвращает телефон пользователя.

        Args:
            obj (Order): Объект заказа.

        Returns:
            str: Телефон пользователя.
        """
        return obj.user.phone_number
    user_phone.short_description = 'Телефон'

    def storage_unit(self, obj: Order) -> StorageUnit:
        """Возвращает ячейку хранения для заказа.

        Args:
            obj (Order): Объект заказа.

        Returns:
            StorageUnit: Ячейка хранения.
        """
        return obj.storage_unit
    storage_unit.short_description = 'Ячейка хранения'

    def total_cost(self, obj: Order) -> float:
        """Возвращает общую стоимость заказа.

        Args:
            obj (Order): Объект заказа.

        Returns:
            Decimal: Общая стоимость заказа.
        """
        return obj.calculated_total_cost
    total_cost.short_description = 'Стоимость'

    def get_warehouse(self, obj: Order) -> str:
        """Возвращает склад, к которому относится ячейка хранения.

        Args:
            obj (Order): Объект заказа.

        Returns:
            str: Название склада или 'Нет склада'.
        """
        return obj.storage_unit.warehouse.name if obj.storage_unit else "Нет склада"
    get_warehouse.short_description = 'Склад'

    def status_display(self, obj: Order) -> str:
        """Возвращает статус заказа, выделяя просроченный.

        Args:
            obj (Order): Объект заказа.

        Returns:
            str: Статус заказа с возможным выделением.
        """
        if obj.is_expired():
            return format_html('<span style="color: red;">{}</span>', 'Просрочен')
        return obj.get_status_display()
    status_display.short_description = 'Статус заказа'

    def save_model(self, request, obj: Order, form, change: bool) -> None:
        """Сохраняет заказ и отображает соответствующие сообщения.

        Args:
            request (HttpRequest): Запрос пользователя.
            obj (Order): Объект заказа.
            form (ModelForm): Форма заказа.
            change (bool): True, если объект изменяется; иначе False.
        """
        try:
            super().save_model(request, obj, form, change)
            messages.success(request, "Заказ успешно добавлен.")
        except ValidationError as e:
            messages.error(request, str(e))

    def delete_model(self, request, obj: Order) -> None:
        """Освобождает ячейку перед удалением заказа.

        Args:
            request (HttpRequest): Запрос пользователя.
            obj (Order): Объект заказа.
        """
        if obj.storage_unit.is_occupied:
            obj.release_storage_unit()
            messages.success(request, "Ячейка успешно освобождена.")
        super().delete_model(request, obj)

    def reminder_date(self, obj: Order) -> str:
        """Возвращает дату напоминания для заказа.

        Args:
            obj (Order): Объект заказа.

        Returns:
            date: Дата напоминания.
        """
        return obj.reminder_date()
    reminder_date.short_description = 'Дата напоминалки'


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    """Админ-интерфейс для модели склада.

    Атрибуты:
        ordering (tuple): Поля для сортировки в админке.
    """
    ordering: tuple = ('warehouse_id', 'name',)


@admin.register(StorageUnit)
class StorageUnitAdmin(admin.ModelAdmin):
    """Админ-интерфейс для модели ячейки хранения.

    Атрибуты:
        list_display (tuple): Поля для отображения в списке ячеек хранения.
    """
    list_display: tuple = (
        'unit_id',
        'warehouse',
        'size',
        'get_occupied_status',
        'get_user_name',
    )

    def get_occupied_status(self, obj: StorageUnit) -> str:
        """Возвращает статус занятости ячейки.

        Args:
            obj (StorageUnit): Объект ячейки хранения.

        Returns:
            str: 'Занята' или 'Свободна'.
        """
        return "Занята" if obj.has_active_orders() else "Свободна"

    get_occupied_status.short_description = 'Статус занятости'

    def get_user_name(self, obj: StorageUnit) -> str:
        """Возвращает имя пользователя, если ячейка занята.

        Args:
            obj (StorageUnit): Объект ячейки хранения.

        Returns:
            str: Имя пользователя или 'Нет'.
        """
        active_order = Order.objects.filter(
            storage_unit=obj, status='active'
        ).first()
        return active_order.user.name if active_order else "Нет"

    get_user_name.short_description = 'Кем занята'


@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    """Админ-интерфейс для модели ссылки.

    Атрибуты:
        list_display (tuple): Поля для отображения в списке ссылок.
    """
    list_display: tuple = ('original_url', 'short_url', 'click_count')
