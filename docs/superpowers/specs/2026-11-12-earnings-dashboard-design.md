# Earnings Dashboard — Diseño (inspirado en Airbnb)

**Fecha:** 2026-11-12  
**Work Item:** #0  
**Branch:** feature/WI-0-earnings-dashboard  

---

## Resumen

Dashboard de ingresos para administradores de la tienda, inspirado visualmente en el panel de ganancias de Airbnb. Muestra ingresos de órdenes de compra agrupados por mes, con comparación año vs año, desglose por producto y vistas de cobros pendientes/recibidos.

---

## Alcance

### Incluido
- Vista **Rendimiento**: gráfica de barras mensual + card de resumen del mes + gráfica de líneas YoY + lista de ingresos por producto
- Vista **Cobros pendientes**: tabla de órdenes en estados no pagados
- Vista **Cobros recibidos**: tabla de órdenes confirmadas/pagadas
- 4 endpoints de agregación en Django (`enid-store`)
- Nuevos componentes Vue en `service-store`

### Excluido
- Vista "Informes" (exportación CSV) — fuera del MVP
- Vista "Configuración y documentos" — fuera del MVP
- Notificaciones push o email
- Filtros por categoría o sucursal

---

## Arquitectura

### Backend — `enid-store`

Nueva Django app `revenue` con 4 endpoints bajo el prefijo `/enid/revenue/`.

#### Mapping de estados

| Grupo | Statuses de Order |
|-------|-------------------|
| Cobros recibidos | `payment_confirmed`, `delivered`, `cash_on_delivery` |
| Cobros pendientes | `pending`, `preparing`, `ready_for_shipping`, `in_transit`, `ready_for_pickup` |
| Excluidos (no cuentan) | `returned`, `refund_processed`, `canceled` |

#### Fórmula de monto

```
monto_orden = SUM(ItemOrder.price × ItemOrder.quantity)
```

Agrupado por `Order.created_at` (mes/año).

#### Endpoints

**1. `GET /enid/revenue/monthly/?year=YYYY`**

Devuelve ingresos mensuales del año para la gráfica de barras.

```json
[
  {"month": 3, "recibidos": 24000.00, "pendientes": 5000.00},
  {"month": 4, "recibidos": 12000.00, "pendientes": 3200.00},
  ...
]
```
- Incluye todos los meses del año (1–12); meses sin órdenes devuelven 0.
- `year` default: año actual.

**2. `GET /enid/revenue/summary/?year=YYYY&month=MM`**

Resumen del mes seleccionado para la card de desglose.

```json
{
  "recibidos": 0.00,
  "pendientes": 16011.46,
  "total": 16011.46
}
```
- `year` y `month` default: mes y año actuales.

**3. `GET /enid/revenue/comparison/?year=YYYY`**

Comparación año actual vs año anterior para la gráfica de líneas.

```json
[
  {"month": 1, "current": 0.00, "previous": 0.00},
  {"month": 3, "current": 24000.00, "previous": 18000.00},
  ...
]
```
- Siempre devuelve los 12 meses; meses futuros del año actual devuelven `null` (para trazar línea discontinua).

**4. `GET /enid/revenue/by-product/?year=YYYY&month=MM`**

Ingresos por producto para el mes seleccionado.

```json
[
  {
    "id": 1,
    "name": "Kit Pesas 20kg",
    "image": "/media/images/kit-pesas.jpg",
    "amount": 8000.00,
    "pct": 50.0
  },
  ...
]
```
- Ordenado de mayor a menor por `amount`.
- `pct` = (amount_producto / total_mes) × 100, redondeado a 1 decimal.
- Si `month` es el mes actual, incluye todos los estados (recibidos + pendientes).

#### Estructura de archivos — backend

```
enid-store/enid/revenue/
  __init__.py
  apps.py
  urls.py
  views.py          ← 4 vistas (APIView)
  serializers.py    ← serializers de respuesta
  tests/
    __init__.py
    test_monthly.py
    test_summary.py
    test_comparison.py
    test_by_product.py
```

Registrar en `enid/enid/urls.py`:
```python
path('revenue/', include('revenue.urls')),
```

#### Autenticación
Los 4 endpoints requieren `IsAdminUser` (Django REST Framework). Solo accesibles para staff.

---

### Frontend — `service-store`

#### Ruta nueva
```
/ingresos  →  EarningsDashboard.vue  (protegida con guard de auth existente)
```

#### Estructura de archivos — frontend

