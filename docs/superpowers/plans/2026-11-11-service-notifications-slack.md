# service-notifications Slack MVP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear `service-notifications` (FastAPI) que recibe eventos de órdenes desde `enid-store` y los notifica a un canal de Slack vía Incoming Webhook.

**Architecture:** `enid-store` llama HTTP POST sync (timeout 3s, try/except) a `service-notifications:8090/notify/order` tras crear una orden o cambiar su status. `service-notifications` formatea el mensaje y hace POST al Slack Incoming Webhook. Si el servicio de notificaciones falla, el checkout de `enid-store` continúa sin interrupción.

**Tech Stack:** FastAPI + uvicorn, python-decouple, requests, pytest, pytest-httpserver (servidor HTTP real para capturar webhook en tests — no mocks).

**Spec:** `docs/superpowers/specs/2026-11-11-service-notifications-slack-design.md`

## Global Constraints

- Python 3.11-slim (imagen Docker base)
- `docker compose` v2 — NUNCA `docker-compose` v1
- Todo comando corre dentro del contenedor: `docker exec <container> pytest`
- NUNCA mocks/stubs/monkeypatch — usar infraestructura real (pytest-httpserver es un servidor HTTP real)
- TDD estricto: test falla → implementación mínima → test pasa → commit
- Commits con Work Item: `#[ID]: descripción`
- NUNCA push a master — siempre feature branch + PR
- Rutas de imports: siempre absolutas desde raíz del paquete (`from app.services.slack import SlackNotifier`)
- Variables de entorno: NUNCA hardcodeadas — siempre via `python-decouple`

---

## Mapa de archivos

### Nuevos (service-notifications)
| Archivo | Responsabilidad |
|---|---|
| `service-notifications/Dockerfile` | Build prod |
| `service-notifications/docker-compose.yml` | Dev local con hot-reload |
| `service-notifications/docker-compose.test.yml` | Contenedor para tests |
| `service-notifications/requirements.txt` | Deps prod |
| `service-notifications/requirements-dev.txt` | watchdog + pytest + pytest-httpserver |
| `service-notifications/env.example` | Plantilla de env vars |
| `service-notifications/app/__init__.py` | Paquete |
| `service-notifications/app/main.py` | FastAPI app, registra router |
| `service-notifications/app/config.py` | Lee `SLACK_WEBHOOK_URL` |
| `service-notifications/app/schemas/order_event.py` | Pydantic schema del payload |
| `service-notifications/app/services/slack.py` | `SlackNotifier` — formatea y POSTea al webhook |
| `service-notifications/app/dependencies.py` | FastAPI DI: `get_notifier()` |
| `service-notifications/app/routers/notify.py` | `POST /notify/order` |
| `service-notifications/tests/__init__.py` | Paquete |
| `service-notifications/tests/test_notify_order.py` | Tests de integración |

### Nuevos (enid-store)
| Archivo | Responsabilidad |
|---|---|
| `enid-store/enid/notifications/__init__.py` | Paquete (vacío) |
| `enid-store/enid/notifications/client.py` | `notify_order(event, order)` — HTTP helper |

### Modificados (enid-store)
| Archivo | Qué cambia |
|---|---|
| `enid-store/enid/enid/settings.py` | Agrega `NOTIFICATIONS_SERVICE_URL` |
| `enid-store/enid/env.example` | Agrega `NOTIFICATIONS_SERVICE_URL` |
| `enid-store/enid/order/views.py` | Llama `notify_order('new_order', order)` tras Stripe exitoso |
| `enid-store/enid/order_payment_on_delivery/views.py` | Llama `notify_order('new_order', order)` tras crear orden POD |
| `enid-store/enid/order_management/views.py` | Sobreescribe `perform_update()` para notificar cambios de status |

---

## Task 1: Scaffold de service-notifications

**Files:**
- Create: `service-notifications/Dockerfile`
- Create: `service-notifications/docker-compose.yml`
- Create: `service-notifications/docker-compose.test.yml`
- Create: `service-notifications/requirements.txt`
- Create: `service-notifications/requirements-dev.txt`
- Create: `service-notifications/env.example`
- Create: `service-notifications/app/__init__.py`
- Create: `service-notifications/tests/__init__.py`

**Interfaces:**
- Produce: directorio `service-notifications/` listo para `docker compose up --build`

- [x] **Step 1: Crear directorio raíz**

```bash
mkdir -p service-notifications/app/schemas service-notifications/app/services service-notifications/app/routers service-notifications/tests
```

- [x] **Step 2: Crear Dockerfile**

