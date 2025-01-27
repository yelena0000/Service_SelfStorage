import logging
import os
import random
import re
import time
from datetime import datetime, timedelta
from io import BytesIO

import django
import qrcode
import schedule
import telegram
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.utils import timezone
from django.utils.timezone import now
from environs import Env
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    ParseMode,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
)

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'storage_bot.settings')
django.setup()

from reservations.models import (
    Order,
    StorageUnit,
    User,
    Warehouse
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для диалога
CONSENT = 0
MAIN_MENU = 1
REQUEST_NAME = 2
REQUEST_PHONE = 3
REQUEST_START_DATE = 4
REQUEST_DURATION = 5
REQUEST_ADDRESS = 6


def start(update: Update, context: CallbackContext):
    """
        Обработчик команды /start. Приветствует пользователя и запрашивает согласие на обработку персональных данных.

        Функция выполняет следующие действия:
        1. Отправляет приветственное сообщение с описанием возможностей сервиса SelfStorage.
        2. Отправляет файл PDF с согласием на обработку персональных данных.
        3. Показывает кнопки с выбором действий: "Принять" или "Отказаться".
    """
    welcome_message = (
        "Привет! 👋 Добро пожаловать в SelfStorage – сервис для хранения вещей.\n\n"
        "📦 Когда наш сервис может быть полезен:\n"
        "- Если у вас дома не хватает места для сезонных вещей, "
        "таких как лыжи, сноуборды или велосипед.\n"
        "- Во время переезда – чтобы временно хранить мебель и другие вещи.\n"
        "- Если есть ценные вещи, которые занимают слишком много пространства, "
        "но выбрасывать их жалко.\n\n"
        "Для продолжения работы с ботом необходимо дать согласие на обработку персональных данных."
    )
    update.message.reply_text(welcome_message)

    # Отправляем файл с согласием на обработку данных
    pdf_file = "consent_form.pdf"
    try:
        with open(pdf_file, "rb") as file:
            context.bot.send_document(
                chat_id=update.effective_chat.id, document=file)
    except FileNotFoundError:
        update.message.reply_text(
            "Файл с соглашением не найден. Пожалуйста, попробуйте позже.")

    # Показываем кнопки для подтверждения
    reply_markup = ReplyKeyboardMarkup([["Принять"], ["Отказаться"]],
                                       one_time_keyboard=True,
                                       resize_keyboard=True)
    update.message.reply_text(
        "После ознакомления с документом выберите действие:\n\n"
        "✅ Нажмите 'Принять', чтобы продолжить пользоваться услугами нашего сервиса.\n\n"

        "⚠️Нажимая 'Принять', я подтверждаю своё согласие на обработку персональных данных.",
        reply_markup=reply_markup,
    )
    return CONSENT


def handle_consent(update: Update, context: CallbackContext):
    """
        Обработчик ответа пользователя на запрос согласия на обработку персональных данных.

        Функция анализирует текстовый ответ пользователя и выполняет следующие действия:
        1. Если пользователь выбрал "Принять":
            - Отправляет сообщение с благодарностью за согласие.
            - Показывает меню с действиями, доступными в сервисе.
            - Завершает состояние диалога.
        2. Если пользователь выбрал "Отказаться":
            - Сообщает, что без согласия невозможно предоставить услугу.
            - Повторно предлагает кнопки для принятия или отказа.
            - Оставляет пользователя в текущем состоянии CONSENT.
        3. Если пользователь ввел некорректный ответ:
            - Уведомляет о необходимости выбора из предложенных вариантов.
            - Повторно показывает кнопки для принятия или отказа.
            - Оставляет пользователя в текущем состоянии CONSENT.
    """
    user_response = update.message.text
    if user_response == "Принять":
        reply_markup = ReplyKeyboardMarkup(
            [["Мои заказы", "Тарифы и условия хранения"], ["Заказать ячейку"]],
            resize_keyboard=True
        )
        update.message.reply_text(
            "Спасибо! Вы приняли условия обработки персональных данных. "
            "Теперь мы можем продолжить работу. 🛠️\n\n"
            "Выберите действие из меню ниже:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    elif user_response == "Отказаться":
        # Повторно показываем кнопки
        reply_markup = ReplyKeyboardMarkup([["Принять"], ["Отказаться"]],
                                           one_time_keyboard=True,
                                           resize_keyboard=True)
        update.message.reply_text(
            "Вы отказались от обработки персональных данных. "
            "Без этого мы не можем предоставить услугу. Если передумаете, выберите 'Принять'.",
            reply_markup=reply_markup
        )
        return CONSENT  # Оставляем пользователя в этом состоянии
    else:
        # Повторно показываем кнопки, если ввод некорректен
        reply_markup = ReplyKeyboardMarkup([["Принять"], ["Отказаться"]],
                                           one_time_keyboard=True,
                                           resize_keyboard=True)
        update.message.reply_text(
            "Пожалуйста, выберите одну из предложенных опций: Принять или Отказаться.",
            reply_markup=reply_markup
        )
        return CONSENT


def tariffs(update: Update, context: CallbackContext):
    """
        Отправляет информацию о тарифах на хранение вещей и количестве свободных ячеек.

        Функция извлекает данные о тарифах и подсчитывает количество свободных ячеек для каждого размера,
        предоставляя пользователю полную информацию о текущей доступности и стоимости.

        Также включает список запрещенных к хранению вещей.
    """
    # Тарифы для каждого размера
    tariffs_data = {
        'small': 100,
        'medium': 300,
        'large': 500,
    }
    size_labels = dict(StorageUnit.SIZE_CHOICES)

    # Подсчитываем количество свободных ячеек по каждому размеру
    free_sizes_count = (
        StorageUnit.objects.filter(is_occupied=False)
        .values('size')
        .annotate(count=Count('size'))
    )

    tariffs_info = "📋 *Тарифы на хранение и количество свободных ячеек:*\n\n"
    for size_data in free_sizes_count:
        size = size_data['size']
        count = size_data['count']
        price = tariffs_data.get(size, 0)
        tariffs_info += (f"- {size_labels.get(size, 'Неизвестно')} "
                         f"({count} свободных): {price} руб./день\n")

    tariffs_info += (
        "\n⚠️ *Запрещенные для хранения вещи:*\n"
        "Мы не принимаем на хранение имущество, которое ограничено по законодательству РФ "
        "или создает неудобства для других арендаторов.\n\n"
        "❌*Нельзя хранить*:\n"
        "- оружие, боеприпасы, взрывчатые вещества;\n"
        "- токсичные, радиоактивные и легковоспламеняющиеся вещества;\n"
        "- животных;\n"
        "- пищевые продукты с истекающим сроком годности;\n"
        "- любое имущество, нарушающее законодательство РФ."
    )

    update.message.reply_text(
        tariffs_info, parse_mode=telegram.ParseMode.MARKDOWN)


def handle_self_delivery(update: Update, context: CallbackContext):
    """
        Обрабатывает выбор пользователем самостоятельной доставки вещей на склад.

        Функция отправляет пользователю список доступных складов для самостоятельной доставки
        и предлагает продолжить оформление заказа.
    """
    update.callback_query.answer()
    context.user_data['delivery_type'] = "self"

    warehouses = Warehouse.objects.all()

    self_delivery_info = "🚗 *Адреса складов для самостоятельной доставки ваших вещей:*\n\n"
    for idx, warehouse in enumerate(warehouses, start=1):
        self_delivery_info += f"{idx}️⃣ Склад: {warehouse.warehouse_address}\n"

    self_delivery_info += (
        "\n📍 Если вы не уверены в размере подходящей ячейки "
        "или не хотите самостоятельно измерять вещи, "
        "наш персонал произведет все замеры на месте."
    )
    keyboard = [
        [InlineKeyboardButton("Продолжить оформление заказа",
                              callback_data="continue_order")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.callback_query.message.reply_text(
        self_delivery_info,
        parse_mode=telegram.ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


def handle_courier_delivery(update: Update, context: CallbackContext):
    """
        Обрабатывает выбор пользователем курьерской доставки.

        Функция информирует пользователя о процессе курьерской доставки, преимуществах,
        а также позволяет перейти к следующему шагу оформления заказа.
    """
    update.callback_query.answer()
    context.user_data['delivery_type'] = "courier"

    courier_info = (
        "📦 *Курьерская доставка:*\n\n"
        "Мы бесплатно заберём ваши вещи из дома или офиса. "
        "Все замеры будут произведены курьером на месте.\n\n"
        "📋 *Процесс оформления заказа:*\n"
        "1️⃣ Вы указываете свои данные (ФИО, телефон, адрес и срок хранения).\n"
        "2️⃣ Курьер связывается с вами.\n"
        "3️⃣ Мы забираем ваши вещи и помещаем их на хранение в ячейку.\n\n"
        "🚚 Курьер приедет в удобное для вас время и заберёт вещи быстро и безопасно.\n\n"
        "Нажмите *Продолжить оформление заказа*, чтобы ввести данные и завершить заказ."
    )

    keyboard = [
        [InlineKeyboardButton("Продолжить оформление заказа",
                              callback_data="continue_order")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.callback_query.message.reply_text(
        courier_info,
        parse_mode=telegram.ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


def order_box(update: Update, context: CallbackContext):
    """
        Обрабатывает запрос пользователя на выбор способа доставки вещей в ячейку.

        Функция выводит кнопки для выбора метода доставки (курьерская доставка или самостоятельная доставка).
        После выбора метода доставки процесс оформления заказа продолжается.
    """
    # Убираем кнопку из главного меню и выводим выбор метода доставки
    keyboard = [
        [InlineKeyboardButton("Доставить мои вещи курьером",
                              callback_data="deliver_courier")],
        [InlineKeyboardButton("Привезу самостоятельно",
                              callback_data="self_delivery")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "Как вы хотите доставить ваши вещи в ячейку? Выберите способ доставки.",
        reply_markup=reply_markup
    )
    # Завершаем основной ConversationHandler, чтобы не было конфликтов
    return ConversationHandler.END


def start_order_form(update: Update, context: CallbackContext):
    """
        Начинает процесс оформления заказа, запрашивая у пользователя ФИО.

        Функция инициирует процесс сбора данных для заказа, отправляя пользователю запрос на ввод ФИО.
        После этого временно убирает главное меню и ожидает ввода данных от пользователя.
    """
    update.callback_query.answer()
    update.callback_query.message.reply_text(
        "👤 Для начала укажите ваше ФИО: (например: Иванов Иван Иванович)",
        reply_markup=ReplyKeyboardRemove()  # Убираем временно главное меню
    )
    return REQUEST_NAME


def check_name_and_request_phone(update: Update, context: CallbackContext):
    """
        Проверяет корректность введённого пользователем ФИО и запрашивает номер телефона.

        Функция выполняет проверку введённого пользователем ФИО на соответствие формату (Фамилия Имя Отчество).
        Если ФИО введено некорректно, выводится сообщение с просьбой ввести данные в правильном формате.
        В случае успешной проверки сохраняет имя в `user_data` и запрашивает номер телефона.
    """
    user_name = update.message.text.strip()
    if not re.match(r"^[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+$", user_name):
        update.message.reply_text(
            "⚠️ Пожалуйста, укажите ваше ФИО в формате: Иванов Иван Иванович.")
        return REQUEST_NAME

    context.user_data['name'] = user_name
    update.message.reply_text(
        "📞 Укажите ваш номер телефона (например: +79991234567 или 89991234567):")
    return REQUEST_PHONE


def check_phone_and_request_start_date(update: Update, context: CallbackContext):
    """
        Проверяет корректность введённого пользователем номера телефона и запрашивает дату начала хранения.

        Функция выполняет проверку введённого номера телефона на соответствие формату (+7XXXXXXXXXX или 8XXXXXXXXXX).
        Если номер телефона введён некорректно, выводится сообщение с просьбой ввести данные в правильном формате.
        В случае успешной проверки сохраняет номер телефона в `user_data` и запрашивает дату начала хранения.
    """
    phone = update.message.text.strip()
    if not re.match(r"^\+7\d{10}$|^8\d{10}$", phone):
        update.message.reply_text(
            "⚠️ Пожалуйста, укажите корректный номер телефона в формате: "
            "+79991234567 или 89991234567."
        )
        return REQUEST_PHONE

    context.user_data['phone'] = phone
    update.message.reply_text(
        "📅 Укажите дату начала хранения (в формате ДД.ММ.ГГГГ):")
    return REQUEST_START_DATE


def check_start_date_and_request_duration(update: Update, context: CallbackContext):
    """
        Проверяет корректность введённой даты начала хранения и запрашивает срок хранения.

        Функция выполняет проверку введённой пользователем даты начала хранения на соответствие формату "ДД.ММ.ГГГГ".
        Если дата некорректна или меньше текущей, выводится сообщение с просьбой ввести правильную дату.
        В случае успешной проверки сохраняет дату начала хранения в `user_data` и запрашивает срок хранения в днях.
    """
    start_date_str = update.message.text.strip()
    try:
        start_date = datetime.strptime(start_date_str, "%d.%m.%Y")
        start_date = timezone.make_aware(start_date)
        if start_date.date() < datetime.now().date():
            update.message.reply_text(
                "⚠️ Дата начала хранения не может быть раньше текущего дня.")
            return REQUEST_START_DATE
    except ValueError:
        update.message.reply_text("⚠️ Укажите дату в формате ДД.ММ.ГГГГ.")
        return REQUEST_START_DATE

    context.user_data['start_date'] = start_date
    update.message.reply_text("📦 Укажите срок хранения в днях (например: 30):")
    return REQUEST_DURATION


def check_duration_and_request_address(update: Update, context: CallbackContext):
    """
        Проверяет корректность введённого срока хранения и запрашивает адрес доставки (если необходимо).

        Функция выполняет проверку введённого пользователем срока хранения. Если срок некорректный (отрицательное или нулевое число),
        выводится сообщение с просьбой ввести корректный срок. Если срок корректен, сохраняет его в `user_data`.
        Далее, в зависимости от типа доставки, либо завершает заказ для самостоятельной доставки, либо запрашивает адрес для курьерской доставки.
    """
    try:
        duration = int(update.message.text.strip())
        if duration <= 0:
            raise ValueError
        context.user_data['storage_duration'] = duration

        # Проверяем тип доставки
        delivery_type = context.user_data.get('delivery_type')
        if delivery_type == "self":
            return finalize_order_self(update, context)
        else:  # Если доставка курьером, запрашиваем адрес
            update.message.reply_text(
                "📍 Укажите адрес, откуда нужно забрать вещи "
                "(например: г. Москва, ул. Ленина, д. 10):"
            )
            return REQUEST_ADDRESS
    except ValueError:
        update.message.reply_text(
            "⚠️ Пожалуйста, введите корректный срок хранения в днях "
            "(число дней не может быть отрицательным)."
        )
        return REQUEST_DURATION


def finalize_order_courier(update: Update, context: CallbackContext):
    """
       Завершает оформление заказа для курьерской доставки.

       Функция выполняет следующие шаги:
       1. Запрашивает у пользователя адрес для курьерской доставки и сохраняет его.
       2. Находит или создает пользователя в базе данных и сохраняет его данные.
       3. Ищет свободную ячейку для хранения и выбирает одну случайным образом.
       4. Создает заказ с информацией о пользователе, ячейке хранения и сроке хранения.
       5. Отправляет пользователю детали заказа с информацией о заказе, включая стоимость.
       6. В случае ошибки при создании заказа, сообщает об ошибке и завершает процесс.
    """
    user_address = update.message.text.strip()
    context.user_data['address'] = user_address

    # Создаем или находим пользователя в базе данных
    user, created = User.objects.get_or_create(
        user_id=update.effective_user.id,
        defaults={
            'name': context.user_data['name'],
            'phone_number': context.user_data['phone'],
            'user_address': user_address,
        }
    )
    if not created:  # Если пользователь уже существует, обновляем адрес
        user.name = context.user_data['name']
        user.phone_number = context.user_data['phone']
        user.user_address = user_address
        user.save()

    # Ищем свободную ячейку
    free_units = StorageUnit.objects.filter(is_occupied=False)
    if not free_units.exists():
        update.message.reply_text(
            "⚠️ На данный момент все ячейки заняты. Попробуйте позже.")
        return ConversationHandler.END

    # Рандомно выбираем свободную ячейку
    selected_unit = random.choice(free_units)

    # Создаем заказ
    try:
        order = Order.objects.create(
            user=user,
            start_date=context.user_data['start_date'],
            storage_unit=selected_unit,
            storage_duration=context.user_data['storage_duration']
        )
        formatted_date = context.user_data['start_date'].strftime("%d.%m.%Y")
        update.message.reply_text(
            "✅ Спасибо! Ваш заказ принят.\n\n"
            f"📋 *Детали заказа:*\n"
            f"👤 ФИО: {user.name}\n"
            f"📞 Телефон: {user.phone_number}\n"
            f"📅 Дата начала хранения: {formatted_date}\n"
            f"📦 Срок хранения: {context.user_data['storage_duration']} дней\n"
            # Адрес выводится только для курьера
            f"📍 Адрес: {context.user_data['address']}\n"
            f"🏷️ Ячейка хранения: {selected_unit.get_size_display()} "
            f"(№ {selected_unit.unit_id})\n\n"
            f"- Общая стоимость: {order.calculated_total_cost} руб.\n\n"
            "Курьер свяжется с вами в ближайшее время. 😊",
            parse_mode=telegram.ParseMode.MARKDOWN
        )
    except ValidationError as e:
        update.message.reply_text(f"⚠️ Ошибка при создании заказа: {e}")
        return ConversationHandler.END
    reply_markup = ReplyKeyboardMarkup(
        [["Мои заказы", "Тарифы и условия хранения"], ["Заказать ячейку"]],
        resize_keyboard=True
    )
    update.message.reply_text(
        "Если вас интересует что-то еще, выберите действие из меню ниже:",
        reply_markup=reply_markup
    )
    return ConversationHandler.END


def finalize_order_self(update: Update, context: CallbackContext):
    """
        Завершает оформление заказа для самостоятельной доставки.

        Функция выполняет следующие шаги:
        1. Находит или создает пользователя в базе данных и сохраняет его данные.
        2. Ищет свободную ячейку для хранения. Если ячейки заняты, уведомляет пользователя.
        3. Создает заказ с информацией о пользователе, ячейке хранения и сроке хранения.
        4. Отправляет пользователю подробности о заказе, включая стоимость.
        5. Если возникает ошибка при создании заказа, сообщает об ошибке.
    """
    user, created = User.objects.get_or_create(
        user_id=update.effective_user.id,
        defaults={
            'name': context.user_data['name'],
            'phone_number': context.user_data['phone'],
        }
    )
    if not created:  # Если пользователь уже существует, обновим данные
        user.name = context.user_data['name']
        user.phone_number = context.user_data['phone']
        user.save()

    # Ищем свободную ячейку
    free_units = StorageUnit.objects.filter(is_occupied=False)
    if not free_units:
        update.message.reply_text(
            "⚠️ На данный момент все ячейки заняты. Попробуйте позже.")
        return ConversationHandler.END

    # Рандомно выбираем свободную ячейку
    selected_unit = random.choice(free_units)
    formatted_start_date = context.user_data['start_date'].strftime("%d.%m.%Y")

    # Создаем заказ
    try:
        order = Order.objects.create(
            user=user,
            start_date=context.user_data['start_date'],
            storage_unit=selected_unit,
            storage_duration=context.user_data['storage_duration']
        )
        update.message.reply_text(
            "✅ Спасибо! Ваш заказ принят.\n\n"
            f"📋 *Детали заказа:*\n"
            f"👤 ФИО: {user.name}\n"
            f"📞 Телефон: {user.phone_number}\n"
            f"📅 Дата начала хранения: {formatted_start_date}\n"
            f"📦 Срок хранения: {context.user_data['storage_duration']} дней\n"
            f"📍 Самостоятельная доставка: {order.storage_unit.warehouse.warehouse_address}\n"
            f"🏷️ Ячейка хранения: {selected_unit.get_size_display()} "
            f"(№ {selected_unit.unit_id})\n\n"
            f"- Общая стоимость: {order.calculated_total_cost} руб.\n\n",
            parse_mode=telegram.ParseMode.MARKDOWN
        )
    except ValidationError as e:
        update.message.reply_text(f"⚠️ Ошибка при создании заказа: {e}")
        return ConversationHandler.END

    reply_markup = ReplyKeyboardMarkup(
        [["Мои заказы", "Тарифы и условия хранения"], ["Заказать ячейку"]],
        resize_keyboard=True
    )
    update.message.reply_text(
        "Если вас интересует что-то еще, выберите действие из меню ниже:",
        reply_markup=reply_markup
    )
    return ConversationHandler.END


def handle_my_order(update: Update, context: CallbackContext):
    """
       Обрабатывает запрос пользователя на просмотр активных заказов.

       Функция выполняет следующие шаги:
       1. Получает пользователя по его telegram_user_id.
       2. Если у пользователя есть активные заказы, выводит подробности каждого заказа.
       3. Для каждого активного заказа:
           - Выводит его статус с эмодзи.
           - Рассчитывает оставшиеся дни аренды.
           - Отправляет пользователю информацию о заказе.
       4. Если активных заказов нет, сообщает об этом пользователю.
       5. Если пользователь не найден в базе данных, выводит сообщение о невозможности найти учетную запись.
    """
    telegram_user_id = update.message.chat_id
    try:
        user = User.objects.get(user_id=telegram_user_id)
        orders = user.get_orders()

        if not orders.exists() or not any(order.status != 'completed' for order in orders):
            update.message.reply_text(
                "📦 У вас пока нет активных заказов.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        for order in orders:
            if order.status != 'completed':
                # Генерация статуса с эмодзи
                status_emoji = {
                    'pending': "⏳",
                    'active': "✅",
                    'expired': "⚠️",
                    'completed': "✔️"
                }.get(order.status, "❓")

                # Рассчитываем дату окончания хранения и оставшиеся дни
                end_date = order.start_date + \
                    timedelta(days=order.storage_duration)
                days_left = (end_date - now()).days

                # Формируем информацию только для текущего заказа
                orders_info = (
                    f"{status_emoji} *Заказ {order.order_id}:*\n"
                    f"- Ячейка {order.storage_unit.unit_id}: "
                    f"{order.storage_unit.get_size_display()}\n"
                    f"- {order.storage_unit.warehouse.name}\n"
                    f"- Адрес склада: {order.storage_unit.warehouse.warehouse_address or 'Адрес не указан'}\n"
                    f"- Срок хранения: {order.storage_duration} дней\n"
                    f"- Осталось дней: {days_left if days_left > 0 else 'Истёк'}\n"
                    f"- Статус: {order.get_status_display()}\n"
                    f"- Дата начала аренды: {order.start_date.strftime('%d.%m.%Y')}\n"
                    f"- Общая стоимость: {order.calculated_total_cost} руб.\n\n"
                )

                # Кнопка для текущего заказа
                keyboard = [
                    [InlineKeyboardButton(
                        "🔑 Забрать вещи из ячейки", callback_data=f"pickup_order_{order.order_id}")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Отправляем сообщение с информацией о текущем заказе
                update.message.reply_text(
                    orders_info,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )

    except User.DoesNotExist:
        update.message.reply_text(
            "❌ Учетная запись не найдена. "
            "Возможно, вы ещё не делали заказы в нашем сервисе.",
            parse_mode=ParseMode.MARKDOWN
        )


def handle_pickup_order(update: Update, context: CallbackContext):
    """
       Обрабатывает запрос на выдачу QR-кода для забора вещей из ячейки.

       Логика:
       1. Извлекаем ID заказа из callback_data.
       2. Проверяем, существует ли заказ в базе данных.
       3. В зависимости от статуса заказа:
           - Если заказ завершен, отправляем сообщение, что заказ уже завершен.
           - Если аренда ячейки еще не началась, сообщаем об этом.
           - Если заказ активен, генерируем QR-код для доступа к ячейке и отправляем его пользователю.
       4. После отправки QR-кода, изменяем статус заказа на "completed".
       5. Если заказ не найден, отправляем ошибку.
       6. Если произошла ошибка валидации или любая другая ошибка, отправляем сообщение об ошибке.
    """
    query = update.callback_query
    query.answer()

    # Извлекаем ID заказа из callback_data
    order_id = query.data.split('_')[-1]

    try:
        order = Order.objects.get(order_id=order_id)

        if order.status == 'completed':
            query.message.reply_text("❌ Этот заказ уже завершен!")
            return

        elif order.status == 'pending':
            query.message.reply_text(
                f"Аренда ячейки {order.storage_unit.unit_id} еще не началась (заказ №{order_id})"
            )
            return

        else:
            # Генерируем данные для QR-кода
            qr_data = (f"Order ID: {order_id}, User: {order.user.name}, "
                       f"Storage Unit: {order.storage_unit.unit_id}")
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)

            # Сохраняем QR-код в буфер
            qr_image = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            qr_image.save(buffer, format="PNG")
            buffer.seek(0)

            # Отправляем QR-код пользователю
            query.message.reply_photo(photo=InputFile(buffer, filename=f"order_{order_id}_qr.png"),
                                      caption=f"🔑 Ваш QR-код для открытия ячейки "
                                              f"№ {order.storage_unit.unit_id}.\n\n"
                                              f"Спасибо, что выбрали наш сервис❤️ "
                                      )

            # Меняем статус заказа на "completed"
            order.status = 'completed'
            order.save()

    except Order.DoesNotExist:
        query.message.reply_text(
            "❌ Заказ не найден. Возможно, он уже был завершен.")
    except ValidationError as e:
        query.message.reply_text(f"⚠️ Ошибка валидации: {e}")
    except Exception as e:
        query.message.reply_text("❌ Произошла ошибка при обработке заказа.")


def send_reminder(bot, order_id):
    """
       Отправляет пользователю напоминание о завершении срока хранения его заказа через 14 дней.

       Эта функция извлекает информацию о заказе по его ID, формирует текстовое сообщение с напоминанием
       о предстоящем окончании срока хранения и отправляет его пользователю через Telegram-бота.
    """
    try:
        order = Order.objects.get(order_id=order_id)
        user_id = order.user.user_id
        message = (
            f"🔔 Напоминание!\n"
            f"Ваш заказ №{order_id} заканчивает срок хранения через 14 дней.\n"
            f"📍 Адрес: {order.storage_unit.warehouse.warehouse_address or 'Не указан'}\n"
            f"Пожалуйста, освободите ячейку в указанный срок."
        )
        bot.send_message(chat_id=user_id, text=message)
    except Exception as e:
        print(f"Ошибка при отправке уведомления: {e}")


def check_and_send_reminders(bot):
    """
        Проверяет все заказы и отправляет напоминания пользователям о завершении срока хранения через 14 дней.

        Эта функция извлекает все заказы, у которых дата напоминания (reminder_date) уже наступила,
        и вызывает функцию send_reminder для каждого из таких заказов.
    """
    now = timezone.now()
    orders_to_remind = Order.objects.filter(reminder_date__lte=now)

    for order in orders_to_remind:
        send_reminder(bot, order.order_id)


def schedule_reminders(bot):
    """
        Планирует выполнение напоминаний для пользователей каждый день в 09:00.

        Эта функция использует библиотеку `schedule` для выполнения функции `check_and_send_reminders`
        каждый день в 09:00, проверяя заказы и отправляя напоминания пользователям.
    """
    schedule.every().day.at("09:00").do(check_and_send_reminders, bot=bot)

    while True:
        schedule.run_pending()  # Выполняем все задачи, когда приходит их время
        time.sleep(5)


def cancel(update: Update, context: CallbackContext):
    """
       Завершает взаимодействие с пользователем, отправляя прощальное сообщение.
    """
    update.message.reply_text(
        "Вы завершили взаимодействие с ботом. До свидания!")
    return ConversationHandler.END


def main_menu(update, context):
    """
        Отображает главное меню бота с доступными опциями для пользователя.

        Эта функция отправляет сообщение с кнопками, предоставляющими пользователю выбор действия:
        1. Просмотр своих заказов.
        2. Ознакомление с тарифами и условиями хранения.
        3. Возможность заказать ячейку для хранения.
    """
    reply_markup = ReplyKeyboardMarkup(
        [["Мои заказы", "Тарифы и условия хранения"], ["Заказать ячейку"]],
        resize_keyboard=True
    )
    update.message.reply_text(
        "Добро пожаловать в меню! Выберите действие:",
        reply_markup=reply_markup
    )
    return MAIN_MENU


def main():
    """
       Основная функция для инициализации и запуска Telegram-бота.

       Эта функция выполняет следующие действия:
       1. Загружает переменные окружения, включая токен для бота.
       2. Создаёт экземпляр бота и диспетчера для обработки обновлений.
       3. Регистрирует обработчики для различных состояний и команд:
           - Обработчик начала диалога с пользователем.
           - Обработчики для работы с меню, заказами и взаимодействием с пользователем.
           - Обработчики для обработки callback-запросов и переходов между состояниями.
       4. Запускает цикл обработки обновлений и ожидание событий от пользователей.
       5. Запускает функцию для отправки напоминаний о сроках хранения.
    """
    env = Env()
    env.read_env()

    token = env.str('TG_BOT_TOKEN')
    bot = telegram.Bot(token=token)

    updater = Updater(token)
    dispatcher = updater.dispatcher

    start_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CONSENT: [
                MessageHandler(Filters.regex(
                    "^(Принять|Отказаться)$"), handle_consent),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    main_menu_handler = ConversationHandler(
        entry_points=[
            # Вход в главное меню через эту команду
            CommandHandler("main_menu", main_menu),
            MessageHandler(Filters.regex("^Меню$"), main_menu),
            MessageHandler(Filters.regex("^Мои заказы$"), handle_my_order),
            MessageHandler(Filters.regex(
                "^Тарифы и условия хранения$"), tariffs),
            MessageHandler(Filters.regex("^Заказать ячейку$"), order_box),
        ],
        states={
            MAIN_MENU: [
                MessageHandler(Filters.regex("^Мои заказы$"), handle_my_order),
                MessageHandler(Filters.regex(
                    "^Тарифы и условия хранения$"), tariffs),
                MessageHandler(Filters.regex("^Заказать ячейку$"), order_box),
                MessageHandler(
                    Filters.text & ~Filters.command,
                    lambda update, context: update.message.reply_text(
                        "Выберите пункт из меню!")
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    order_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_order_form, pattern="^continue_order$"),
        ],
        states={
            REQUEST_NAME: [
                MessageHandler(Filters.text & ~Filters.command,
                               check_name_and_request_phone),
            ],
            REQUEST_PHONE: [
                MessageHandler(Filters.text & ~Filters.command,
                               check_phone_and_request_start_date),
            ],
            REQUEST_START_DATE: [
                MessageHandler(Filters.text & ~Filters.command,
                               check_start_date_and_request_duration),
            ],
            REQUEST_DURATION: [
                MessageHandler(Filters.text & ~Filters.command,
                               check_duration_and_request_address),
            ],
            REQUEST_ADDRESS: [
                MessageHandler(Filters.text & ~Filters.command,
                               finalize_order_courier),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    dispatcher.add_handler(start_conv_handler)
    dispatcher.add_handler(order_conv_handler)
    dispatcher.add_handler(main_menu_handler)

    dispatcher.add_handler(
        CallbackQueryHandler(handle_courier_delivery, pattern="^deliver_courier$")
    )
    dispatcher.add_handler(
        CallbackQueryHandler(handle_self_delivery, pattern="^self_delivery$")
    )
    dispatcher.add_handler(
        CallbackQueryHandler(start_order_form, pattern="^continue_order$")
    )
    dispatcher.add_handler(CallbackQueryHandler(
        handle_pickup_order, pattern=r'^pickup_order_\d+$')
    )

    # Запуск бота
    updater.start_polling()
    updater.idle()

    schedule_reminders(bot)


if __name__ == '__main__':
    main()
