from pydantic import BaseModel
from enum import Enum
from typing import List


class OrderEvent(str, Enum):
    new_order = "new_order"
    payment_confirmed = "payment_confirmed"
    delivered = "delivered"


class OrderEventPayload(BaseModel):
    event: OrderEvent
    order_id: int
    client_name: str
    total: float
    products: List[str]
    source: str = ""