```dockerfile
# service-notifications/Dockerfile
ARG PYTHON_VERSION=python:3.11-slim
FROM ${PYTHON_VERSION}

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY requirements-dev.txt /app/
RUN pip install -r requirements-dev.txt

COPY . .

EXPOSE 8080

CMD ["watchmedo", "auto-restart", \
     "--directory=./", \
     "--pattern=*.py", \
     "--recursive", \
     "--", \
     "uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8080"]
```

- [x] **Step 3: Crear docker-compose.yml (dev con hot-reload)**

```yaml
# service-notifications/docker-compose.yml
version: '3'

services:
  service-notifications:
    build: .
    image: ${SERVICENAME:-service-notifications}_service
    container_name: ${SERVICENAME:-service-notifications}_service
    ports:
      - "8090:8080"
    env_file:
      - .env
    volumes:
      - .:/app
    networks:
      - backend
      - enid_service_network

networks:
  backend:
    driver: bridge
  enid_service_network:
    external: true
```

- [x] **Step 4: Crear docker-compose.test.yml**

```yaml
# service-notifications/docker-compose.test.yml
version: '3'

services:
  notifications-test:
    build: .
    container_name: service-notifications-test
    volumes:
      - .:/app
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - APP_ENV=test
      - SLACK_WEBHOOK_URL=http://placeholder-replaced-in-test:9999/webhook
    command: tail -f /dev/null
```

- [x] **Step 5: Crear requirements.txt**

```
fastapi==0.111.0
uvicorn==0.29.0
python-decouple==3.8
requests==2.31.0
```

- [x] **Step 6: Crear requirements-dev.txt**

```
watchdog[watchmedo]==4.0.0
pytest==7.4.4
pytest-httpserver==1.0.10
httpx==0.26.0
```

- [x] **Step 7: Crear env.example**

```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXXX/YYYY/ZZZZ
APP_ENV=development
```

- [x] **Step 8: Crear archivos __init__.py vacíos**

```bash
touch service-notifications/app/__init__.py
touch service-notifications/app/schemas/__init__.py
touch service-notifications/app/services/__init__.py
touch service-notifications/app/routers/__init__.py
touch service-notifications/tests/__init__.py
```

- [x] **Step 9: Build para verificar que el scaffold es válido**

```bash
cd service-notifications
docker compose build
```

Esperado: build exitoso sin errores.

- [x] **Step 10: Commit**

```bash
git add service-notifications/
git commit -m "#[WI]: Step 1 - scaffold service-notifications"
```

---

## Task 2: Config, schema y app skeleton

**Files:**
- Create: `service-notifications/app/config.py`
- Create: `service-notifications/app/schemas/order_event.py`
- Create: `service-notifications/app/main.py`

**Interfaces:**
- Produce: `SLACK_WEBHOOK_URL: str` desde `app.config`
- Produce: `OrderEvent` (Enum), `OrderEventPayload` (Pydantic) desde `app.schemas.order_event`
- Produce: `app` (FastAPI instance) desde `app.main`

- [x] **Step 1: Crear app/config.py**

```python
# service-notifications/app/config.py
from decouple import config

SLACK_WEBHOOK_URL: str = config("SLACK_WEBHOOK_URL")
```

- [x] **Step 2: Crear app/schemas/order_event.py**

```python
# service-notifications/app/schemas/order_event.py
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
```

- [x] **Step 3: Crear app/main.py (skeleton sin router aún)**

```python
# service-notifications/app/main.py
from fastapi import FastAPI

app = FastAPI(title="service-notifications")
```

- [x] **Step 4: Levantar servicio para verificar que arranca**

```bash
docker compose up --build
# En otro terminal:
curl http://localhost:8090/docs
```

Esperado: responde con HTML de Swagger UI (FastAPI activo).

- [x] **Step 5: Commit**

```bash
git add service-notifications/app/config.py \
        service-notifications/app/schemas/ \
        service-notifications/app/main.py
git commit -m "#[WI]: Step 2 - config, schema y app skeleton"
```

---

## Task 3: SlackNotifier + endpoint /notify/order (TDD)

**Files:**
- Create: `service-notifications/app/services/slack.py`
- Create: `service-notifications/app/dependencies.py`
- Create: `service-notifications/app/routers/notify.py`
- Create: `service-notifications/tests/test_notify_order.py`
- Modify: `service-notifications/app/main.py`

**Interfaces:**
- Consume: `OrderEvent`, `OrderEventPayload` desde `app.schemas.order_event`
- Consume: `SLACK_WEBHOOK_URL` desde `app.config`
- Produce: `SlackNotifier(webhook_url=None)` con método `send(payload: OrderEventPayload) -> bool`
- Produce: `get_notifier() -> SlackNotifier` (FastAPI dependency)
- Produce: `POST /notify/order` → `{"ok": True}` (200) o HTTP 502

