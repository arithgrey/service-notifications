import requests
from app.config import SLACK_WEBHOOK_URL
from app.schemas.order_event import OrderEventPayload, OrderEvent

_EMOJI = {
    OrderEvent.new_order: "🛒",
    OrderEvent.payment_confirmed: "✅",
    OrderEvent.delivered: "📦",
}

_TITLE = {
    OrderEvent.new_order: "Nueva orden",
    OrderEvent.payment_confirmed: "Pago confirmado",
    OrderEvent.delivered: "Entregada",
}


class SlackNotifier:
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or SLACK_WEBHOOK_URL

    def send(self, payload: OrderEventPayload) -> bool:
        message = self._format(payload)
        response = requests.post(
            self.webhook_url, json={"text": message}, timeout=5
        )
        return response.status_code == 200

    def _format(self, payload: OrderEventPayload) -> str:
        emoji = _EMOJI[payload.event]
        title = _TITLE[payload.event]
        lines = [
            f"{emoji} *{title} — Orden #{payload.order_id}* — ${payload.total:.2f}",
            f"👤 {payload.client_name}",
        ]
        if payload.event == OrderEvent.new_order and payload.products:
            lines.append(f"📦 {', '.join(payload.products)}")
        if payload.event == OrderEvent.new_order and payload.source:
            lines.append(f"🌐 Fuente: {payload.source}")
        return "\n".join(lines)
