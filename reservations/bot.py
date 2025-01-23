import logging
import telegram
from telegram import (
    Bot,
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    Filters,
)
from environs import Env


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
    welcome_message = (
        "Привет! 👋 Добро пожаловать в SelfStorage – сервис для хранения вещей.\n\n"
        "📦 Когда наш сервис может быть полезен:\n"
        "- Если у тебя дома не хватает места для сезонных вещей, таких как лыжи, сноуборды или велосипед.\n"
        "- Во время переезда – чтобы временно хранить мебель и другие вещи.\n"
        "- Если есть ценные вещи, которые занимают слишком много пространства, но выбрасывать их жалко.\n\n"
        "📍 Напиши /help, чтобы узнать о доступных командах и начать работу.\n\n"
        "Для продолжения работы с ботом необходимо дать согласие на обработку персональных данных."
    )
    update.message.reply_text(welcome_message)

    # Отправляем файл с согласием на обработку данных
    pdf_file = "consent_form.pdf"
    try:
        with open(pdf_file, "rb") as file:
            context.bot.send_document(chat_id=update.effective_chat.id, document=file)
    except FileNotFoundError:
        update.message.reply_text("Файл с соглашением не найден. Пожалуйста, попробуйте позже.")

    # Показываем кнопки для подтверждения
    reply_markup = ReplyKeyboardMarkup([["Принять"], ["Отказаться"]],
                                       one_time_keyboard=True,
                                       resize_keyboard=True)
    update.message.reply_text(
        "После ознакомления с документом выберите действие:\n\n"
        "✅ Нажмите 'Принять', чтобы продолжить.\n"
        "❌ Нажмите 'Отказаться', чтобы выйти. \n\n"
        "⚠️Нажимая 'Принять', я подтверждаю своё согласие на обработку персональных данных.",
        reply_markup=reply_markup,
    )
    return CONSENT

def handle_consent(update: Update, context: CallbackContext):
    user_response = update.message.text
    if user_response == "Принять":
        update.message.reply_text(
            "Спасибо! Вы приняли условия обработки персональных данных. Теперь мы можем продолжить работу. 🛠️"
        )

        # Основное меню с кнопками
        reply_markup = ReplyKeyboardMarkup(
            [["Мой заказ", "Тарифы и условия хранения"], ["Заказать ячейку"]],
            resize_keyboard=True
        )
        update.message.reply_text(
            "Выберите действие из меню ниже:",
            reply_markup=reply_markup
        )
        return MAIN_MENU
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
    tariffs_info = (
        "📋 *Тарифы на хранение:*\n"
        "- До 1 м³: 100 руб./день\n"
        "- От 1 до 5 м³: 300 руб./день\n"
        "- Более 5 м³: 500 руб./день\n\n"
        "⚠️ *Запрещенные для хранения вещи:*\n"
        "Мы не принимаем на хранение имущество, которое ограничено по законодательству РФ "
        "или создает неудобства для других арендаторов.\n\n"
        "Нельзя хранить:\n"
        "- Оружие, боеприпасы, взрывчатые вещества\n"
        "- Токсичные, радиоактивные и легковоспламеняющиеся вещества\n"
        "- Животных\n"
        "- Пищевые продукты с истекающим сроком годности\n"
        "- Любое имущество, нарушающее законодательство РФ"
    )
    update.message.reply_text(tariffs_info, parse_mode=telegram.ParseMode.MARKDOWN)