**Nota sobre tests:** `pytest-httpserver` inicia un servidor HTTP real en un puerto aleatorio durante el test. `SlackNotifier` recibe el `webhook_url` como argumento de constructor, lo que permite apuntarlo al servidor real de test sin usar mocks ni monkeypatch. `app.dependency_overrides` es el mecanismo oficial de FastAPI para inyectar dependencias en tests — no es mocking.

- [x] **Step 1: Levantar contenedor de test**

```bash
cd service-notifications
docker compose -f docker-compose.test.yml up -d
```

- [x] **Step 2: Escribir tests (deben fallar — RED)**

Crear `service-notifications/tests/test_notify_order.py`:

```python
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
```

- [x] **Step 3: Correr tests para confirmar que fallan (RED)**

```bash
docker exec service-notifications-test pytest tests/test_notify_order.py -v
```

Esperado: `ModuleNotFoundError: No module named 'app.services.slack'`

- [x] **Step 4: Crear app/services/slack.py**

```python
# service-notifications/app/services/slack.py
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
```

- [x] **Step 5: Crear app/dependencies.py**

```python
# service-notifications/app/dependencies.py
from app.services.slack import SlackNotifier


def get_notifier() -> SlackNotifier:
    return SlackNotifier()
```

- [x] **Step 6: Crear app/routers/notify.py**

```python
# service-notifications/app/routers/notify.py
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.order_event import OrderEventPayload
from app.services.slack import SlackNotifier
from app.dependencies import get_notifier

router = APIRouter()


@router.post("/notify/order", status_code=200)
def notify_order(
    payload: OrderEventPayload,
    notifier: SlackNotifier = Depends(get_notifier),
):
    success = notifier.send(payload)
    if not success:
        raise HTTPException(status_code=502, detail="Slack webhook failed")
    return {"ok": True}
```

- [x] **Step 7: Registrar router en app/main.py**

Reemplazar el contenido de `app/main.py`:

```python
# service-notifications/app/main.py
from fastapi import FastAPI
from app.routers.notify import router

app = FastAPI(title="service-notifications")
app.include_router(router)
```

- [x] **Step 8: Correr tests (GREEN)**

```bash
docker exec service-notifications-test pytest tests/test_notify_order.py -v
```

Esperado: todos los tests en PASS.

- [x] **Step 9: Commit**

```bash
git add service-notifications/app/services/slack.py \
        service-notifications/app/dependencies.py \
        service-notifications/app/routers/notify.py \
        service-notifications/app/main.py \
        service-notifications/tests/test_notify_order.py
git commit -m "#[WI]: Step 3 - SlackNotifier + endpoint /notify/order (TDD)"
```

- [x] **Step 10: Bajar contenedor de test**

```bash
docker compose -f docker-compose.test.yml down
```

---

## Task 4: enid-store notifications client

**Files:**
- Create: `enid-store/enid/notifications/__init__.py`
- Create: `enid-store/enid/notifications/client.py`
- Modify: `enid-store/enid/enid/settings.py`
- Modify: `enid-store/enid/env.example`

**Interfaces:**
- Consume: `order.id`, `order.items` (related_name='items'), `order.user`, `order.source` del modelo `Order`
- Consume: `item.product.name`, `item.quantity`, `item.price` del modelo `ItemOrder`
- Consume: `settings.NOTIFICATIONS_SERVICE_URL`
- Produce: `notify_order(event: str, order: Order) -> None` — no lanza excepciones, loguea fallos

**Nota:** `notifications/` no es una Django app (sin modelos ni migrations). Es un módulo Python simple. No agregar a `INSTALLED_APPS`.

- [x] **Step 1: Crear archivos del módulo notifications**

```bash
touch enid-store/enid/notifications/__init__.py
```

- [x] **Step 2: Crear enid-store/enid/notifications/client.py**

```python
# enid-store/enid/notifications/client.py
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def notify_order(event: str, order) -> None:
    url = getattr(settings, "NOTIFICATIONS_SERVICE_URL", "")
    if not url:
        return

    items = order.items.select_related("product").all()
    products = [f"{item.product.name} x{item.quantity}" for item in items]
    total = float(sum(item.price * item.quantity for item in items))

    user = order.user
    if user and (user.first_name or user.last_name):
        client_name = f"{user.first_name} {user.last_name}".strip()
    else:
        client_name = "Cliente"

    payload = {
        "event": event,
        "order_id": order.id,
        "client_name": client_name,
        "total": total,
        "products": products,
        "source": order.source or "",
    }

    try:
        requests.post(
            f"{url}/notify/order",
            json=payload,
            timeout=3,
        )
    except Exception as e:
        logger.error("notify_order failed for order %s: %s", order.id, e)
```

- [x] **Step 3: Agregar NOTIFICATIONS_SERVICE_URL a settings.py**

En `enid-store/enid/enid/settings.py`, agregar junto a las otras vars de config (cerca de `STRIPE_SECRET_KEY`):

