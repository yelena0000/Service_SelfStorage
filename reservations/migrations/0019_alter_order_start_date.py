# Generated by Django 5.1.5 on 2025-01-24 14:46

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0018_alter_order_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='start_date',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='Дата начала аренды'),
        ),
    ]
