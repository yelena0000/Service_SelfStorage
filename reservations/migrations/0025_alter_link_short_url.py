# Generated by Django 5.1.5 on 2025-01-26 18:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0024_alter_link_original_url_alter_link_short_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='link',
            name='short_url',
            field=models.CharField(blank=True, max_length=100, verbose_name='Сокращенная ссылка'),
        ),
    ]