```python
NOTIFICATIONS_SERVICE_URL = config("NOTIFICATIONS_SERVICE_URL", default="")
```

- [x] **Step 4: Agregar var a env.example**

En `enid-store/enid/env.example`, agregar:

```
NOTIFICATIONS_SERVICE_URL=http://localhost:8090
```

- [x] **Step 5: Verificar que el módulo importa correctamente**

```bash
docker exec ${SERVICENAME}_service python -c "from notifications.client import notify_order; print('OK')"
```

Esperado: imprime `OK` sin errores.

- [x] **Step 6: Commit**

---

## Task 5: Wire up — integración en los 3 puntos de enid-store

**Files:**
- Modify: `enid-store/enid/order/views.py`
- Modify: `enid-store/enid/order_payment_on_delivery/views.py`
- Modify: `enid-store/enid/order_management/views.py`

**Interfaces:**
- Consume: `notify_order(event: str, order: Order)` desde `notifications.client`

**Nota sobre order/views.py:** la llamada a `notify_order` ocurre dentro del bloque `transaction.atomic()`, después de que `register_items_order` ya guardó los items. `order.items.all()` los verá correctamente. Si `notify_order` lanza (aunque no debería), el `try/except` interior lo absorbe sin afectar la transacción.

- [ ] **Step 1: Modificar order/views.py — agregar import**

Agregar al bloque de imports en `enid-store/enid/order/views.py`:

```python
from notifications.client import notify_order
```

- [ ] **Step 2: Modificar order/views.py — llamar notify_order tras Stripe exitoso**

Ubicar el bloque `if charge_result['status'] == 'success':` (aprox línea 53) y agregar la llamada antes del `return`:

```python
if charge_result['status'] == 'success':
    order_data = serializer.data
    notify_order('new_order', order)
    return Response(order_data, status=status.HTTP_201_CREATED)
```

- [ ] **Step 3: Modificar order_payment_on_delivery/views.py — agregar import**

Agregar al bloque de imports en `enid-store/enid/order_payment_on_delivery/views.py`:

```python
from notifications.client import notify_order
```

- [ ] **Step 4: Modificar order_payment_on_delivery/views.py — llamar notify_order tras crear orden POD**

Ubicar el bloque `if isinstance(order, Order):` dentro del `transaction.atomic()` y agregar la llamada después de `register_items_order`:

```python
if isinstance(order, Order):
    self.register_items_order(order, products)
    notify_order('new_order', order)
    serializer = OrderSerializer(order, context={'request': request})
    return Response(serializer.data, status=status.HTTP_201_CREATED)
```

- [ ] **Step 5: Modificar order_management/views.py — agregar import y perform_update**

Reemplazar el contenido completo de `enid-store/enid/order_management/views.py`:

```python
from rest_framework import viewsets
from order_management.serializers import OrderSerializer
from order.models import Order
from notifications.client import notify_order

_NOTIFY_STATUSES = {'payment_confirmed', 'delivered'}


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def perform_update(self, serializer):
        old_status = self.get_object().status
        instance = serializer.save()
        if instance.status != old_status and instance.status in _NOTIFY_STATUSES:
            notify_order(instance.status, instance)
```

- [ ] **Step 6: Verificar que enid-store arranca sin errores**

```bash
docker compose up --build
```

Esperado: servicio levanta, no hay ImportError ni SyntaxError en los logs.

- [ ] **Step 7: Smoke test manual — crear orden de prueba**

Con enid-store y service-notifications corriendo, hacer login en `http://localhost/login` con `enidservice@gmail.com` / `enidservice@gmail.com` y crear una orden de prueba desde la tienda. Verificar que llega notificación en Slack.

- [ ] **Step 8: Commit**

```bash
git add enid-store/enid/order/views.py \
        enid-store/enid/order_payment_on_delivery/views.py \
        enid-store/enid/order_management/views.py
git commit -m "#[WI]: Step 5 - wire up notify_order en los 3 puntos de enid-store"
```

---

## Checklist final antes de PR

- [ ] `docker exec service-notifications-test pytest tests/ -v` → todos PASS
- [ ] `service-notifications` arranca con `docker compose up` sin errores
- [ ] `enid-store` arranca con `docker compose up` sin errores
- [ ] Smoke test manual: orden creada → notificación llega a Slack
- [ ] `SLACK_WEBHOOK_URL` y `NOTIFICATIONS_SERVICE_URL` **nunca** hardcodeadas en el código
- [ ] Branch: `feature/WI-[ID]-service-notifications-slack`
- [ ] PR creado en Azure DevOps

---

**Progreso:** 4/5 Tasks (80%) — ⏸️ SIGUIENTE: Task 5 - Wire up notify_order en los 3 puntos de enid-store
