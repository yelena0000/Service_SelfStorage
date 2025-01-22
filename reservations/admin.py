from django.contrib import admin
from .models import Client


class ClientAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'order_type',
        'order_date',
        'storage_duration',
        'get_order_status',
        'phone_number',)
    list_filter = ('is_processed', 'storage_duration', 'order_date')
    search_fields = ('full_name', 'phone_number')

    def get_order_status(self, obj):
        # Возвращает статус заказа
        return obj.get_order_status()

    get_order_status.short_description = 'Статус заказа'


admin.site.register(Client, ClientAdmin)
