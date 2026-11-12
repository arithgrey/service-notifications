import pytest
from fastapi.testclient import TestClient
from pytest_httpserver import HTTPServer
from app.main import app
from app.services.slack import SlackNotifier
from app.schemas.order_event import OrderEventPayload, OrderEvent
from app.dependencies import get_notifier

SAMPLE_NEW_ORDER = {
    "event": "new_order",
    "order_id": 42,
    "client_name": "Juan Pérez",
    "total": 850.00,
    "products": ["Carpa 3x3 x2"],
    "source": "main_landing",
}

SAMPLE_PAYMENT_CONFIRMED = {
    "event": "payment_confirmed",
    "order_id": 42,
    "client_name": "Juan Pérez",
    "total": 850.00,
    "products": [],
    "source": "",
}

SAMPLE_DELIVERED = {
    "event": "delivered",
    "order_id": 42,
    "client_name": "Juan Pérez",
    "total": 850.00,
    "products": [],
    "source": "",
}


class TestSlackNotifier:
    def test_new_order_sends_correct_payload(self, httpserver: HTTPServer):
        httpserver.expect_request("/webhook").respond_with_data("ok")
        notifier = SlackNotifier(webhook_url=httpserver.url_for("/webhook"))

        result = notifier.send(OrderEventPayload(**SAMPLE_NEW_ORDER))

        assert result is True
        assert len(httpserver.log) == 1
        body = httpserver.log[0][0].json
        assert "🛒" in body["text"]
        assert "Nueva orden" in body["text"]
        assert "#42" in body["text"]
        assert "$850.00" in body["text"]
        assert "Juan Pérez" in body["text"]
        assert "Carpa 3x3 x2" in body["text"]
        assert "main_landing" in body["text"]

    def test_payment_confirmed_sends_correct_payload(self, httpserver: HTTPServer):
        httpserver.expect_request("/webhook").respond_with_data("ok")
        notifier = SlackNotifier(webhook_url=httpserver.url_for("/webhook"))

        result = notifier.send(OrderEventPayload(**SAMPLE_PAYMENT_CONFIRMED))

        assert result is True
        body = httpserver.log[0][0].json
        assert "✅" in body["text"]
        assert "Pago confirmado" in body["text"]
        assert "#42" in body["text"]

    def test_delivered_sends_correct_payload(self, httpserver: HTTPServer):
        httpserver.expect_request("/webhook").respond_with_data("ok")
        notifier = SlackNotifier(webhook_url=httpserver.url_for("/webhook"))

        result = notifier.send(OrderEventPayload(**SAMPLE_DELIVERED))

        assert result is True
        body = httpserver.log[0][0].json
        assert "📦" in body["text"]
        assert "Entregada" in body["text"]
        assert "#42" in body["text"]

    def test_send_returns_false_on_webhook_failure(self, httpserver: HTTPServer):
        httpserver.expect_request("/webhook").respond_with_data("", status=500)
        notifier = SlackNotifier(webhook_url=httpserver.url_for("/webhook"))

        result = notifier.send(OrderEventPayload(**SAMPLE_NEW_ORDER))

        assert result is False


class TestNotifyOrderEndpoint:
    def test_new_order_returns_200(self, httpserver: HTTPServer):
        httpserver.expect_request("/webhook").respond_with_data("ok")

        def get_test_notifier():
            return SlackNotifier(webhook_url=httpserver.url_for("/webhook"))

        app.dependency_overrides[get_notifier] = get_test_notifier
        client = TestClient(app)
        response = client.post("/notify/order", json=SAMPLE_NEW_ORDER)
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_invalid_event_returns_422(self):
        client = TestClient(app)
        response = client.post(
            "/notify/order", json={**SAMPLE_NEW_ORDER, "event": "invalid_event"}
        )
        assert response.status_code == 422

    def test_slack_failure_returns_502(self, httpserver: HTTPServer):
        httpserver.expect_request("/webhook").respond_with_data("", status=500)

        def get_test_notifier():
            return SlackNotifier(webhook_url=httpserver.url_for("/webhook"))

        app.dependency_overrides[get_notifier] = get_test_notifier
        client = TestClient(app)
        response = client.post("/notify/order", json=SAMPLE_NEW_ORDER)
        app.dependency_overrides.clear()

        assert response.status_code == 502
