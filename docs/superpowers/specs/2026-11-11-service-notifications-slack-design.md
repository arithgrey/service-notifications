# service-notifications — Notificaciones Slack para Órdenes

**Fecha:** 2026-11-11
**Work Item:** pendiente de crear
**Branch:** feature/WI-[ID]-service-notifications-slack

---

## Contexto y objetivo

`enid-store` procesa órdenes de compra. Actualmente no existe mecanismo de alerta cuando llega una orden nueva o cambia de estado. El objetivo es notificar a un canal de Slack en 3 momentos clave, evitando construir un sistema de alertas propio.

Se crea un microservicio dedicado (`service-notifications`) para centralizar las notificaciones. Esto permite que en el futuro otros servicios (leads, stock) también notifiquen sin acoplar esa lógica a cada servicio.

---

## Arquitectura

```
enid-store (order creado / status actualizado)
    │
    └─ HTTP POST (sync, timeout 3s) → service-notifications:8090/notify/order
                                            │
                                            └─ HTTP POST → Slack Incoming Webhook
```

La llamada desde `enid-store` está envuelta en `try/except`. Si `service-notifications` está caído o tarda más de 3s, se loguea el error y el flujo de checkout continúa sin interrupción.

---

## Eventos notificados

| Evento | Disparador | Status de la orden |
|---|---|---|
| `new_order` | Orden creada exitosamente | `pending` |
| `payment_confirmed` | Status cambia a `payment_confirmed` | `payment_confirmed` |
| `delivered` | Status cambia a `delivered` | `delivered` |

---

## service-notifications

### Stack
- Python + FastAPI
- Puerto: `8090`
- Un único endpoint: `POST /notify/order`

### Payload recibido

```json
{
  "event": "new_order",
  "order_id": 42,
  "client_name": "Juan Pérez",
  "total": 850.00,
  "products": ["Carpa 3x3 x2", "Silla plegable x4"],
  "source": "main_landing"
}
```

### Comportamiento

1. Valida que el campo `event` sea uno de los 3 valores permitidos.
2. Formatea el mensaje Slack según el evento.
3. Hace `POST` al Incoming Webhook de Slack.
4. Retorna `200 OK` si el webhook responde `200`, o `502` si falla.

### Mensajes Slack por evento

**new_order:**
```
🛒 *Nueva orden #42* — $850.00
👤 Juan Pérez | 📦 Carpa 3x3 x2, Silla plegable x4
🌐 Fuente: main_landing
```

**payment_confirmed:**
```
✅ *Pago confirmado — Orden #42*
👤 Juan Pérez | $850.00
```

**delivered:**
```
📦 *Entregada — Orden #42*
👤 Juan Pérez
```

### Configuración

| Variable | Descripción |
|---|---|
| `SLACK_WEBHOOK_URL` | URL del Incoming Webhook de Slack |
| `APP_ENV` | `development` / `production` |

### Estructura de archivos

```
service-notifications/
├── app/
│   ├── main.py              # FastAPI app, registra router
│   ├── config.py            # Lee env vars con python-decouple
│   ├── routers/
│   │   └── notify.py        # POST /notify/order
│   ├── services/
│   │   └── slack.py         # SlackNotifier — formatea y envía a webhook
│   └── schemas/
│       └── order_event.py   # Pydantic schema del payload
├── tests/
│   └── test_notify_order.py # Integration test con Testcontainers (PostgreSQL)
├── Dockerfile
├── docker-compose.yml        # Solo desarrollo local
├── requirements.txt
├── requirements-dev.txt      # watchdog[watchmedo]
└── env.example
```

---

## Integración en enid-store

### Puntos de integración

| Archivo | Momento |
|---|---|
| `enid-store/enid/order/views.py` | Después de orden creada con Stripe exitosamente |
| `enid-store/enid/order_payment_on_delivery/views.py` | Después de orden contra entrega creada exitosamente |
| `enid-store/enid/order_management/views.py` | Después de PATCH/PUT que cambie status a `payment_confirmed` o `delivered` |

### Helper a crear

`enid-store/enid/notifications/client.py` — función `notify_order(event, order)` que:
1. Construye el payload a partir del objeto `Order`.
2. Llama `requests.post(NOTIFICATIONS_SERVICE_URL + "/notify/order", json=payload, timeout=3)`.
3. En cualquier excepción: loguea y retorna sin relanzar.

### Nueva variable de entorno en enid-store

| Variable | Descripción |
|---|---|
| `NOTIFICATIONS_SERVICE_URL` | URL base de service-notifications (ej. `http://service-notifications:8090`) |

---

## Tests

### service-notifications

**Test de integración** (`tests/test_notify_order.py`):
- Levanta PostgreSQL real vía Testcontainers.
- Llama `POST /notify/order` con cada uno de los 3 eventos.
- Verifica que el endpoint retorna `200` y que el payload enviado al webhook de Slack tiene el formato correcto.
- El webhook de Slack en test se apunta a un servidor HTTP local (Testcontainers o httpserver fixture).

### enid-store

No se agregan tests nuevos para el helper `notify_order` — es un wrapper de red. Los tests de integración existentes de órdenes cubren el flujo de creación; `notify_order` se llama dentro de un `try/except` que no altera el comportamiento observable.

---

## Desarrollo local

```bash
# Levantar service-notifications
cd service-notifications
docker compose up --build

# Correr tests
docker compose -f docker-compose.test.yml up -d
docker exec service-notifications-test pytest tests/ -v
docker compose -f docker-compose.test.yml down
```

---

## Fuera de alcance (MVP)

- Reintentos automáticos si Slack falla.
- Otros canales (WhatsApp, email).
- Notificaciones para otros servicios (leads, stock).
- Configuración dinámica de canales por tipo de evento.
