import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, CallbackContext
from telegram.ext import Filters
from datetime import datetime
from config import BOT_TOKEN
from database import init_db, save_order, get_new_orders, get_order_by_id, update_order_status, get_orders_stats, \
    get_new_orders_by_category, get_orders_count_by_category, get_master_active_orders, assign_order_to_master, \
    complete_order, get_completed_orders_with_master, get_master_earnings

# Простые категории прямо в коде
REPAIR_CATEGORIES = {
    "plumbing": "Сантехника 🚿",
    "electrical": "Электрика ⚡",
    "appliances": "Бытовая техника 🌀",
    "furniture": "Сборка мебели 🛋️",
    "doors_windows": "Двери/Окна 🚪",
    "other": "Прочее 🔧"
}

# Глобальный словарь для отслеживания состояния пользователей
user_states = {}

# Список ID администраторов/мастеров
ADMIN_IDS = [5172832447]  # Замените на ваш Telegram ID

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def start_command(update: Update, context: CallbackContext):
    """Команда /start для обычных пользователей"""
    user_id = update.effective_user.id
    user_states[user_id] = 'awaiting_category'

    keyboard = []
    for category_key, category_name in REPAIR_CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(category_name, callback_data=f"category_{category_key}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        f"Привет, {update.effective_user.first_name}! 👋\n"
        "У вас что-то сломалось? Не беда! Я помогу найти проверенного мастера в Таганроге.\n"
        "Выберите категорию:",
        reply_markup=reply_markup
    )


def admin_command(update: Update, context: CallbackContext):
    """Команда /admin только для мастеров"""
    user_id = update.effective_user.id

    if user_id not in ADMIN_IDS:
        update.message.reply_text("⛔ Доступ запрещен. Эта команда только для мастеров.")
        return

    show_admin_panel(update, context)


