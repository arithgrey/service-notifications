# Venta Manual con Datos de Cliente — Design Spec

**Fecha:** 2026-11-17  
**Work Item:** #0  
**Branch:** develop (todos los repos)

---

## Contexto y Problema

El endpoint `POST /productos/manual-sale/` y el componente `ManualSaleForm.vue` permiten registrar ventas manuales/históricas, pero crean órdenes sin asociar cliente ni dirección. Esto impide identificar ventas recurrentes y deja `Order.user` y `Order.shipping_address` siempre nulos en ventas admin.

---

## Objetivo

Extender la venta manual para que el admin pueda:

1. Buscar un cliente existente (por email o nombre) y autocompletar sus datos.
2. Registrar un cliente nuevo (se crea via `get_or_create` por email).
3. Asociar opcionalmente una dirección de envío a la orden.

Todo ello reutilizando modelos existentes: `auth.User`, `Address`, `Order.user`, `Order.shipping_address`.

---

## Arquitectura

### Sin modelos nuevos

| Campo reutilizado | Modelo | Ya nullable |
|---|---|---|
| `Order.user` | `auth.User` FK | sí |
| `Order.shipping_address` | `Address` FK | sí |

No se crean tablas ni migraciones nuevas.

---

## Backend

### Nuevo endpoint: `GET /productos/clientes/`

**Clase:** `ProductVuewSet` (nuevo `@action`)  
**Ruta:** `GET /productos/clientes/?q=<query>`  
**Permiso:** `IsAdminUser`

**Lógica:**
- `q` vacío o ausente → `400 Bad Request`.
- Busca en `auth.User` filtrando por `email__icontains=q` OR `first_name__icontains=q` OR `last_name__icontains=q`.
- Para cada usuario encontrado, busca su orden más reciente (`Order.objects.filter(user=u).order_by('-created_at').first()`) y extrae `shipping_address`.

**Response (200):**
```json
[
  {
    "id": 42,
    "email": "ana@ejemplo.com",
    "name": "Ana García",
    "last_address": {
      "street": "Av. Hidalgo",
      "number": 10,
      "interior_number": 1,
      "colony": "Centro",
      "delegation_or_municipality": "Cuauhtémoc",
      "city": "CDMX",
      "state": 9,
      "postal_code": "06600",
      "phone_number": "5512345678",
      "additional_details": ""
    }
  }
]
```

`last_address` puede ser `null` si el usuario no tiene órdenes con dirección.

---

### Extender: `POST /productos/manual-sale/`

**Payload nuevo (todos los campos nuevos son opcionales):**

```json
{
  "items": [{"product": 1, "quantity": 2, "price": 250}],
  "status": "delivered",
  "sale_date": "2025-03-15T12:00:00Z",
  "customer_id": 42,
  "customer_email": "nuevo@ejemplo.com",
  "customer_name": "Luis Pérez",
  "address": {
    "street": "Calle Morelos",
    "number": 5,
    "interior_number": 1,
    "colony": "Juárez",
    "delegation_or_municipality": "Cuauhtémoc",
    "city": "CDMX",
    "state": 9,
    "postal_code": "06600",
    "phone_number": "5598765432",
    "additional_details": ""
  }
}
```

**Reglas de resolución del cliente:**

| Escenario | Comportamiento |
|---|---|
| `customer_id` presente | `User.objects.filter(pk=customer_id).first()` → 400 si no existe |
| `customer_email` presente (sin `customer_id`) | `get_or_create(email=customer_email)`, usa `customer_name` para `first_name`/`last_name` si es nuevo |
| Ninguno presente | `Order.user = None` (igual que hoy, retrocompatible) |

**Regla de dirección:**

| Escenario | Comportamiento |
|---|---|
| `address` presente | Crea `Address`, asigna a `Order.shipping_address` |
| `address` ausente | `Order.shipping_address = None` (retrocompatible) |

Todo dentro de `transaction.atomic()`.

**Validaciones adicionales (→ 400):**
- `customer_id` enviado pero usuario no existe.
- `customer_email` enviado pero es string vacío.
- `address` enviado pero falta algún campo requerido (`street`, `number`, `interior_number`, `colony`, `delegation_or_municipality`, `city`, `state`, `postal_code`, `phone_number`).

