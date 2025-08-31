
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from config import BOT_TOKEN
from database import init_db, save_order, get_new_orders, get_order_by_id, update_order_status, get_orders_stats, \
    get_new_orders_by_category, get_orders_count_by_category, get_master_active_orders, assign_order_to_master, \
    complete_order, get_completed_orders_with_master

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

# Список ID администраторов/мастеров (ЗАМЕНИТЕ НА СВОЙ ID)
ADMIN_IDS = [5172832447]  # Замените на ваш Telegram ID (узнать через @userinfobot)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start для обычных пользователей"""
    user_id = update.effective_user.id

    # Сбрасываем состояние пользователя
    user_states[user_id] = 'awaiting_category'

    print("Команда /start получена от пользователя!")

    # Создаем инлайн-клавиатуру с категориями
    keyboard = []
    for category_key, category_name in REPAIR_CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(category_name, callback_data=f"category_{category_key}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    print("Клавиатура создана, отправляем сообщение...")

    await update.message.reply_text(
        f"Привет, {update.effective_user.first_name}! 👋\n"
        "У вас что-то сломалось? Не беда! Я помогу найти проверенного мастера в Таганроге.\n"
        "Выберите категорию:",
        reply_markup=reply_markup
    )
    print("Сообщение отправлено!")


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /admin только для мастеров"""
    user_id = update.effective_user.id

    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен. Эта команда только для мастеров.")
        return

    print("Команда /admin получена от мастера!")
    await show_admin_panel(update, context)


async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать панель управления для мастеров"""
    user_id = update.effective_user.id
    stats = get_orders_stats()

    # Проверяем, есть ли у мастера активная заявка
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

    # Добавляем информацию о текущей заявке мастера
    if has_active_order:
        order = active_orders[0]
        order_id = order[0]
        category = order[3]
        description = order[4]
        contacts = order[5]
        username = order[2]
        created_at = order[9]

        admin_text += (
            "📋 *Ваша текущая заявка:*\n"
            f"• *Заявка #*: {order_id}\n"
            f"• *Категория:* {category}\n"
            f"• *Клиент:* {username}\n"
            f"• *Описание:* {description}\n"
            f"• *Контакты:* {contacts}\n"
            f"• *Принята:* {created_at}\n\n"
        )

    admin_text += "Выберите действие:"

    keyboard = [
        [InlineKeyboardButton("📂 Просмотреть заявки", callback_data="admin_show_categories")],
    ]

    # Добавляем кнопку для текущей заявки если она есть
    if has_active_order:
        order_id = active_orders[0][0]
        keyboard.append([InlineKeyboardButton("📋 Моя заявка в работе", callback_data=f"show_my_order_{order_id}")])

    keyboard.extend([
        [InlineKeyboardButton("🔄 Обновить статистику", callback_data="admin_refresh")],
        [InlineKeyboardButton("❌ Закрыть панель", callback_data="admin_close")]
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(admin_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(admin_text, reply_markup=reply_markup, parse_mode='Markdown')


async def show_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор категорий для просмотра заявок с количеством заявок"""
    query = update.callback_query
    await query.answer()
    print("Показываем выбор категорий для админа")

    # Получаем количество заявок по категориям
    category_counts = {}
    for category_key in REPAIR_CATEGORIES.keys():
        count = get_orders_count_by_category(category_key)
        category_counts[category_key] = count

    keyboard = []
    # Добавляем кнопки для всех категорий с количеством заявок
    for category_key, category_name in REPAIR_CATEGORIES.items():
        count = category_counts[category_key]
        button_text = f"{category_name} ({count})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"admin_category_{category_key}")])

    # Кнопка "Все заявки" с общим количеством
    total_new = get_orders_stats()['new']
    keyboard.append([InlineKeyboardButton(f"📋 Все заявки ({total_new})", callback_data="admin_all_orders")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📂 Выберите категорию для просмотра заявок:\n(в скобках указано количество новых заявок)",
        reply_markup=reply_markup
    )


async def show_single_order(update: Update, context: ContextTypes.DEFAULT_TYPE, category_key=None):
    """Показать одну заявку с навигацией"""
    query = update.callback_query
    await query.answer()

    if category_key == "all":
        orders = get_new_orders()
        category_name = "Все заявки"
    else:
        orders = get_new_orders_by_category(category_key)
        category_name = REPAIR_CATEGORIES.get(category_key, "Неизвестная категория")

    if not orders:
        await query.edit_message_text(
            f"📭 Нет новых заявок в категории '{category_name}'\n\n"
            "Новых заявок пока нет. Проверьте позже.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К выбору категорий", callback_data="admin_show_categories")]
            ])
        )
        return

    # Получаем индекс текущей заявки из контекста или начинаем с первой
    current_index = context.user_data.get('current_order_index', 0)

    # Циклическая навигация: если индекс вне диапазона, начинаем сначала
    if current_index >= len(orders):
        current_index = 0
    if current_index < 0:
        current_index = len(orders) - 1

    order = orders[current_index]
    # Теперь в order 10 значений: id, user_id, username, category, description, contacts, status, master_id, master_name, created_at
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

    # Кнопки навигации если заявок больше одной
    if len(orders) > 1:
        nav_buttons = []
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"prev_{order_id}_{category_key}"))
        nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"next_{order_id}_{category_key}"))
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 К категориям", callback_data="admin_show_categories")])

    # Сохраняем индекс для навигации
    context.user_data['current_order_index'] = current_index
    context.user_data['current_orders'] = orders
    context.user_data['current_category'] = category_key

    await query.edit_message_text(
        order_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def show_single_order_direct(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id):
    """Показать конкретную заявку по ID"""
    query = update.callback_query
    await query.answer()

    order = get_order_by_id(order_id)
    if not order:
        await query.edit_message_text("❌ Заявка не найдена.")
        return

    # Создаем словарь для удобного доступа к данным
    order_data = {
        'id': order[0],
        'user_id': order[1],
        'username': order[2],
        'category': order[3],
        'description': order[4],
        'contacts': order[5],
        'status': order[6],
        'master_id': order[7],
        'master_name': order[8],
        'created_at': order[9]
    }

    order_text = (
        f"🎯 *Заявка #{order_data['id']}*\n\n"
        f"*Статус:* {order_data['status']}\n"
        f"*Категория:* {order_data['category']}\n"
        f"*Клиент:* @{order_data['username'] if order_data['username'] else 'без username'}\n"
        f"*Описание:* {order_data['description']}\n"
        f"*Контакты:* {order_data['contacts']}\n"
        f"*Создана:* {order_data['created_at']}\n\n"
    )

    keyboard = []

    if order_data['status'] == 'new':
        order_text += "_Заявка ожидает мастера_"
        keyboard.append([InlineKeyboardButton("✅ Взять в работу", callback_data=f"take_{order_data['id']}")])
    elif order_data['status'] == 'in_progress':
        order_text += f"*Мастер:* {order_data['master_name']}\n"
        order_text += "_Заявка в работе_"
        # Если это заявка текущего мастера
        if order_data['master_id'] == query.from_user.id:
            keyboard.append([InlineKeyboardButton("✅ Завершить заявку", callback_data=f"complete_{order_data['id']}")])
    else:
        order_text += f"*Мастер:* {order_data['master_name']}\n"
        order_text += "_Заявка завершена_"

    keyboard.append([InlineKeyboardButton("📋 Все заявки", callback_data="admin_show_categories")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])

    try:
        await query.edit_message_text(
            order_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Ошибка при редактировании сообщения: {e}")
        await query.message.reply_text(
            order_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )


async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действий в панели администратора"""
    query = update.callback_query
    await query.answer()

    data = query.data
    master_id = update.effective_user.id
    master_name = update.effective_user.first_name

    print(f"Админ действие: {data}")

    # Обработка перехода к конкретной заявке
    if data.startswith("admin_show_order_"):
        order_id = data.split("_")[3]
        print(f"Переход к заявке #{order_id}")
        await show_single_order_direct(update, context, order_id)
        return

    elif data == "admin_show_categories":
        await show_category_selection(update, context)

    elif data == "admin_refresh":
        await query.answer("Статистика обновлена! ✅")
        # Можно обновить сообщение
        await show_admin_panel(update, context)

    elif data == "admin_back":
        await show_admin_panel(update, context)

    elif data == "admin_close":
        await query.edit_message_text("Панель управления закрыта")

    elif data == "admin_all_orders":
        context.user_data['current_order_index'] = 0
        await show_single_order(update, context, "all")

    elif data.startswith("admin_category_"):
        category_key = data.split("_")[2]
        context.user_data['current_order_index'] = 0
        await show_single_order(update, context, category_key)

    elif data.startswith("take_"):
        # Проверяем, нет ли у мастера уже активных заявок
        active_orders = get_master_active_orders(master_id)
        if active_orders:
            await query.answer(
                "⛔ У вас уже есть активная заявка!\n"
                "Завершите текущую заявку прежде чем брать новую.",
                show_alert=True
            )
            return

        order_id = data.split("_")[1]
        success = assign_order_to_master(order_id, master_id, master_name)

        if success:
            current_category = context.user_data.get('current_category', 'all')

            await query.edit_message_text(
                f"✅ Заявка #{order_id} взята в работу!\n\n"
                f"Мастер: {master_name}\n"
                "Свяжитесь с клиентом в ближайшее время.\n\n"
                "Когда завершите заявку, используйте команду /complete",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 К заявкам", callback_data=f"admin_back_to_{current_category}")]
                ])
            )
        else:
            await query.answer("❌ Заявка уже взята другим мастером!", show_alert=True)

    elif data.startswith("admin_back_to_"):
        category_key = data.split("_")[3]
        context.user_data['current_order_index'] = 0
        await show_single_order(update, context, category_key)

    elif data.startswith("show_my_order_"):
        order_id = data.split("_")[3]
        await show_my_active_order(update, context, order_id)

    elif data.startswith("next_"):
        parts = data.split("_")
        if len(parts) >= 3:
            category_key = parts[2]
            current_index = context.user_data.get('current_order_index', 0)
            context.user_data['current_order_index'] = current_index + 1
            await show_single_order(update, context, category_key)

    elif data.startswith("prev_"):
        parts = data.split("_")
        if len(parts) >= 3:
            category_key = parts[2]
            current_index = context.user_data.get('current_order_index', 0)
            context.user_data['current_order_index'] = current_index - 1
            await show_single_order(update, context, category_key)

    elif data.startswith("complete_"):
        order_id = data.split("_")[1]
        complete_order(order_id)

        await query.edit_message_text(
            f"✅ Заявка #{order_id} завершена!\n\n"
            "Теперь вы можете брать новые заявки через /admin"
        )

    else:
        # Если действие не распознано
        print(f"Неизвестное действие: {data}")
        await query.answer("Неизвестное действие")


async def complete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для завершения заявки"""
    user_id = update.effective_user.id

    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return

    # Получаем активные заявки мастера
    active_orders = get_master_active_orders(user_id)

    if not active_orders:
        await update.message.reply_text(
            "У вас нет активных заявок для завершения.\n"
            "Используйте /admin для просмотра заявок."
        )
        return

    # Показываем активные заявки для завершения
    keyboard = []
    for order in active_orders:
        order_id = order[0]  # order[0] - id заявки
        category = order[3]  # order[3] - категория
        keyboard.append(
            [InlineKeyboardButton(f"Заявка #{order_id} - {category}", callback_data=f"complete_{order_id}")])

    await update.message.reply_text(
        "Выберите заявку для завершения:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора категории пользователем"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    if query.data.startswith("category_"):
        category_key = query.data[9:]  # Убираем "category_"

        if category_key in REPAIR_CATEGORIES:
            category_name = REPAIR_CATEGORIES[category_key]
            print(f"Выбрана категория: {category_name}")

            # Сохраняем данные
            context.user_data['category'] = category_key
            context.user_data['category_name'] = category_name
            user_states[user_id] = 'awaiting_description'

            # Обновляем сообщение
            await query.edit_message_text(
                text=f"Вы выбрали: {category_name}\n\n"
                     "Теперь подробно опишите, что случилось:"
            )
            print("Ожидаем описание проблемы...")

        else:
            await query.edit_message_text("Категория не найдена. Нажмите /start")
            user_states[user_id] = 'main'


async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Умный обработчик для всех текстовых сообщений"""
    user_id = update.effective_user.id
    current_state = user_states.get(user_id, 'main')
    user_text = update.message.text

    print(f"Получено сообщение в состоянии '{current_state}': {user_text}")

    if current_state == 'awaiting_description':
        # Сохраняем описание проблемы
        context.user_data['description'] = user_text
        user_states[user_id] = 'awaiting_contacts'

        print(f"Описание сохранено: {user_text}")

        # Запрашиваем контакты
        await update.message.reply_text(
            "Спасибо за описание! 📝\n\n"
            "Теперь укажите, пожалуйста:\n"
            "• Ваш номер телефона для связи\n"
            "• Адрес, куда приехать мастеру\n\n"
            "Например:\n"
            "+7 900 123-45-67\n"
            "ул. Ленина, д. 10, кв. 25"
        )
        print("Ожидаем контактные данные...")

    elif current_state == 'awaiting_contacts':
        # Сохраняем контакты
        context.user_data['contacts'] = user_text

        # Формируем данные для сохранения
        category = context.user_data.get('category_name', 'Не указана')
        description = context.user_data.get('description', 'Не указано')
        username = update.effective_user.username or update.effective_user.first_name

        # СОХРАНЯЕМ ЗАЯВКУ В БАЗУ ДАННЫХ И ПОЛУЧАЕМ ID
        order_id = save_order(user_id, username, category, description, user_text)
        print(f"Заявка #{order_id} сохранена в базе данных!")

        # ⭐⭐⭐ ОТПРАВЛЯЕМ УВЕДОМЛЕНИЯ МАСТЕРАМ ⭐⭐⭐
        try:
            await notify_masters_new_order(context, order_id, category, description)
        except Exception as e:
            print(f"Ошибка при отправке уведомлений: {e}")

        # Формируем сообщение для пользователя
        order_text = (
            "✅ *Заявка создана!*\n\n"
            f"*Номер заявки:* #{order_id}\n"
            f"*Категория:* {category}\n"
            f"*Описание:* {description}\n"
            f"*Контакты:* {user_text}\n\n"
            "Мастер свяжется с вами в ближайшее время! ⏰\n"
            "Обычно это занимает 10-30 минут."
        )

        await update.message.reply_text(order_text, parse_mode='Markdown')

        # Сбрасываем состояние
        user_states[user_id] = 'main'

        # Выводим заявку в консоль
        print(f"\n=== НОВАЯ ЗАЯВКА #{order_id} ===")
        print(f"Пользователь: {username} (ID: {user_id})")
        print(f"Категория: {category}")
        print(f"Описание: {description}")
        print(f"Контакты: {user_text}")
        print("Уведомления отправлены мастерам")
        print("=====================\n")

    else:
        # Если не в процессе создания заявки
        await update.message.reply_text(
            "Для создания новой заявки нажмите /start\n\n"
            "Если у вас есть вопросы, напишите нам: @ваш_аккаунт"
        )


async def handle_complete_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка завершения заявок"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("complete_"):
        order_id = data.split("_")[1]
        complete_order(order_id)

        await query.edit_message_text(
            f"✅ Заявка #{order_id} завершена!\n\n"
            "Теперь вы можете брать новые заявки через /admin"
        )


async def show_my_active_order(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id):
    """Показать активную заявку мастера"""
    query = update.callback_query
    await query.answer()

    order = get_order_by_id(order_id)
    if not order:
        await query.edit_message_text("Заявка не найдена.")
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

    await query.edit_message_text(
        order_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def finance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для финансовой отчетности (только для вас)"""
    try:
        user_id = update.effective_user.id

        if user_id != 5172832447:  # ← ВАШ ID
            await update.message.reply_text("⛔ Доступ запрещен.")
            return

        # Получаем статистику
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
                finance_text += f"  Создана: {created_at}\n\n"

            masters_stats = {}
            for order in completed_orders:
                master_id = order[1]
                masters_stats[master_id] = masters_stats.get(master_id, 0) + 1

            finance_text += "👨‍🔧 *По мастерам:*\n"
            for master_id, orders_count in masters_stats.items():
                finance_text += f"• Мастер {master_id}: {orders_count} зак.\n"
        else:
            finance_text += "📭 Пока нет выполненных заказов"

        await update.message.reply_text(finance_text, parse_mode='Markdown')

    except Exception as e:
        print(f"Ошибка: {e}")
        await update.message.reply_text("⚠️ Ошибка формирования отчета")


async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение получения оплаты от мастера"""
    user_id = update.effective_user.id
    if user_id != 5172832447:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return

    # Логика подтверждения платежа
    # Можно добавить инлайн-кнопки с суммами
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить платеж 500 руб.", callback_data="confirm_500")],
        [InlineKeyboardButton("✅ Подтвердить платеж 1000 руб.", callback_data="confirm_1000")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_payment")]
    ]

    await update.message.reply_text(
        "Подтвердите получение платежа от мастера:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def notify_masters_new_order(context, order_id, category, description):
    """Уведомление с разными сообщениями для админа и мастеров"""
    short_description = description[:100] + "..." if len(description) > 100 else description

    # Сообщение для мастера
    master_message = (
        "🎯 *НОВАЯ ЗАЯВКА!*\n\n"
        f"*Заявка #*: {order_id}\n"
        f"*Категория:* {category}\n"
        f"*Описание:* {short_description}\n\n"
        "➡️ Нажмите чтобы сразу перейти к заявке"
    )

    # Сообщение для админа (вас)
    admin_message = (
        "👑 *НОВАЯ ЗАЯВКА ДЛЯ АДМИНА*\n\n"
        f"*Заявка #*: {order_id}\n"
        f"*Категория:* {category}\n"
        f"*Описание:* {description}\n\n"
        "💵 Не забудьте получить 10% после выполнения!"
    )

    # Клавиатура для перехода к заявке
    keyboard = [
        [InlineKeyboardButton("🚀 Перейти к заявке", callback_data=f"admin_show_order_{order_id}")],
        [InlineKeyboardButton("📋 Все заявки", callback_data="admin_show_categories")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    print(f"Отправляем уведомления о заявке #{order_id}")

    for master_id in ADMIN_IDS:
        try:
            if master_id == ADMIN_IDS[0]:  # Это вы (админ)
                await context.bot.send_message(
                    chat_id=master_id,
                    text=admin_message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:  # Обычные мастера
                await context.bot.send_message(
                    chat_id=master_id,
                    text=master_message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            print(f"✅ Уведомление отправлено ID {master_id}")
        except Exception as e:
            print(f"❌ Не удалось отправить уведомление ID {master_id}: {e}")


# Вызывайте эту функцию после save_order()


def main():
    print("Запускаем бота...")
    init_db()
    print("База данных готова")

    application = Application.builder().token(BOT_TOKEN).build()

    # СНАЧАЛА команды - они имеют приоритет
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("complete", complete_command))
    application.add_handler(CommandHandler("finance", finance_command))  # ← ДОБАВЬТЕ ЭТУ СТРОЧКУ

    # ПОТОМ обработчики callback'ов
    application.add_handler(CallbackQueryHandler(handle_category_selection, pattern="^category_"))
    application.add_handler(CallbackQueryHandler(handle_complete_actions, pattern="^complete_"))
    application.add_handler(CallbackQueryHandler(handle_admin_actions, pattern="^admin_show_order_"))
    application.add_handler(CallbackQueryHandler(handle_admin_actions))

    # И только ПОСЛЕДНИМИ текстовые сообщения
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text_messages
    ))

    print("Бот запущен!")
    application.run_polling(allowed_updates=['message', 'callback_query'])
    print("• /start - для пользователей")
    print("• /admin - для мастеров (просмотр заявок)")
    print("• /complete - для мастеров (завершение заявок)")
    application.run_polling(
        allowed_updates=['message', 'callback_query'],
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()