def handle_self_delivery(update: Update, context: CallbackContext):
    # Отображение адресов для самостоятельной доставки
    self_delivery_info = (
        "🚗 *Пункты приёма вещей для самостоятельной доставки:*\n\n"
        "1️⃣ <Адрес 1>\n"
        "2️⃣ <Адрес 2>\n"
        "3️⃣ <Адрес 3>\n\n"
        "📍 Если не знаете габариты ваших вещей или не хотите их измерять, все необходимые замеры произведут при приёме на склад!\n"
        "📦 Если вы передумаете ехать самостоятельно, вы всегда можете выбрать бесплатную доставку курьером!"
    )

    # Кнопка для перехода на доставку курьером
    keyboard = [
        [InlineKeyboardButton("Доставить мои вещи курьером", callback_data="deliver_courier")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.callback_query.message.reply_text(
        self_delivery_info,
        parse_mode=telegram.ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

def handle_courier_delivery(update: Update, context: CallbackContext):
    update.callback_query.answer()
    courier_info = (
        "📦 *Курьерская доставка:*\n\n"
        "Мы бесплатно заберём ваши вещи из дома или офиса. Все замеры будут произведены курьером на месте.\n\n"
        "📋 *Процесс оформления заказа:*\n"
        "1️⃣ Вы указываете свои данные (ФИО, телефон, адрес и срок хранения).\n"
        "2️⃣ Курьер связывается с вами.\n"
        "3️⃣ Мы забираем ваши вещи и помещаем их на хранение в ячейку.\n\n"
        "🚚 Курьер приедет в удобное для вас время и заберёт вещи быстро и безопасно.\n\n"
        "Нажмите *Продолжить оформление заказа*, чтобы ввести данные и завершить заказ."
    )

    keyboard = [
        [InlineKeyboardButton("Продолжить оформление заказа", callback_data="continue_order")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.callback_query.message.reply_text(
        courier_info,
        parse_mode=telegram.ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

def order_box(update: Update, context: CallbackContext):
    # Убираем кнопку из главного меню и выводим выбор метода доставки
    keyboard = [
        [InlineKeyboardButton("Доставить мои вещи курьером", callback_data="deliver_courier")],
        [InlineKeyboardButton("Привезу самостоятельно", callback_data="self_delivery")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "Как вы хотите заказать ячейку? Выберите способ доставки.",
        reply_markup=reply_markup
    )
    # Завершаем основной ConversationHandler, чтобы не было конфликтов
    return ConversationHandler.END


def start_order_form(update: Update, context: CallbackContext):
    # Начинаем оформление заказа
    logger.info(f"Пользователь {update.effective_user.id} начал оформление заказа.")
    update.callback_query.answer()
    update.callback_query.message.reply_text(
        "👤 Для начала укажите ваше ФИО: (например: Иванов Иван Иванович)",
        reply_markup=ReplyKeyboardRemove()  # Убираем главное меню
    )
    return REQUEST_NAME


def request_name(update: Update, context: CallbackContext):
    logger.info(f"Функция request_name вызвана пользователем {update.effective_user.id}")

    user_name = update.message.text.strip()

    logger.info(f"Получено имя от пользователя {update.effective_user.id}: {user_name}")

    context.user_data['name'] = user_name
    update.message.reply_text("📞 Укажите ваш номер телефона (например: +79001234567):")

    logger.info(f"Переход к состоянию REQUEST_PHONE для пользователя {update.effective_user.id}")
    return REQUEST_PHONE


def request_phone(update: Update, context: CallbackContext):
    context.user_data['phone'] = update.message.text.strip()
    update.message.reply_text("📅 Укажите дату начала хранения (в формате ДД.ММ.ГГГГ):")
    return REQUEST_START_DATE


def request_start_date(update: Update, context: CallbackContext):
    context.user_data['start_date'] = update.message.text.strip()
    update.message.reply_text("📦 Укажите срок хранения в днях (например: 30):")
    return REQUEST_DURATION


def request_duration(update: Update, context: CallbackContext):
    try:
        context.user_data['storage_duration'] = int(update.message.text.strip())
        update.message.reply_text("📍 Укажите адрес, откуда нужно забрать вещи (например: г. Москва, ул. Ленина, д. 10):")
        return REQUEST_ADDRESS
    except ValueError:
        update.message.reply_text("⚠️ Пожалуйста, введите срок хранения числом.")
        return REQUEST_DURATION


def request_address(update: Update, context: CallbackContext):
    context.user_data['address'] = update.message.text.strip()

    # Подтверждение всех введённых данных
    update.message.reply_text(
        "✅ Спасибо! Ваш заказ принят.\n\n"
        f"📋 *Детали заказа:*\n"
        f"👤 ФИО: {context.user_data['name']}\n"
        f"📞 Телефон: {context.user_data['phone']}\n"
        f"📅 Дата начала хранения: {context.user_data['start_date']}\n"
        f"📦 Срок хранения: {context.user_data['storage_duration']} дней\n"
        f"📍 Адрес: {context.user_data['address']}\n\n"
        "Курьер свяжется с вами в ближайшее время. 😊",
        parse_mode=telegram.ParseMode.MARKDOWN
    )
    reply_markup = ReplyKeyboardMarkup(
        [["Мой заказ", "Тарифы и условия хранения"], ["Заказать ячейку"]],
        resize_keyboard=True
    )
    update.message.reply_text(
        "Заказ успешно оформлен. Если вас интересует что-то еще, выберите действие из меню ниже:",
        reply_markup=reply_markup
    )
    return MAIN_MENU



def handle_my_order(update: Update, context: CallbackContext):
    # Заглушка для кнопки "Мой заказ"
    update.message.reply_text("<здесь будет выводиться информация о заказах пользователя>")


def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Вы завершили взаимодействие с ботом. До свидания!")
    return ConversationHandler.END


# Регистрация CallbackQueryHandler для обработки инлайн-кнопок
def main():
    env = Env()
    env.read_env()

    token = env.str('TG_BOT_TOKEN')
    bot = telegram.Bot(token=token)

    updater = Updater(token)
    dispatcher = updater.dispatcher

    main_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CONSENT: [MessageHandler(Filters.regex("^(Принять|Отказаться)$"), handle_consent)],
            MAIN_MENU: [
                MessageHandler(Filters.regex("^Мой заказ$"), handle_my_order),
                MessageHandler(Filters.regex("^Тарифы и условия хранения$"), tariffs),
                MessageHandler(Filters.regex("^Заказать ячейку$"), order_box),
                MessageHandler(Filters.text & ~Filters.command,
                               lambda update, context: update.message.reply_text("Выберите пункт из меню!"))
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    order_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_order_form, pattern="^continue_order$")],
        states={
            REQUEST_NAME: [
                MessageHandler(Filters.text & ~Filters.command, request_name),
                MessageHandler(Filters.all,
                               lambda update, context: update.message.reply_text("Пожалуйста, введите ФИО текстом."))
            ],
            REQUEST_PHONE: [
                MessageHandler(Filters.text & ~Filters.command, request_phone),
                MessageHandler(Filters.all, lambda update, context: update.message.reply_text(
                    "Введите номер телефона в формате +79001234567."))
            ],
            REQUEST_START_DATE: [
                MessageHandler(Filters.text & ~Filters.command, request_start_date),
                MessageHandler(Filters.all,
                               lambda update, context: update.message.reply_text("Введите дату в формате ДД.ММ.ГГГГ."))
            ],
            REQUEST_DURATION: [
                MessageHandler(Filters.text & ~Filters.command, request_duration),
                MessageHandler(Filters.all, lambda update, context: update.message.reply_text(
                    "Введите срок хранения числом (например: 30)."))
            ],
            REQUEST_ADDRESS: [
                MessageHandler(Filters.text & ~Filters.command, request_address),
                MessageHandler(Filters.all, lambda update, context: update.message.reply_text(
                    "Введите адрес в формате: г. Москва, ул. Ленина, д. 10"))
            ],
            MAIN_MENU: [
                MessageHandler(Filters.regex("^(Мой заказ|Тарифы и условия хранения|Заказать ячейку)$"),
                               start_order_form)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    dispatcher.add_handler(main_conv_handler)  # Основной ConversationHandler
    dispatcher.add_handler(order_conv_handler) # Отдельный ConversationHandler для оформления заказа
    dispatcher.add_handler(CallbackQueryHandler(handle_courier_delivery, pattern="^deliver_courier$"))
    dispatcher.add_handler(CallbackQueryHandler(handle_self_delivery, pattern="^self_delivery$"))
    dispatcher.add_handler(CallbackQueryHandler(start_order_form, pattern="^continue_order$"))

    # Запуск бота
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()

