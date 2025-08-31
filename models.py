from enum import Enum

class OrderState(Enum):
    PENDING = "ожидает мастера"
    ACCEPTED = "принят мастером"
    COMPLETED = "выполнен"

# Модель заявки. Позже это будет таблица в БД.
class Order:
    def __init__(self, user_id, category, description, address, phone):
        self.user_id = user_id
        self.category = category
        self.description = description
        self.address = address
        self.phone = phone
        self.state = OrderState.PENDING
        self.master_id = None