```
service-store/src/
  views/Earnings/
    EarningsDashboard.vue      ← layout: sidebar + router-view interno
    Rendimiento.vue            ← gráfica barras + card + YoY + by-product
    CobrosPendientes.vue       ← tabla órdenes pendientes
    CobrosRecibidos.vue        ← tabla órdenes pagadas
  components/Earnings/
    BarChart.vue               ← wrapper vue-chartjs (bar)
    LineChart.vue              ← wrapper vue-chartjs (line)
    MonthSummaryCard.vue       ← card: recibidos / pendientes / total
    ProductIncomeList.vue      ← lista: foto + nombre + barra % + monto
```

#### Librería de gráficas
`chart.js` + `vue-chartjs` — instaladas como dependencia nueva.

#### Layout del dashboard

```
┌─────────────────────────────────────────────────────┐
│  Ingresos                                           │
│  ─────────────────                                  │
│  [▦] Rendimiento       │  <contenido activo>        │
│  [▤] Cobros pendientes │                            │
│  [▤] Cobros recibidos  │                            │
│                        │                            │
└─────────────────────────────────────────────────────┘
```

#### Vista Rendimiento — secciones en orden

1. **Gráfica de barras** (BarChart.vue)
   - Llama `monthly/?year=YYYY`
   - Barras dobles: recibidos (magenta sólido) + pendientes (magenta claro)
   - Selector de año en el header
   - Al click en una barra → actualiza el mes seleccionado globalmente

2. **Card de resumen del mes** (MonthSummaryCard.vue)
   - Llama `summary/?year=YYYY&month=MM`
   - Muestra: Cobros recibidos · Cobros pendientes · Total MXN
   - Acordeón "Desglose de los pagos" — lista de órdenes del mes con link a detalle

3. **Gráfica de líneas YoY** (LineChart.vue)
   - Llama `comparison/?year=YYYY`
   - Dos líneas: año actual (magenta) + año anterior (morado)
   - Toggle "Mostrar ingresos futuros" — oculta/muestra meses futuros con línea discontinua

4. **Lista por producto** (ProductIncomeList.vue)
   - Llama `by-product/?year=YYYY&month=MM`
   - Fila: miniatura imagen + nombre + barra de progreso % + monto MXN

#### Vista Cobros pendientes

Tabla de órdenes con status en `{pending, preparing, ready_for_shipping, in_transit, ready_for_pickup}`.
Columnas: ID orden · Fecha · Cliente · Total · Status · Acciones (link a detalle).
Reutiliza `OrderSearchSerializer` del endpoint existente `/enid/order-search/`.

#### Vista Cobros recibidos

Igual que Cobros pendientes pero filtrando `{payment_confirmed, delivered, cash_on_delivery}`.
Reutiliza el mismo serializer y componentes de tabla.

---

## Flujo de datos

```
Vue view
  │── axios GET /enid/revenue/monthly/   → BarChart.vue
  │── axios GET /enid/revenue/summary/   → MonthSummaryCard.vue
  │── axios GET /enid/revenue/comparison/→ LineChart.vue
  └── axios GET /enid/revenue/by-product/→ ProductIncomeList.vue
```

Cada llamada es independiente. No hay store Pinia para este dashboard — estado local en `Rendimiento.vue` (año y mes seleccionados), props hacia los hijos.

---

## Testing

### Backend (TDD estricto, sin mocks)

Cada test usa Testcontainers con PostgreSQL real.

| Archivo | Qué verifica |
|---------|-------------|
| `test_monthly.py` | Suma correcta por mes, meses vacíos = 0, exclusión de canceladas |
| `test_summary.py` | Totales correctos para mes específico, default = mes actual |
| `test_comparison.py` | YoY correcto, meses futuros = null |
| `test_by_product.py` | Orden desc por monto, cálculo de pct, imagen incluida |

### Frontend

Tests de integración con Cypress o Vitest + Vue Test Utils para:
- Renderizado correcto de cada sección con datos mockeados del endpoint
- Click en barra actualiza el mes seleccionado
- Toggle YoY muestra/oculta meses futuros

---

## Consideraciones

- **Moneda:** todos los montos en MXN, formato `$#,###.## MXN`.
- **Zona horaria:** `Order.created_at` está en UTC; agrupar en UTC (consistente con el resto de la app).
- **Acceso:** solo admin (IsAdminUser). Sin SSO adicional, usa la sesión Django existente.
- **Performance:** los 4 endpoints son queries de agregación en SQL — O(n) sobre órdenes. Sin caché en MVP; si el volumen crece, se agrega caché en siguiente iteración.
- **Imagen de producto:** si el producto no tiene imagen, mostrar placeholder genérico.