def show_admin_panel(update: Update, context: CallbackContext):
    """Показать панель управления для мастеров"""
    user_id = update.effective_user.id
    stats = get_orders_stats()

    active_orders = get_master_active_orders(user_id)
    has_active_order = len(active_orders) > 0

    admin_text = (
        "👨‍🔧 *Панель управления мастера*\n\n"
        f"📊 Статистика заявок:\n"
        f"• Всего: {stats['total']}\n"
        f"• Новые: {stats['new']}\n"
        f"• В работе: {stats['in_progress']}\n"
        f"• Завершено: {stats['completed']}\n\n"
    )

    if has_active_order:
        order = active_orders[0]
        admin_text += (
            "📋 *Ваша текущая заявка:*\n"
            f"• *Заявка #*: {order[0]}\n"
            f"• *Категория:* {order[3]}\n"
            f"• *Клиент:* {order[2]}\n"
            f"• *Описание:* {order[4]}\n"
            f"• *Контакты:* {order[5]}\n"
            f"• *Принята:* {order[9]}\n\n"
        )

    admin_text += "Выберите действие:"

    keyboard = [
        [InlineKeyboardButton("📂 Просмотреть заявки", callback_data="admin_show_categories")],
    ]

    if has_active_order:
        order_id = active_orders[0][0]
        keyboard.append([InlineKeyboardButton("📋 Моя заявка в работе", callback_data=f"show_my_order_{order_id}")])

    keyboard.extend([
        [InlineKeyboardButton("🔄 Обновить статистику", callback_data="admin_refresh")],
        [InlineKeyboardButton("❌ Закрыть панель", callback_data="admin_close")]
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        update.callback_query.edit_message_text(admin_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        update.message.reply_text(admin_text, reply_markup=reply_markup, parse_mode='Markdown')


def show_category_selection(update: Update, context: CallbackContext):
    """Показать выбор категорий для просмотра заявок с количеством заявок"""
    query = update.callback_query
    query.answer()

    category_counts = {}
    for category_key in REPAIR_CATEGORIES.keys():
        count = get_orders_count_by_category(category_key)
        category_counts[category_key] = count

    keyboard = []
    for category_key, category_name in REPAIR_CATEGORIES.items():
        count = category_counts[category_key]
        button_text = f"{category_name} ({count})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"admin_category_{category_key}")])

    total_new = get_orders_stats()['new']
    keyboard.append([InlineKeyboardButton(f"📋 Все заявки ({total_new})", callback_data="admin_all_orders")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(
        "📂 Выберите категорию для просмотра заявок:\n(в скобках указано количество новых заявок)",
        reply_markup=reply_markup
    )


def show_single_order(update: Update, context: CallbackContext, category_key=None):
    """Показать одну заявку с навигацией"""
    query = update.callback_query
    query.answer()

    if category_key == "all":
        orders = get_new_orders()
        category_name = "Все заявки"
    else:
        orders = get_new_orders_by_category(category_key)
        category_name = REPAIR_CATEGORIES.get(category_key, "Неизвестная категория")

    if not orders:
        query.edit_message_text(
            f"📭 Нет новых заявок в категории '{category_name}'\n\n"
            "Новых заявок пока нет. Проверьте позже.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К выбору категорий", callback_data="admin_show_categories")]
            ])
        )
        return

    current_index = context.user_data.get('current_order_index', 0)

    if current_index >= len(orders):
        current_index = 0
    if current_index < 0:
        current_index = len(orders) - 1

    order = orders[current_index]
    order_id = order[0]
    username = order[2]
    order_category = order[3]
    description = order[4]
    contacts = order[5]
    created_at = order[9]

    order_text = (
        f"🎯 *Заявка #{order_id}* ({category_name})\n"
        f"*{current_index + 1} из {len(orders)}*\n\n"
        f"• *Категория:* {order_category}\n"
        f"• *Пользователь:* {username}\n"
        f"• *Описание:* {description}\n"
        f"• *Контакты:* {contacts}\n"
        f"• *Создана:* {created_at}\n\n"
        "Выберите действие:"
    )

    keyboard = []
    keyboard.append([InlineKeyboardButton("✅ Взять в работу", callback_data=f"take_{order_id}")])

    if len(orders) > 1:
        nav_buttons = []
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"prev_{order_id}_{category_key}"))
        nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"next_{order_id}_{category_key}"))
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 К категориям", callback_data="admin_show_categories")])

    context.user_data['current_order_index'] = current_index
    context.user_data['current_orders'] = orders
    context.user_data['current_category'] = category_key

    query.edit_message_text(
        order_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


def handle_admin_actions(update: Update, context: CallbackContext):
    """Обработка действий в панели администратора"""
    query = update.callback_query
    query.answer()

    data = query.data
    master_id = update.effective_user.id
    master_name = update.effective_user.first_name

    if data == "admin_show_categories":
        show_category_selection(update, context)

    elif data == "admin_refresh":
        query.answer("Статистика обновлена! ✅")

    elif data == "admin_back":
        show_admin_panel(update, context)

    elif data == "admin_close":
        query.edit_message_text("Панель управления закрыта")

    elif data == "admin_all_orders":
        context.user_data['current_order_index'] = 0
        show_single_order(update, context, "all")

    elif data.startswith("admin_category_"):
        category_key = data.split("_")[2]
        context.user_data['current_order_index'] = 0
        show_single_order(update, context, category_key)

    elif data.startswith("take_"):
        active_orders = get_master_active_orders(master_id)
        if active_orders:
            query.answer(
                "⛔ У вас уже есть активная заявка!\n"
                "Завершите текущую заявку прежде чем брать новую.",
                show_alert=True
            )
            return

        order_id = data.split("_")[1]
        assign_order_to_master(order_id, master_id, master_name)
        current_category = context.user_data.get('current_category', 'all')

        query.edit_message_text(
            f"✅ Заявка #{order_id} взята в работу!\n\n"
            f"Мастер: {master_name}\n"
            "Свяжитесь с клиентом в ближайшее время.\n\n"
            "Когда завершите заявку, используйте команду /complete",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К заявкам", callback_data=f"admin_back_to_{current_category}")]
            ])
        )

    elif data.startswith("admin_back_to_"):
        category_key = data.split("_")[3]
        context.user_data['current_order_index'] = 0
        show_single_order(update, context, category_key)

    elif data.startswith("show_my_order_"):
        order_id = data.split("_")[3]
        show_my_active_order(update, context, order_id)

    elif data.startswith("next_"):
        parts = data.split("_")
        if len(parts) >= 3:
            category_key = parts[2]
            current_index = context.user_data.get('current_order_index', 0)
            context.user_data['current_order_index'] = current_index + 1
            show_single_order(update, context, category_key)

    elif data.startswith("prev_"):
        parts = data.split("_")
        if len(parts) >= 3:
            category_key = parts[2]
            current_index = context.user_data.get('current_order_index', 0)
            context.user_data['current_order_index'] = current_index - 1
            show_single_order(update, context, category_key)

    elif data.startswith("complete_"):
        order_id = data.split("_")[1]
        complete_order(order_id)
        query.edit_message_text(
            f"✅ Заявка #{order_id} завершена!\n\n"
            "Теперь вы можете брать новые заявки через /admin"
        )


