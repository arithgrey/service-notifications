# Certificación de Productos — Documento de Diseño (Spec)

**Fecha:** 2026-11-13
**Servicio backend:** `enid-store` (Django, puerto 8085, ruteado `/enid/` en nginx)
**Servicio frontend:** `service-store` (Vue)
**Branch:** `develop`
**Work Item:** #0 (pendiente asignar)

---

## 1. Problema y objetivo

El holding publica muchos productos y necesita identificar **cuáles realmente valen la pena impulsar**. Un producto se considera "certificado" cuando **genera ingresos reales**.

Flujo conceptual del usuario:
- Al publicarse, un producto es efectivamente un **A/B test** (aún no probado).
- Cuando se registra una **venta/ingreso real**, se vuelve **candidato a certificado**.
- El **admin confirma** la certificación.
- Existen productos que ya venden **fuera de la página** (offline/histórico) y que también deben contabilizarse, aunque sus compras no provengan del sitio.

El objetivo es dar al admin la capacidad de: (a) ver/gestionar el estado de certificación, y (b) **registrar ventas manuales** para que productos privados/offline acumulen ingreso real igual que los públicos.

## 2. Alcance

**Incluye:**
- Máquina de estados de certificación sobre `Product` (3 estados).
- Transición automática `published → candidate` al detectar ingreso real.
- Transición manual `candidate → certified` (y override admin directo a `certified`).
- Registro de **venta manual** por el admin, reutilizando `Order` + `ItemOrder`.
- Soporte de **fecha histórica** de venta (`sale_date`).
- Endpoints admin y exposición del estado en serializers.
- UI admin en `service-store` (badge + botón certificar + formulario venta manual).

**No incluye (YAGNI):**
- Umbrales configurables de certificación (se usa "1 venta con ingreso").
- Estados adicionales (descartado, borrador).
- Modelo nuevo de "venta"; se reutiliza `Order`/`ItemOrder`.
- Reportería/analítica nueva; se aprovecha la app `revenue` existente.

## 3. Estado actual (contexto del repo)

- `Product` (`enid-store/enid/products/models.py`): catálogo con `price`, `cost`, `es_publico` (público/privado), etc.
- `Order` (`enid-store/enid/order/models.py`): tiene `status` (choices), `source` (default `main_landing`), `created_at = auto_now_add`.
- `ItemOrder` (`enid-store/enid/item_order/models.py`): `order`, `product`, `quantity`, `price`.
- `revenue` (`enid-store/enid/revenue/`): calcula ingreso sumando `ItemOrder.price * quantity` filtrando por `order.status`. Define:
  - `RECIBIDOS = ['payment_confirmed', 'delivered', 'cash_on_delivery']` (ingreso real)
  - `PENDIENTES = ['pending', 'preparing', 'ready_for_shipping', 'in_transit', 'ready_for_pickup']`

**Decisión DRY:** la regla "genera ingresos" = orden con `status in RECIBIDOS`, reutilizando la constante existente de `revenue` como única fuente de verdad (se extrae a un lugar compartido para evitar duplicación).

## 4. Diseño

### 4.1 Máquina de estados (persistida en `Product`)

Nuevos campos en `Product`:

```python
CERTIFICATION_CHOICES = (
    ('published', 'Publicado (A/B test)'),
    ('candidate', 'Candidato a certificado'),
    ('certified', 'Certificado'),
)
certification = models.CharField(
    max_length=20, choices=CERTIFICATION_CHOICES, default='published'
)
certified_at = models.DateTimeField(null=True, blank=True)
```

Transiciones válidas:

| Desde | Hacia | Disparador |
|-------|-------|-----------|
| `published` | `candidate` | **Automático**: 1ª `ItemOrder` del producto en orden con `status in RECIBIDOS`. |
| `candidate` | `certified` | **Manual**: admin confirma (set `certified_at`). |
| `published` / `candidate` | `certified` | **Override admin** al publicar/editar (sembrar ganador histórico). |
| `certified` | `candidate` / `published` | **Manual** (revertir), opcional. |

Reglas:
- `certified_at` se setea al entrar a `certified` y se limpia al revertir.
- El estado es **persistido** (no derivado) para que la confirmación del admin sea explícita y auditable, y para evitar N+1 al listar.
- La transición automática **nunca** degrada un `certified` (una venta posterior no revierte una certificación).

### 4.2 Transición automática (signal)