**Response (201) — igual que hoy + campos nuevos:**
```json
{
  "order_id": 38,
  "status": "delivered",
  "customer_id": 42,
  "customer_email": "ana@ejemplo.com"
}
```

---

## Frontend — `ManualSaleForm.vue`

### Estructura del form (de arriba a abajo)

```
┌─────────────────────────────────────────┐
│  🔍 Buscar cliente (email o nombre)     │  ← nuevo
│     [ dropdown con resultados ]         │
├─────────────────────────────────────────┤
│  Email del cliente      [____________]  │  ← nuevo
│  Nombre completo        [____________]  │  ← nuevo
├─────────────────────────────────────────┤
│  [ ] ¿Agregar dirección de envío?       │  ← toggle, oculto por defecto
│  (si activo → sub-form con 9 campos)   │
├─────────────────────────────────────────┤
│  Cantidad   [__]                        │  ← igual que hoy
│  Precio     [__]                        │
│  Estado     [select]                    │
│  Fecha      [datetime-local]            │
├─────────────────────────────────────────┤
│        [ Registrar venta ]              │
└─────────────────────────────────────────┘
```

### Comportamiento de búsqueda

- Input debounced **300 ms** → `GET enid/productos/clientes/?q=<query>` (mínimo 2 caracteres).
- Dropdown muestra hasta 8 resultados: `nombre — email`.
- Al hacer clic en un resultado:
  - Autofill de `email` y `nombre`.
  - Si tiene `last_address`: activa el toggle de dirección y pre-llena los campos.
  - Guarda internamente `customer_id` para enviarlo en el payload.
  - Cierra el dropdown.
- Si el query no retorna resultados: muestra "Cliente nuevo — se creará al registrar".
- El admin puede ignorar la búsqueda y llenar email/nombre manualmente.

### Sección de dirección (colapsable)

- Toggle checkbox "¿Agregar dirección de envío?" — oculto por defecto.
- Al activar: aparecen los campos (mismos que `AddressValidatorSerializer`):
  - Calle, Número, Número interior, Colonia, Municipio/Delegación, Ciudad, Estado (select con estados de MX), CP, Teléfono, Detalles adicionales (opcional).
- El estado es un `<select>` que carga los estados desde la DB (reutilizar el endpoint de estados que ya usa el checkout normal).

### Payload que envía al submit

```js
{
  items: [...],
  status: this.status,
  sale_date: ...,
  // cliente
  customer_id: this.selectedCustomer?.id || undefined,
  customer_email: this.email || undefined,
  customer_name: this.customerName || undefined,
  // dirección
  address: this.showAddress ? { ...this.addressForm } : undefined,
}
```

---

## Testing

### Backend (`django.test.TestCase` + Postgres real del contenedor)

**`products/tests/test_client_search.py`**
- Buscar por email exacto → retorna el cliente correcto con `last_address`.
- Buscar por nombre parcial → retorna coincidencias.
- Query vacío → 400.
- Sin resultados → lista vacía `[]`.
- No-admin → 403.

**`products/tests/test_manual_sale_customer.py`**
- Venta con `customer_id` existente → `Order.user` asignado.
- Venta con `customer_id` inexistente → 400.
- Venta con `customer_email` nuevo → `get_or_create` crea user, `Order.user` asignado.
- Venta con `customer_email` existente → reutiliza user existente.
- Venta con `address` → `Order.shipping_address` asignado con los datos correctos.
- Venta sin datos de cliente ni dirección → retrocompatible, `Order.user = None`, `Order.shipping_address = None`.

### Frontend (Jest, render puro sin red)

**`tests/unit/components/Products/ManualSaleForm.spec.js`** (extender el existente o nuevo archivo)
- El input de búsqueda renderiza.
- La sección de dirección está oculta por defecto.
- Al marcar el toggle de dirección, aparecen los campos de dirección.
- Con `selectedCustomer` seteado, los campos email y nombre muestran los valores del cliente.

---

## Constraints

- **Sin mocks** — tests de integración con Postgres real.
- **TDD estricto** — test falla primero.
- **Sin hardcode** — estados se cargan desde DB/API, no array estático.
- **Import absolutos** — `from products.services import ...`, `@/components/...`.
- **Rutas Django sin `/enid/`** — el prefijo lo agrega nginx.
- **Sin PII en logs** — solo ids/pks en `logger.error`.
- **Rama única `develop`** en ambos repos (`enid-store` y `service-store`).