def complete_command(update: Update, context: CallbackContext):
    """Команда для завершения заявки"""
    user_id = update.effective_user.id

    if user_id not in ADMIN_IDS:
        update.message.reply_text("⛔ Доступ запрещен.")
        return

    active_orders = get_master_active_orders(user_id)

    if not active_orders:
        update.message.reply_text(
            "У вас нет активных заявок для завершения.\n"
            "Используйте /admin для просмотра заявок."
        )
        return

    keyboard = []
    for order in active_orders:
        order_id = order[0]
        category = order[3]
        keyboard.append(
            [InlineKeyboardButton(f"Заявка #{order_id} - {category}", callback_data=f"complete_{order_id}")])

    update.message.reply_text(
        "Выберите заявку для завершения:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def handle_complete_actions(update: Update, context: CallbackContext):
    """Обработка завершения заявок"""
    query = update.callback_query
    query.answer()

    data = query.data

    if data.startswith("complete_"):
        order_id = data.split("_")[1]
        complete_order(order_id)
        query.edit_message_text(
            f"✅ Заявка #{order_id} завершена!\n\n"
            "Теперь вы можете брать новые заявки через /admin"
        )


def handle_category_selection(update: Update, context: CallbackContext):
    """Обработка выбора категории пользователем"""
    query = update.callback_query
    query.answer()

    user_id = update.effective_user.id

    if query.data.startswith("category_"):
        category_key = query.data[9:]

        if category_key in REPAIR_CATEGORIES:
            category_name = REPAIR_CATEGORIES[category_key]
            context.user_data['category'] = category_key
            context.user_data['category_name'] = category_name
            user_states[user_id] = 'awaiting_description'

            query.edit_message_text(
                text=f"Вы выбрали: {category_name}\n\n"
                     "Теперь подробно опишите, что случилось:"
            )

        else:
            query.edit_message_text("Категория не найдена. Нажмите /start")
            user_states[user_id] = 'main'


def handle_text_messages(update: Update, context: CallbackContext):
    """Умный обработчик для всех текстовых сообщений"""
    user_id = update.effective_user.id
    current_state = user_states.get(user_id, 'main')
    user_text = update.message.text

    if current_state == 'awaiting_description':
        context.user_data['description'] = user_text
        user_states[user_id] = 'awaiting_contacts'

        update.message.reply_text(
            "Спасибо за описание! 📝\n\n"
            "Теперь укажите, пожалуйста:\n"
            "• Ваш номер телефона для связи\n"
            "• Адрес, куда приехать мастеру\n\n"
            "Например:\n"
            "+7 900 123-45-67\n"
            "ул. Ленина, д. 10, кв. 25"
        )

    elif current_state == 'awaiting_contacts':
        context.user_data['contacts'] = user_text
        category = context.user_data.get('category_name', 'Не указана')
        description = context.user_data.get('description', 'Не указано')
        username = update.effective_user.username or update.effective_user.first_name

        order_id = save_order(user_id, username, category, description, user_text)

        order_text = (
            "✅ *Заявка создана!*\n\n"
            f"*Номер заявки:* #{order_id}\n"
            f"*Категория:* {category}\n"
            f"*Описание:* {description}\n"
            f"*Контакты:* {user_text}\n\n"
            "Мастер свяжется с вами в ближайшее время! ⏰"
        )

        update.message.reply_text(order_text, parse_mode='Markdown')
        user_states[user_id] = 'main'

    else:
        update.message.reply_text("Нажмите /start чтобы создать новую заявку")


def show_my_active_order(update: Update, context: CallbackContext, order_id):
    """Показать активную заявку мастера"""
    query = update.callback_query
    query.answer()

    order = get_order_by_id(order_id)
    if not order:
        query.edit_message_text("Заявка не найдена.")
        return

    order_id, user_id, username, category, description, contacts, status, master_id, master_name, created_at = order

    order_text = (
        "📋 *Ваша активная заявка*\n\n"
        f"• *Заявка #*: {order_id}\n"
        f"• *Категория:* {category}\n"
        f"• *Клиент:* {username}\n"
        f"• *Описание:* {description}\n"
        f"• *Контакты:* {contacts}\n"
        f"• *Принята:* {created_at}\n"
        f"• *Статус:* В работе\n\n"
        "Выберите действие:"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Завершить заявку", callback_data=f"complete_{order_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
    ]

    query.edit_message_text(
        order_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


def finance_command(update: Update, context: CallbackContext):
    """Команда для финансовой отчетности"""
    user_id = update.effective_user.id

    if user_id not in ADMIN_IDS:
        update.message.reply_text("⛔ Доступ запрещен.")
        return

    completed_orders = get_completed_orders_with_master()
    total_orders = len(completed_orders)
    your_earnings = total_orders * 500  # 500 руб. с заказа

    finance_text = (
        "💰 *ФИНАНСОВАЯ ОТЧЕТНОСТЬ*\n\n"
        f"• Всего выполнено заказов: {total_orders}\n"
        f"• Ваш заработок (10%): {your_earnings} руб.\n\n"
    )

    if total_orders > 0:
        finance_text += "📊 *Последние заказы:*\n\n"

        for order in completed_orders[:5]:
            order_id, master_id, master_name, category, created_at = order
            finance_text += f"• Заявка #{order_id} - {category}\n"
            finance_text += f"  Мастер: {master_name}\n"
            finance_text += f"  Завершена: {created_at}\n\n"

        masters_stats = {}
        for order in completed_orders:
            master_id = order[1]
            masters_stats[master_id] = masters_stats.get(master_id, 0) + 1

        finance_text += "👨‍🔧 *По мастерам:*\n"
        for master_id, orders_count in masters_stats.items():
            finance_text += f"• Мастер {master_id}: {orders_count} зак.\n"
    else:
        finance_text += "📭 Пока нет выполненных заказов"

    update.message.reply_text(finance_text, parse_mode='Markdown')


def status_command(update: Update, context: CallbackContext):
    """Проверка статуса бота"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    stats = get_orders_stats()
    status_text = (
        "🤖 *Статус бота*\n\n"
        f"• Запущен: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"• Заявок всего: {stats['total']}\n"
        f"• Новых: {stats['new']}\n"
        f"• В работе: {stats['in_progress']}\n"
        f"• Завершено: {stats['completed']}\n"
        f"• Мастеров: {len(ADMIN_IDS) - 1}\n"
        "• Статус: ✅ Работает"
    )
    update.message.reply_text(status_text, parse_mode='Markdown')


def main():
    print("Запускаем бота...")
    init_db()
    print("База данных готова")

    updater = Updater(BOT_TOKEN, use_context=True)
    application = updater.dispatcher

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("complete", complete_command))
    application.add_handler(CommandHandler("finance", finance_command))
    application.add_handler(CommandHandler("status", status_command))

    application.add_handler(CallbackQueryHandler(handle_category_selection, pattern="^category_"))
    application.add_handler(CallbackQueryHandler(handle_complete_actions, pattern="^complete_"))
    application.add_handler(CallbackQueryHandler(handle_admin_actions))

    application.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text_messages))

    print("Бот запущен!")
    print("• /start - для пользователей")
    print("• /admin - для мастеров (просмотр заявок)")
    print("• /complete - для мастеров (завершение заявок)")
    print("• /finance - финансовая отчетность")
    print("• /status - статус бота")

    updater.start_polling(
        allowed_updates=['message', 'callback_query'],
        drop_pending_updates=True
    )
    updater.idle()


if __name__ == "__main__":
    main()