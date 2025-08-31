import sqlite3
from datetime import datetime


def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('orders.db')
    cur = conn.cursor()

    cur.execute('''CREATE TABLE IF NOT EXISTS orders (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER,
                 username TEXT,
                 category TEXT,
                 description TEXT,
                 contacts TEXT,
                 status TEXT DEFAULT 'new',
                 master_id INTEGER DEFAULT NULL,
                 master_name TEXT DEFAULT NULL,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 completed_at TIMESTAMP DEFAULT NULL)''')  # ← ДОБАВЛЕНО completed_at

    conn.commit()
    conn.close()
    print("База данных инициализирована")


def save_order(user_id, username, category, description, contacts):
    """Сохранение заявки в базу данных с возвратом ID"""
    conn = sqlite3.connect('orders.db')
    cur = conn.cursor()

    cur.execute("""INSERT INTO orders 
                 (user_id, username, category, description, contacts) 
                 VALUES (?, ?, ?, ?, ?)""",
                (user_id, username, category, description, contacts))

    order_id = cur.lastrowid  # Получаем ID созданной записи
    conn.commit()
    conn.close()
    print(f"Заявка #{order_id} сохранена для пользователя {username}")
    return order_id  # ← Возвращаем ID


def get_new_orders():
    """Получение ВСЕХ новых заявок (самые старые первыми)"""
    conn = sqlite3.connect('orders.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE status = 'new' ORDER BY created_at ASC")  # ASC вместо DESC
    orders = cur.fetchall()
    conn.close()
    return orders


def get_new_orders_by_category(category_key=None):
    """Получение новых заявок с фильтром по категории (самые старые первыми)"""
    conn = sqlite3.connect('orders.db')
    cur = conn.cursor()

    # Сопоставление ключей с human-readable названиями
    category_mapping = {
        "plumbing": "Сантехника 🚿",
        "electrical": "Электрика ⚡",
        "appliances": "Бытовая техника 🌀",
        "furniture": "Сборка мебели 🛋️",
        "doors_windows": "Двери/Окна 🚪",
        "other": "Прочее 🔧"
    }

    if category_key and category_key != "all":
        # Преобразуем ключ в human-readable название
        category_name = category_mapping.get(category_key, category_key)
        cur.execute("SELECT * FROM orders WHERE status = 'new' AND category = ? ORDER BY created_at ASC",
                    (category_name,))  # ASC вместо DESC
    else:
        # Для "all" или без категории - все заявки
        cur.execute("SELECT * FROM orders WHERE status = 'new' ORDER BY created_at ASC")  # ASC вместо DESC

    orders = cur.fetchall()
    conn.close()
    return orders


def get_order_by_id(order_id):
    """Получение заявки по ID"""
    conn = sqlite3.connect('orders.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cur.fetchone()
    conn.close()
    return order


def update_order_status(order_id, status):
    """Обновление статуса заявки"""
    conn = sqlite3.connect('orders.db')
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()
    print(f"Статус заявки {order_id} изменен на {status}")


def get_orders_stats():
    """Получение статистики по заявкам"""
    conn = sqlite3.connect('orders.db')
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM orders")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM orders WHERE status = 'new'")
    new = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM orders WHERE status = 'in_progress'")
    in_progress = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed'")
    completed = cur.fetchone()[0]

    conn.close()

    return {
        'total': total,
        'new': new,
        'in_progress': in_progress,
        'completed': completed
    }


def get_orders_count_by_category(category_key):
    """Получение количества новых заявок по категории"""
    conn = sqlite3.connect('orders.db')
    cur = conn.cursor()

    # Сопоставление ключей с human-readable названиями
    category_mapping = {
        "plumbing": "Сантехника 🚿",
        "electrical": "Электрика ⚡",
        "appliances": "Бытовая техника 🌀",
        "furniture": "Сборка мебели 🛋️",
        "doors_windows": "Двери/Окна 🚪",
        "other": "Прочее 🔧"
    }

    category_name = category_mapping.get(category_key, category_key)

    cur.execute("SELECT COUNT(*) FROM orders WHERE status = 'new' AND category = ?", (category_name,))
    count = cur.fetchone()[0]
    conn.close()
    return count


def assign_order_to_master(order_id, master_id, master_name):
    """Назначение заявки мастеру с проверкой"""
    conn = sqlite3.connect('orders.db')
    cur = conn.cursor()

    # Сначала проверяем, не взята ли уже заявка
    cur.execute("SELECT status, master_id FROM orders WHERE id = ?", (order_id,))
    order = cur.fetchone()

    if order and order[0] != 'new':
        conn.close()
        return False  # Заявка уже взята

    # Если заявка свободна - назначаем
    cur.execute("UPDATE orders SET status = 'in_progress', master_id = ?, master_name = ? WHERE id = ?",
                (master_id, master_name, order_id))
    conn.commit()
    conn.close()
    return True  # Успешно назначено


def get_master_active_orders(master_id):
    """Получение активных заявок мастера"""
    conn = sqlite3.connect('orders.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE master_id = ? AND status = 'in_progress'", (master_id,))
    orders = cur.fetchall()
    conn.close()
    return orders


def complete_order(order_id):
    """Завершение заявки с записью времени завершения"""
    conn = sqlite3.connect('orders.db')
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    print(f"Заявка #{order_id} завершена")


def get_completed_orders_with_master():
    """Получить все завершенные заказы с информацией о мастере"""
    conn = sqlite3.connect('orders.db')
    cur = conn.cursor()
    cur.execute("""
        SELECT id, master_id, master_name, category, created_at, completed_at 
        FROM orders 
        WHERE status = 'completed' 
        ORDER BY completed_at DESC
    """)
    orders = cur.fetchall()
    conn.close()
    return orders


def get_master_earnings(master_id):
    """Получить статистику заработка мастера"""
    conn = sqlite3.connect('orders.db')
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) as completed_orders 
        FROM orders 
        WHERE master_id = ? AND status = 'completed'
    """, (master_id,))
    stats = cur.fetchone()
    conn.close()
    return stats[0]  # Количество выполненных заказов