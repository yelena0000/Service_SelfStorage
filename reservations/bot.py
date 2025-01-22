import telegram
from telegram import (
    Bot,
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    ConversationHandler,
    MessageHandler,
    Filters,
)
from environs import Env

# Состояния для диалога
CONSENT, MAIN_MENU = range(2)

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
    pdf_file = "reservations/consent_form.pdf"
    context.bot.send_document(chat_id=update.effective_chat.id, document=open(pdf_file, "rb"))

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
            [["Мой заказ", "Тарифы и условия хранения"], ["Заказать бокс"]],
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

def order_box(update: Update, context: CallbackContext):
    # Создаёт инлайн-кнопки для выбора способа доставки
    keyboard = [
        [InlineKeyboardButton("Доставить мои вещи курьером", callback_data="deliver_courier")],
        [InlineKeyboardButton("Привезу самостоятельно", callback_data="self_delivery")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        "Как вы хотите заказать бокс? Выберите один из вариантов ниже:",
        reply_markup=reply_markup
    )

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
    # Обработка выбора доставки курьером
    courier_info = (
        "📦 *Доставка курьером:*\n\n"
        "Мы бесплатно заберём ваши вещи из дома или офиса. Для этого:\n"
        "1️⃣ <сделайте ....>.\n"
        "2️⃣ <.....>\n\n"
        "📍 Курьер замерит вещи на месте."
    )
    update.callback_query.message.reply_text(
        courier_info,
        parse_mode=telegram.ParseMode.MARKDOWN
    )


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
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CONSENT: [MessageHandler(Filters.text & ~Filters.command, handle_consent)],
            MAIN_MENU: [
                MessageHandler(Filters.regex("Мой заказ"), handle_my_order),
                MessageHandler(Filters.regex("Тарифы и условия хранения"), tariffs),
                MessageHandler(Filters.regex("Заказать бокс"), order_box),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(telegram.ext.CallbackQueryHandler(handle_courier_delivery, pattern="^deliver_courier$"))
    dispatcher.add_handler(telegram.ext.CallbackQueryHandler(handle_self_delivery, pattern="^self_delivery$"))

    # Запуск бота
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()