`post_save` en `Order` (y/o `ItemOrder`): cuando una orden pasa a `status in RECIBIDOS`, para cada producto de sus `items` cuyo `certification == 'published'`, cambiar a `candidate`.

- Idempotente: si ya es `candidate`/`certified`, no hace nada.
- Se dispara tanto para ventas de página como para ventas manuales (ambas son `Order`/`ItemOrder`).

### 4.3 Venta manual (reutiliza `Order` + `ItemOrder`)

El admin registra una venta con los mismos datos que una venta tradicional, pero creada por él. **No hay modelo nuevo.**

- Crea un `Order` con `source='admin_manual'` y `status` de ingreso real (default `delivered`, configurable entre `RECIBIDOS`).
- Crea sus `ItemOrder` (producto, cantidad, precio).
- Cuenta automáticamente en `revenue` y dispara el signal `published → candidate`.

**Fecha histórica** — nuevo campo en `Order`:

```python
sale_date = models.DateTimeField(null=True, blank=True,
    help_text="Fecha real de la venta (para ventas manuales/históricas). "
              "Si es nulo se usa created_at.")
```

- Ventas de página: `sale_date` nulo → se usa `created_at` (comportamiento actual intacto).
- `revenue` y la lógica de certificación usan la **fecha efectiva** = `sale_date or created_at` (coalesce). Se ajustan las queries de `revenue` para agrupar por la fecha efectiva.

### 4.4 API (backend `enid-store`, bajo `/enid/`, permiso `IsAdminUser`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/products/manual-sale/` | Crea venta manual: lista de items (producto, cantidad, precio), `status` (default `delivered`), `sale_date` opcional. Reutiliza serializers de order/item_order. |
| `PATCH` | `/products/{id}/certification/` | Transición de estado: confirmar (`candidate→certified`), override (`→certified`), revertir. Valida transiciones permitidas. |

- El serializer de `Product` expone `certification` y `certified_at` (visibles en listados admin para el ranking).
- Sin hardcode: puertos/URLs vía config existente; constante `RECIBIDOS` compartida.

### 4.5 Frontend admin (`service-store`, Vue)

En la vista/componente de producto del admin:
- **Badge** de estado: Publicado / Candidato / Certificado.
- **Botón "Certificar"** visible cuando el producto es `candidate`.
- **Formulario "Registrar venta manual"**: producto(s), cantidad, precio, status, fecha.
- Consumo de API sin URLs hardcodeadas (usa la config de rutas existente, prefijo `/enid/`).

## 5. Manejo de errores

- Transición inválida (`PATCH certification`) → `400` con mensaje claro (sin PII).
- Venta manual sin items o con producto inexistente → `400`.
- `status` fuera de los choices válidos → `400`.
- Permisos: no-admin → `403`.
- El signal es idempotente y no debe romper el guardado de la orden si falla (se registra error sin exponer PII).

## 6. Pruebas (TDD estricto, Testcontainers, sin mocks)

Infra real (Postgres vía Testcontainers / `docker-compose.test.yml`). **Cada test RED antes del código.** Mínimo las siguientes de integración:

1. Venta de página que entra a `status in RECIBIDOS` → producto `published → candidate`.
2. Venta en status NO-ingreso (`pending`, `canceled`) → producto permanece `published`.
3. Venta manual (`POST /products/manual-sale/`) con `sale_date` histórico → suma en `revenue` en el mes correcto y dispara `candidate`.
4. Admin confirma candidato (`PATCH`) → `certified` con `certified_at` seteado.
5. Override: publicar/editar con certificación directa → `certified`.
6. Una venta posterior NO degrada un producto `certified`.
7. Permisos: no-admin recibe `403` en ambos endpoints.
8. `revenue` sigue correcto para ventas de página sin `sale_date` (no-regresión de fecha efectiva).

Comando:
```bash
docker compose -f docker-compose.test.yml up -d
docker exec <servicio>-test pytest enid/products enid/order enid/revenue -v
docker compose -f docker-compose.test.yml down
```

## 7. Migraciones

- `Product`: agregar `certification`, `certified_at`.
- `Order`: agregar `sale_date`.
- Datos existentes: `certification` default `published`; opcional comando de management para sembrar `certified` en productos que ya tienen ingreso histórico (fuera del alcance inicial salvo que se pida).

## 8. Fuera de alcance / futuro

- Umbrales configurables de certificación.
- Estado "descartado" para limpiar ranking.
- Dashboard dedicado de certificación (hoy se ve vía listado admin + `revenue`).
