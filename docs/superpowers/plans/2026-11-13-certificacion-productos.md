# Certificación de Productos — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar al admin una máquina de estados de certificación sobre `Product` (published → candidate → certified), con transición automática al detectar ingreso real y registro de ventas manuales/históricas reutilizando `Order`/`ItemOrder`.

**Architecture:** Dos campos nuevos en `Product` (`certification`, `certified_at`) + un campo en `Order` (`sale_date`). La promoción `published → candidate` se dispara vía signals `post_save` en `Order` e `ItemOrder` cuando el estado está en `RECIBIDOS`. Las transiciones manuales y la venta manual son `@action` admin en `ProductVuewSet`. `revenue` pasa a usar fecha efectiva `Coalesce(sale_date, created_at)`.

**Tech Stack:** Django 4.2.7, DRF, PostgreSQL, Vue 3 + Vite (frontend `service-store`). Tests: `django.test.TestCase` + `APIClient` (patrón existente del repo).

**Spec:** `docs/superpowers/specs/2026-11-13-certificacion-productos-design.md`

## Global Constraints

- **Rama única `develop`** en todos los repos anidados (HARD-GATE). NUNCA `git checkout -b`. Commitear cada Step en `develop`.
- **Work Item:** `#0`. Formato de commit: `#0: descripción`.
- **Solo Docker** — NUNCA correr comandos en el host. Backend tests: `docker exec enid_store_service python manage.py test ...`.
- **Sin mocks** (HARD-GATE): los tests corren contra el Postgres real del contenedor (`enid_store_postgres`), que es el patrón de integración existente. NO introducir `unittest.mock`, `pytest-mock`, `monkeypatch`.
- **TDD estricto:** cada test se escribe y DEBE fallar (RED) antes del código de producción.
- **Sin hardcode:** la constante `RECIBIDOS` es fuente única en `revenue/constants.py` tras Task 1; importar de ahí siempre.
- **Import absolutos** desde la raíz del paquete (`from products.models import Product`). Prohibido `../`.
- **Rutas internas Django sin `/enid/`** — el prefijo `/enid/` lo añade nginx. Endpoints reales: `/productos/manual-sale/`, `/productos/{id}/certification/`. El frontend sí llama con `enid/productos/...`.
- **No PII en logs** — los `logger.error` de los signals solo registran ids/pk, nunca datos de cliente.
- **Desviación del spec registrada:** el spec §6 menciona pytest/Testcontainers/`docker-compose.test.yml`; el repo no los tiene. Se sigue el patrón real (`TestCase` + Postgres real), que satisface integración real sin mocks. No se crea infra pytest.

---

## Task 1: Fuente única de constantes `RECIBIDOS`/`PENDIENTES` (DRY)

Hoy `RECIBIDOS`/`PENDIENTES` están triplicadas (`revenue/views.py:15-16`, `revenue/tests/test_monthly.py:16-17`, `revenue/management/commands/seed_revenue_demo.py:28-29`). Se extraen a un módulo único.

**Files:**
- Create: `enid/revenue/constants.py`
- Modify: `enid/revenue/views.py:15-16,81`
- Modify: `enid/revenue/management/commands/seed_revenue_demo.py:28-29`
- Modify: `enid/revenue/tests/test_monthly.py:16-17`
- Test: `enid/revenue/tests/test_constants.py` (nuevo)

**Interfaces:**
- Produces: `revenue.constants.RECIBIDOS: list[str]`, `revenue.constants.PENDIENTES: list[str]`, `revenue.constants.ALL_COUNTED: list[str]`.

- [x] **Step 1: Escribir el test que falla** ✅ (2026-11-13)

Create `enid/revenue/tests/test_constants.py`:

```python
from django.test import TestCase
from revenue.constants import RECIBIDOS, PENDIENTES, ALL_COUNTED


class RevenueConstantsTest(TestCase):
    def test_recibidos_values(self):
        self.assertEqual(
            RECIBIDOS, ['payment_confirmed', 'delivered', 'cash_on_delivery']
        )

    def test_pendientes_values(self):
        self.assertEqual(
            PENDIENTES,
            ['pending', 'preparing', 'ready_for_shipping', 'in_transit', 'ready_for_pickup'],
        )

    def test_all_counted_is_union(self):
        self.assertEqual(ALL_COUNTED, RECIBIDOS + PENDIENTES)
```

- [x] **Step 2: Correr el test y verificar que falla**

Run: `docker exec enid_store_service python manage.py test revenue.tests.test_constants -v 2`
Expected: FAIL — `ModuleNotFoundError: No module named 'revenue.constants'`.

- [x] **Step 3: Crear el módulo de constantes**

Create `enid/revenue/constants.py`:

```python
"""Fuente única de verdad de los estados de orden que cuentan como ingreso.

WHY: estas listas estaban duplicadas en views.py, seed_revenue_demo.py y los
tests. La regla "genera ingreso" (RECIBIDOS) la consume también la máquina de
certificación de productos, así que vive en un solo lugar.
"""

RECIBIDOS = ['payment_confirmed', 'delivered', 'cash_on_delivery']
PENDIENTES = ['pending', 'preparing', 'ready_for_shipping', 'in_transit', 'ready_for_pickup']
ALL_COUNTED = RECIBIDOS + PENDIENTES
```

- [x] **Step 4: Refactorizar `revenue/views.py` para importar de constants**

En `enid/revenue/views.py`, borrar las líneas 15-16 (`RECIBIDOS = ...`, `PENDIENTES = ...`) y la línea 81 (`ALL_COUNTED = RECIBIDOS + PENDIENTES`). Añadir al bloque de imports (después de la línea 13):

```python
from revenue.constants import RECIBIDOS, PENDIENTES, ALL_COUNTED
```

- [x] **Step 5: Refactorizar `seed_revenue_demo.py` y `test_monthly.py`**

En `enid/revenue/management/commands/seed_revenue_demo.py`, borrar las definiciones locales de `RECIBIDOS`/`PENDIENTES` (líneas ~28-29) y añadir en imports:

```python
from revenue.constants import RECIBIDOS, PENDIENTES
```

En `enid/revenue/tests/test_monthly.py`, borrar las definiciones locales (líneas ~16-17) y añadir en imports:

```python
from revenue.constants import RECIBIDOS, PENDIENTES
```

- [x] **Step 6: Correr tests (constants + toda la app revenue, regresión)**

Run: `docker exec enid_store_service python manage.py test revenue -v 2`
Expected: PASS (nuevos + todos los existentes de revenue).

- [x] **Step 7: Commit**

```bash
git add enid/revenue/constants.py enid/revenue/views.py \
        enid/revenue/management/commands/seed_revenue_demo.py \
        enid/revenue/tests/test_monthly.py enid/revenue/tests/test_constants.py
git commit -m "#0: extraer RECIBIDOS/PENDIENTES a revenue/constants.py (DRY)"
```

---

## Task 2: Campos de certificación en `Product` + migración

**Files:**
- Modify: `enid/products/models.py` (clase `Product`)
- Create: `enid/products/migrations/0005_product_certification.py`
- Test: `enid/products/tests/test_certification_model.py` (nuevo)

**Interfaces:**
- Produces: `Product.CERTIFICATION_CHOICES` (tuple), `Product.certification` (CharField, default `'published'`), `Product.certified_at` (DateTimeField, nullable).

- [x] **Step 1: Escribir el test que falla**

Create `enid/products/tests/test_certification_model.py`:

```python
from django.test import TestCase
from categories.models import Category
from products.models import Product


def _make_product():
    cat = Category.objects.create(name='Cat cert', slug='cat-cert')
    return Product.objects.create(
        category=cat, name='Prod cert', specific_name='Prod cert', price=100, cost=50
    )


class ProductCertificationModelTest(TestCase):
    def test_default_certification_is_published(self):
        product = _make_product()
        self.assertEqual(product.certification, 'published')
        self.assertIsNone(product.certified_at)

    def test_certification_choices_are_three(self):
        keys = [c[0] for c in Product.CERTIFICATION_CHOICES]
        self.assertEqual(keys, ['published', 'candidate', 'certified'])
```

- [x] **Step 2: Correr el test y verificar que falla**

Run: `docker exec enid_store_service python manage.py test products.tests.test_certification_model -v 2`
Expected: FAIL — `AttributeError`/`type object 'Product' has no attribute 'CERTIFICATION_CHOICES'`.

- [x] **Step 3: Añadir los campos al modelo `Product`**

En `enid/products/models.py`, dentro de la clase `Product` (junto a los demás campos, antes de los métodos `def __str__`):

```python
    CERTIFICATION_CHOICES = (
        ('published', 'Publicado (A/B test)'),
        ('candidate', 'Candidato a certificado'),
        ('certified', 'Certificado'),
    )
    certification = models.CharField(
        max_length=20, choices=CERTIFICATION_CHOICES, default='published',
        help_text='Estado de certificación: published→candidate→certified',
    )
    certified_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Fecha en que el producto fue certificado (se limpia al revertir)',
    )
```

- [x] **Step 4: Crear la migración**

Run: `docker exec enid_store_service python manage.py makemigrations products`
Expected: genera `products/migrations/0005_product_certification.py` con `AddField` de `certification` y `certified_at`, `dependencies = [('products', '0004_delivery_scheduling_fields')]`.

- [x] **Step 5: Correr tests (aplican migración sobre DB de test)**

Run: `docker exec enid_store_service python manage.py test products.tests.test_certification_model -v 2`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add enid/products/models.py enid/products/migrations/0005_product_certification.py \
        enid/products/tests/test_certification_model.py
git commit -m "#0: campos certification y certified_at en Product + migración"
```

---

## Task 3: Campo `sale_date` en `Order` + fecha efectiva en `revenue`

`revenue` filtra/agrupa por `order__created_at`. Con ventas históricas se necesita la fecha efectiva `Coalesce(sale_date, created_at)`. Ventas de página (sin `sale_date`) deben seguir igual.

**Files:**
- Modify: `enid/order/models.py` (clase `Order`)
- Create: `enid/order/migrations/0003_order_sale_date.py`
- Modify: `enid/revenue/views.py` (`_monthly_sums`, `SummaryRevenueView._sum`, `_year_total_by_month`, `ByProductRevenueView`)
- Test: `enid/revenue/tests/test_effective_date.py` (nuevo)

**Interfaces:**
- Produces: `Order.sale_date` (DateTimeField, nullable). Fecha efectiva usada por revenue = `Coalesce('order__sale_date', 'order__created_at')`.

- [x] **Step 1: Escribir el test que falla**

Create `enid/revenue/tests/test_effective_date.py`:

```python
from datetime import datetime
import pytz
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from order.models import Order
from item_order.models import ItemOrder
from revenue.tests.test_monthly import _make_address, _make_product

User = get_user_model()


class EffectiveDateRevenueTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser('a@t.com', 'a@t.com', 'pass')
        self.client.force_authenticate(user=self.admin)
        self.address = _make_address()

    def _order_with_sale_date(self, created_year, created_month, sale_year, sale_month):
        created = datetime(created_year, created_month, 15, 12, 0, tzinfo=pytz.UTC)
        sale = datetime(sale_year, sale_month, 15, 12, 0, tzinfo=pytz.UTC)
        order = Order.objects.create(shipping_address=self.address, status='delivered')
        Order.objects.filter(pk=order.pk).update(created_at=created, sale_date=sale)
        ItemOrder.objects.create(order=order, product=_make_product(), quantity=1, price=500)
        return order

    def test_sale_date_overrides_created_at_in_summary(self):
        # Orden creada en enero pero vendida (histórica) en abril → cuenta en abril.
        self._order_with_sale_date(2025, 1, 2025, 4)
        resp = self.client.get('/revenue/summary/', {'year': 2025, 'month': 4})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(float(resp.data['recibidos']), 500.0)

    def test_null_sale_date_falls_back_to_created_at(self):
        # Sin sale_date → se usa created_at (no regresión).
        order = Order.objects.create(shipping_address=self.address, status='delivered')
        created = datetime(2025, 7, 10, 12, 0, tzinfo=pytz.UTC)
        Order.objects.filter(pk=order.pk).update(created_at=created)
        ItemOrder.objects.create(order=order, product=_make_product(), quantity=1, price=300)
        resp = self.client.get('/revenue/summary/', {'year': 2025, 'month': 7})
        self.assertEqual(float(resp.data['recibidos']), 300.0)
```

- [x] **Step 2: Correr el test y verificar que falla**

Run: `docker exec enid_store_service python manage.py test revenue.tests.test_effective_date -v 2`
Expected: FAIL — `Order` no tiene campo `sale_date` (error al hacer `.update(sale_date=...)`).

- [x] **Step 3: Añadir `sale_date` al modelo `Order`**

En `enid/order/models.py`, dentro de la clase `Order` (junto a `source`):

```python
    sale_date = models.DateTimeField(
        null=True, blank=True,
        help_text="Fecha real de la venta (para ventas manuales/históricas). "
                  "Si es nulo se usa created_at.",
    )
```

- [x] **Step 4: Crear la migración de Order**

Run: `docker exec enid_store_service python manage.py makemigrations order`
Expected: genera `order/migrations/0003_order_sale_date.py`, `dependencies = [('order', '0002_delivery_date_end')]`.

- [x] **Step 5: Refactorizar revenue a fecha efectiva**

En `enid/revenue/views.py`, añadir import en la línea 5:

```python
from django.db.models.functions import ExtractMonth, Coalesce
```

Reemplazar `_monthly_sums` (líneas 19-26) por:

```python
def _monthly_sums(year, group):
    return (
        ItemOrder.objects
        .annotate(effective_date=Coalesce('order__sale_date', 'order__created_at'))
        .filter(effective_date__year=year, order__status__in=group)
        .annotate(month=ExtractMonth('effective_date'))
        .values('month')
        .annotate(total=Sum(F('price') * F('quantity'), output_field=DecimalField()))
    )
```

Reemplazar el cuerpo de `_sum` dentro de `SummaryRevenueView.get` (líneas 59-69) por:

```python
        def _sum(statuses):
            result = (
                ItemOrder.objects
                .annotate(effective_date=Coalesce('order__sale_date', 'order__created_at'))
                .filter(
                    effective_date__year=year,
                    effective_date__month=month,
                    order__status__in=statuses,
                )
                .aggregate(total=Sum(F('price') * F('quantity'), output_field=DecimalField()))
            )
            return result['total'] or Decimal('0.00')
```

Reemplazar `_year_total_by_month` (líneas 84-93) por:

```python
def _year_total_by_month(year, statuses):
    """Returns {month: total} for a given year and status list (effective date)."""
    qs = (
        ItemOrder.objects
        .annotate(effective_date=Coalesce('order__sale_date', 'order__created_at'))
        .filter(effective_date__year=year, order__status__in=statuses)
        .annotate(month=ExtractMonth('effective_date'))
        .values('month')
        .annotate(total=Sum(F('price') * F('quantity'), output_field=DecimalField()))
    )
    return {r['month']: r['total'] for r in qs}
```

En `ByProductRevenueView.get`, reemplazar el `.filter(...)` (líneas 127-132) por una versión con fecha efectiva:

```python
            ItemOrder.objects
            .annotate(effective_date=Coalesce('order__sale_date', 'order__created_at'))
            .filter(
                effective_date__year=year,
                effective_date__month=month,
                order__status__in=ALL_COUNTED,
            )
```

- [x] **Step 6: Correr tests (nuevos + regresión revenue completa)**

Run: `docker exec enid_store_service python manage.py test revenue -v 2`
Expected: PASS (incluye los 4 test suites existentes de revenue sin regresión).

- [x] **Step 7: Commit**

```bash
git add enid/order/models.py enid/order/migrations/0003_order_sale_date.py \
        enid/revenue/views.py enid/revenue/tests/test_effective_date.py
git commit -m "#0: Order.sale_date + fecha efectiva Coalesce en revenue"
```

---

## Task 4: Transición automática `published → candidate` (signals)

Al guardarse una `Order`/`ItemOrder` con `status in RECIBIDOS`, promover a `candidate` los productos de la orden que estén en `published`. Idempotente; nunca degrada `certified`.

**Files:**
- Create: `enid/products/services.py`
- Create: `enid/products/signals.py`
- Modify: `enid/products/apps.py` (método `ready`)
- Test: `enid/products/tests/test_auto_candidate.py` (nuevo)

**Interfaces:**
- Consumes: `Product.certification` (Task 2), `Order.sale_date` no requerido aquí, `revenue.constants.RECIBIDOS` (Task 1).
- Produces: `products.services.promote_products_to_candidate(order) -> None`.

- [x] **Step 1: Escribir el test que falla**

Create `enid/products/tests/test_auto_candidate.py`:

```python
from django.test import TestCase
from categories.models import Category
from products.models import Product
from order.models import Order
from item_order.models import ItemOrder


def _make_product(name='p'):
    cat, _ = Category.objects.get_or_create(name=f'cat-{name}', slug=f'cat-{name}')
    return Product.objects.create(
        category=cat, name=name, specific_name=name, price=100, cost=50
    )


class AutoCandidateTest(TestCase):
    def test_income_order_promotes_published_to_candidate(self):
        product = _make_product('promote')
        order = Order.objects.create(status='delivered')
        ItemOrder.objects.create(order=order, product=product, quantity=1, price=100)
        product.refresh_from_db()
        self.assertEqual(product.certification, 'candidate')

    def test_non_income_status_keeps_published(self):
        product = _make_product('keep')
        order = Order.objects.create(status='pending')
        ItemOrder.objects.create(order=order, product=product, quantity=1, price=100)
        product.refresh_from_db()
        self.assertEqual(product.certification, 'published')

    def test_income_order_never_degrades_certified(self):
        product = _make_product('cert')
        product.certification = 'certified'
        product.save(update_fields=['certification'])
        order = Order.objects.create(status='delivered')
        ItemOrder.objects.create(order=order, product=product, quantity=1, price=100)
        product.refresh_from_db()
        self.assertEqual(product.certification, 'certified')
```

- [x] **Step 2: Correr el test y verificar que falla**

Run: `docker exec enid_store_service python manage.py test products.tests.test_auto_candidate -v 2`
Expected: FAIL — en `test_income_order_promotes...`, `certification` sigue `'published'` (aún no hay signal).

- [x] **Step 3: Crear el servicio de promoción**

Create `enid/products/services.py`:

```python
"""Lógica de negocio de certificación de productos."""
from revenue.constants import RECIBIDOS
from products.models import Product


def promote_products_to_candidate(order):
    """Promueve a 'candidate' los productos 'published' de una orden con ingreso real.

    Idempotente: el filtro certification='published' deja intactos los productos
    ya 'candidate' o 'certified' (una venta posterior nunca degrada un certified).
    """
    if order.status not in RECIBIDOS:
        return
    product_ids = list(order.items.values_list('product_id', flat=True))
    if not product_ids:
        return
    Product.objects.filter(
        id__in=product_ids, certification='published'
    ).update(certification='candidate')
```

- [x] **Step 4: Crear los receivers de signals**

Create `enid/products/signals.py`:

```python
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from order.models import Order
from item_order.models import ItemOrder
from products.services import promote_products_to_candidate

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def _promote_on_order_save(sender, instance, **kwargs):
    try:
        promote_products_to_candidate(instance)
    except Exception:
        # No romper el guardado de la orden. Sin PII: solo el pk.
        logger.error("Fallo promoviendo productos a candidate (order=%s)", instance.pk)


@receiver(post_save, sender=ItemOrder)
def _promote_on_item_order_save(sender, instance, **kwargs):
    try:
        promote_products_to_candidate(instance.order)
    except Exception:
        logger.error("Fallo promoviendo productos a candidate (item_order=%s)", instance.pk)
```

- [x] **Step 5: Registrar los signals en `apps.ready`**

Leer `enid/products/apps.py`. Debe quedar así (ajustar `name` si ya difiere; conservar el existente):

```python
from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'products'

    def ready(self):
        import products.signals  # noqa: F401  (registra receivers post_save)
```

Verificar que `enid/products/__init__.py` tenga `default_app_config` o que `INSTALLED_APPS` use `'products'` (Django 4.2 autodetecta `ProductsConfig`). Si `INSTALLED_APPS` lista `'products.apps.ProductsConfig'`, dejarlo.

- [x] **Step 6: Correr el test y verificar que pasa**

Run: `docker exec enid_store_service python manage.py test products.tests.test_auto_candidate -v 2`
Expected: PASS (los 3 tests).

- [x] **Step 7: Commit**

```bash
git add enid/products/services.py enid/products/signals.py enid/products/apps.py \
        enid/products/tests/test_auto_candidate.py
git commit -m "#0: signal post_save promueve published->candidate al detectar ingreso"
```

---

## Task 5: Endpoint `PATCH /productos/{id}/certification/` (transiciones manuales)

**Files:**
- Modify: `enid/products/views.py` (clase `ProductVuewSet`: nueva `@action` + imports)
- Test: `enid/products/tests/test_certification_endpoint.py` (nuevo)

**Interfaces:**
- Consumes: `Product.CERTIFICATION_CHOICES` (Task 2).
- Produces: ruta `PATCH /productos/{pk}/certification/` body `{"certification": "<estado>"}`, `IsAdminUser`. Devuelve `ProductSerializer` del producto actualizado; `400` transición inválida; `403` no-admin.

- [x] **Step 1: Escribir el test que falla** ✅ (2026-11-13)

Create `enid/products/tests/test_certification_endpoint.py`:

```python
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from categories.models import Category
from products.models import Product

User = get_user_model()


def _make_product(certification='candidate'):
    cat, _ = Category.objects.get_or_create(name='cat-ep', slug='cat-ep')
    p = Product.objects.create(
        category=cat, name='ep', specific_name='ep', price=100, cost=50
    )
    p.certification = certification
    p.save(update_fields=['certification'])
    return p


class CertificationEndpointTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser('ad@t.com', 'ad@t.com', 'pass')

    def _url(self, pk):
        return f'/productos/{pk}/certification/'

    def test_admin_confirms_candidate_to_certified(self):
        self.client.force_authenticate(user=self.admin)
        product = _make_product('candidate')
        resp = self.client.patch(self._url(product.id), {'certification': 'certified'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        product.refresh_from_db()
        self.assertEqual(product.certification, 'certified')
        self.assertIsNotNone(product.certified_at)

    def test_override_published_to_certified(self):
        self.client.force_authenticate(user=self.admin)
        product = _make_product('published')
        resp = self.client.patch(self._url(product.id), {'certification': 'certified'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        product.refresh_from_db()
        self.assertEqual(product.certification, 'certified')

    def test_revert_certified_clears_certified_at(self):
        self.client.force_authenticate(user=self.admin)
        product = _make_product('candidate')
        self.client.patch(self._url(product.id), {'certification': 'certified'}, format='json')
        resp = self.client.patch(self._url(product.id), {'certification': 'candidate'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        product.refresh_from_db()
        self.assertEqual(product.certification, 'candidate')
        self.assertIsNone(product.certified_at)

    def test_invalid_state_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        product = _make_product('published')
        resp = self.client.patch(self._url(product.id), {'certification': 'xxx'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_admin_returns_403(self):
        plain = User.objects.create_user('u@t.com', 'u@t.com', 'pass')
        self.client.force_authenticate(user=plain)
        product = _make_product('candidate')
        resp = self.client.patch(self._url(product.id), {'certification': 'certified'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
```

- [x] **Step 2: Correr el test y verificar que falla** ✅ (2026-11-13) — 405, ruta no existía

Run: `docker exec enid_store_service python manage.py test products.tests.test_certification_endpoint -v 2`
Expected: FAIL — `404` (la ruta `certification` no existe).

- [x] **Step 3: Añadir la `@action` `certification`** ✅ (2026-11-13)

En `enid/products/views.py`, añadir imports arriba:

```python
from rest_framework.permissions import IsAdminUser
from django.utils import timezone
```

Dentro de `ProductVuewSet` (después de `primary_products`):

```python
    ALLOWED_TRANSITIONS = {
        'published': {'candidate', 'certified'},
        'candidate': {'certified', 'published'},
        'certified': {'candidate', 'published'},
    }

    @action(detail=True, methods=['patch'], url_path='certification',
            permission_classes=[IsAdminUser])
    def certification(self, request, pk=None):
        product = self.get_object()
        target = request.data.get('certification')
        valid = dict(Product.CERTIFICATION_CHOICES)
        if target not in valid:
            return Response({'error': 'Estado de certificación inválido'}, status=400)
        if target != product.certification and target not in self.ALLOWED_TRANSITIONS[product.certification]:
            return Response(
                {'error': f'Transición no permitida: {product.certification} → {target}'},
                status=400,
            )
        product.certification = target
        product.certified_at = timezone.now() if target == 'certified' else None
        product.save(update_fields=['certification', 'certified_at'])
        return Response(ProductSerializer(product).data)
```

- [x] **Step 4: Correr el test y verificar que pasa** ✅ (2026-11-13) — 5/5 OK

Run: `docker exec enid_store_service python manage.py test products.tests.test_certification_endpoint -v 2`
Expected: PASS (los 5 tests).

- [x] **Step 5: Commit** ✅ (2026-11-13)

```bash
git add enid/products/views.py enid/products/tests/test_certification_endpoint.py
git commit -m "#0: endpoint PATCH /productos/{id}/certification/ (transiciones admin)"
```

---

## Task 6: Endpoint `POST /productos/manual-sale/` (venta manual/histórica)

Crea `Order` (`source='admin_manual'`, status de ingreso) + `ItemOrder`s. Dispara el signal de Task 4 y cuenta en revenue (Task 3).

**Files:**
- Modify: `enid/products/views.py` (clase `ProductVuewSet`: nueva `@action` + imports)
- Test: `enid/products/tests/test_manual_sale.py` (nuevo)

**Interfaces:**
- Consumes: `Order.sale_date` (Task 3), signal de promoción (Task 4), `revenue.constants.RECIBIDOS` (Task 1).
- Produces: ruta `POST /productos/manual-sale/` body `{"items": [{"product": id, "quantity": n, "price": d}], "status": "delivered", "sale_date": "ISO|null"}`, `IsAdminUser`. Devuelve `201` `{"order_id", "status"}`; `400` sin items / producto inexistente / status inválido; `403` no-admin.

- [x] **Step 1: Escribir el test que falla** ✅ (2026-11-13)

Create `enid/products/tests/test_manual_sale.py`:

```python
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from categories.models import Category
from products.models import Product
from order.models import Order

User = get_user_model()


def _make_product():
    cat, _ = Category.objects.get_or_create(name='cat-ms', slug='cat-ms')
    return Product.objects.create(
        category=cat, name='ms', specific_name='ms', price=100, cost=50
    )


class ManualSaleTest(TestCase):
    URL = '/productos/manual-sale/'

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser('ms@t.com', 'ms@t.com', 'pass')

    def test_manual_sale_with_historical_date_counts_and_promotes(self):
        self.client.force_authenticate(user=self.admin)
        product = _make_product()
        payload = {
            'items': [{'product': product.id, 'quantity': 2, 'price': 250}],
            'status': 'delivered',
            'sale_date': '2025-03-15T12:00:00Z',
        }
        resp = self.client.post(self.URL, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Orden creada como manual
        order = Order.objects.get(pk=resp.data['order_id'])
        self.assertEqual(order.source, 'admin_manual')
        self.assertIsNotNone(order.sale_date)
        # Producto promovido a candidate por el signal
        product.refresh_from_db()
        self.assertEqual(product.certification, 'candidate')
        # Cuenta en revenue en marzo 2025 (fecha efectiva = sale_date)
        summary = self.client.get('/revenue/summary/', {'year': 2025, 'month': 3})
        self.assertEqual(float(summary.data['recibidos']), 500.0)

    def test_no_items_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.URL, {'items': [], 'status': 'delivered'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_product_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        payload = {'items': [{'product': 999999, 'quantity': 1, 'price': 10}], 'status': 'delivered'}
        resp = self.client.post(self.URL, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_status_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        product = _make_product()
        payload = {'items': [{'product': product.id, 'quantity': 1, 'price': 10}], 'status': 'pending'}
        resp = self.client.post(self.URL, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_admin_returns_403(self):
        plain = User.objects.create_user('u2@t.com', 'u2@t.com', 'pass')
        self.client.force_authenticate(user=plain)
        product = _make_product()
        payload = {'items': [{'product': product.id, 'quantity': 1, 'price': 10}], 'status': 'delivered'}
        resp = self.client.post(self.URL, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
```

- [x] **Step 2: Correr el test y verificar que falla** ✅ (2026-11-13) — 5 fallan, ruta no existía

Run: `docker exec enid_store_service python manage.py test products.tests.test_manual_sale -v 2`
Expected: FAIL — `404` (ruta `manual-sale` no existe).

- [x] **Step 3: Añadir la `@action` `manual_sale`** ✅ (2026-11-13)

En `enid/products/views.py` añadir imports:

```python
from django.db import transaction
from order.models import Order
from item_order.models import ItemOrder
from revenue.constants import RECIBIDOS
```

Dentro de `ProductVuewSet`:

```python
    @action(detail=False, methods=['post'], url_path='manual-sale',
            permission_classes=[IsAdminUser])
    def manual_sale(self, request):
        items = request.data.get('items') or []
        status_val = request.data.get('status', 'delivered')
        sale_date = request.data.get('sale_date') or None

        if not items:
            return Response({'error': 'Se requiere al menos un item'}, status=400)
        if status_val not in RECIBIDOS:
            return Response(
                {'error': f'status inválido; usar uno de {RECIBIDOS}'}, status=400
            )
        # Validar productos antes de crear nada
        resolved = []
        for it in items:
            product = Product.objects.filter(pk=it.get('product')).first()
            if not product:
                return Response({'error': 'Producto inexistente'}, status=400)
            resolved.append((product, it.get('quantity', 1), it.get('price')))

        with transaction.atomic():
            order = Order.objects.create(
                status=status_val, source='admin_manual', sale_date=sale_date
            )
            for product, quantity, price in resolved:
                ItemOrder.objects.create(
                    order=order, product=product, quantity=quantity, price=price
                )
        return Response({'order_id': order.id, 'status': order.status}, status=201)
```

- [x] **Step 4: Correr el test y verificar que pasa** ✅ (2026-11-13) — 5/5 OK

Run: `docker exec enid_store_service python manage.py test products.tests.test_manual_sale -v 2`
Expected: PASS (los 5 tests).

- [x] **Step 5: Correr la suite de backend completa (regresión)** ✅ (2026-11-13) — sin fallos nuevos; los 23 fails/errors son pre-existentes (union de baselines products/order/revenue)

Run: `docker exec enid_store_service python manage.py test products order item_order revenue -v 2`
Expected: PASS, cero fallos.

- [x] **Step 6: Commit** ✅ (2026-11-13)

```bash
git add enid/products/views.py enid/products/tests/test_manual_sale.py
git commit -m "#0: endpoint POST /productos/manual-sale/ (venta manual/histórica)"
```

---

## Task 7: Frontend admin `service-store` (badge + certificar + venta manual)

Repo frontend: `/home/arithgrey/enid/service-store` (repo git anidado; commitear en su propia `develop`). Axios: `this.$axios` (Options API), paths con prefijo `enid/`.

**Files:**
- Create: `service-store/src/components/Products/ProductCertificationConfig.vue`
- Create: `service-store/src/components/Products/ManualSaleForm.vue`
- Modify: la vista de detalle/config de producto admin `service-store/src/views/Product/ProductDetail.vue` (montar los dos componentes nuevos)
- Test: `service-store/tests/ProductCertificationConfig.spec.js` (Jest, patrón existente)

**Interfaces:**
- Consumes (backend Task 5 y 6): `PATCH enid/productos/{id}/certification/` body `{certification}`; `POST enid/productos/manual-sale/` body `{items, status, sale_date}`. El `ProductSerializer` ya expone `certification` y `certified_at` (`fields='__all__'`).

- [x] **Step 1: Escribir el test que falla (Jest)** ✅ (2026-11-13)

Create `service-store/tests/ProductCertificationConfig.spec.js`:

```javascript
import { mount } from '@vue/test-utils';
import ProductCertificationConfig from '@/components/Products/ProductCertificationConfig.vue';

// Tests de render puro: NO invocan this.$axios (no se llama certify()),
// por eso no se inyecta ningún mock/stub de red (cumple el HARD-GATE sin mocks).
describe('ProductCertificationConfig', () => {
  it('muestra el badge con el estado de certificación', () => {
    const wrapper = mount(ProductCertificationConfig, {
      props: { product: { id: 1, certification: 'candidate' } },
    });
    expect(wrapper.text()).toContain('Candidato');
  });

  it('muestra el botón Certificar solo cuando es candidate', () => {
    const wrapper = mount(ProductCertificationConfig, {
      props: { product: { id: 1, certification: 'candidate' } },
    });
    expect(wrapper.find('[data-test="certify-btn"]').exists()).toBe(true);
  });

  it('oculta el botón Certificar cuando ya está certified', () => {
    const wrapper = mount(ProductCertificationConfig, {
      props: { product: { id: 1, certification: 'certified' } },
    });
    expect(wrapper.find('[data-test="certify-btn"]').exists()).toBe(false);
  });
});
```

- [x] **Step 2: Correr el test y verificar que falla** ✅ (2026-11-13) — módulo no existe

Run: `docker exec service-store-frontend-1 npx jest tests/ProductCertificationConfig.spec.js`
Expected: FAIL — no existe el componente.

- [x] **Step 3: Crear `ProductCertificationConfig.vue`** ✅ (2026-11-13)

Create `service-store/src/components/Products/ProductCertificationConfig.vue`:

```vue
<template>
  <div class="certification-config">
    <span :class="['badge', badgeClass]" data-test="cert-badge">{{ label }}</span>
    <button
      v-if="product.certification === 'candidate'"
      data-test="certify-btn"
      @click="certify"
    >
      Certificar
    </button>
  </div>
</template>

<script>
export default {
  name: 'ProductCertificationConfig',
  props: {
    product: { type: Object, required: true },
  },
  computed: {
    label() {
      return {
        published: 'Publicado',
        candidate: 'Candidato',
        certified: 'Certificado',
      }[this.product.certification] || 'Publicado';
    },
    badgeClass() {
      return `badge--${this.product.certification}`;
    },
  },
  methods: {
    async certify() {
      const { data } = await this.$axios.patch(
        `enid/productos/${this.product.id}/certification/`,
        { certification: 'certified' }
      );
      this.$emit('updated', data);
    },
  },
};
</script>
```

- [x] **Step 4: Crear `ManualSaleForm.vue`** ✅ (2026-11-13)

Create `service-store/src/components/Products/ManualSaleForm.vue`:

```vue
<template>
  <form class="manual-sale-form" @submit.prevent="submit">
    <h4>Registrar venta manual</h4>
    <label>Cantidad
      <input v-model.number="quantity" type="number" min="1" data-test="ms-qty" />
    </label>
    <label>Precio
      <input v-model.number="price" type="number" min="0" step="0.01" data-test="ms-price" />
    </label>
    <label>Estado
      <select v-model="status" data-test="ms-status">
        <option value="delivered">Entregado</option>
        <option value="payment_confirmed">Pago Confirmado</option>
        <option value="cash_on_delivery">Pagado contra Entrega</option>
      </select>
    </label>
    <label>Fecha de venta (opcional)
      <input v-model="saleDate" type="datetime-local" data-test="ms-date" />
    </label>
    <button type="submit" data-test="ms-submit">Registrar</button>
  </form>
</template>

<script>
export default {
  name: 'ManualSaleForm',
  props: { product: { type: Object, required: true } },
  data() {
    return { quantity: 1, price: this.product.price, status: 'delivered', saleDate: '' };
  },
  methods: {
    async submit() {
      const payload = {
        items: [{ product: this.product.id, quantity: this.quantity, price: this.price }],
        status: this.status,
        sale_date: this.saleDate ? new Date(this.saleDate).toISOString() : null,
      };
      const { data } = await this.$axios.post('enid/productos/manual-sale/', payload);
      this.$emit('sale-registered', data);
    },
  },
};
</script>
```

- [x] **Step 5: Montar ambos componentes en la vista de producto admin** ✅ (2026-11-13)

En `service-store/src/views/Product/ProductDetail.vue`, importar y montar (con `@/`):

```javascript
import ProductCertificationConfig from '@/components/Products/ProductCertificationConfig.vue';
import ManualSaleForm from '@/components/Products/ManualSaleForm.vue';
```

Registrar en `components: { ... }` y en el template, dentro de la sección admin del producto:

```html
<ProductCertificationConfig :product="product" @updated="onProductUpdated" />
<ManualSaleForm :product="product" @sale-registered="onSaleRegistered" />
```

Añadir handlers mínimos en `methods` que refresquen el producto (reutilizar el fetch existente de la vista; si hay `fetchProduct()`, llamarlo):

```javascript
onProductUpdated(updated) { this.product = { ...this.product, ...updated }; },
onSaleRegistered() { if (this.fetchProduct) this.fetchProduct(); },
```

- [x] **Step 6: Correr el test y verificar que pasa** ✅ (2026-11-13) — 3/3 PASS

- [x] **Step 7: Commit (en el repo anidado service-store, rama develop)** ✅ (2026-11-13)

```bash
cd /home/arithgrey/enid/service-store
git add src/components/Products/ProductCertificationConfig.vue \
        src/components/Products/ManualSaleForm.vue \
        src/views/Product/ProductDetail.vue \
        tests/ProductCertificationConfig.spec.js
git commit -m "#0: UI admin certificación (badge + certificar + venta manual)"
```

---

**Progreso:** 7/7 Tasks (100%) ✅ COMPLETO

> NOTA Task 7 (2026-11-13) — desviaciones del plan:
> 1. Spec ubicado en `tests/unit/components/Products/ProductCertificationConfig.spec.js` (patrón real del repo), no en `tests/`.
> 2. Componentes montados en `src/components/Products/ProductConfig.vue` (agregador admin real, junto a ProductDeliverySchedulingConfig/InventoryConfig), NO en `views/Product/ProductDetail.vue` (esa es la vista PÚBLICA; montar controles admin ahí sería incorrecto).
> 3. BLOQUEO infra resuelto: se borró `src/.babelrc.js` — stub ESM muerto (`export default` + `"type":"module"`) que rompía Jest para TODOS los specs de componentes (babel-jest síncrono no carga config ESM). Vite no usa babel; babel.config.json raíz ya cubre. Aprobado por el usuario. Mis 3 tests pasan. `FormCheckout.spec.js` sigue fallando por otra causa pre-existente ajena (`import.meta`).

> NOTA Task 6 (2026-11-13): helper reusa fila sembrada (colisión secuencia Postgres). Regresión `products.tests order item_order revenue`: 23 fails/errors TODOS pre-existentes (14 de products.tests + 9 de order/item_order/revenue, confirmado por baselines separados). Los 15 tests de la feature certificación pasan.

> NOTA Task 5 (2026-11-13): helper `_make_product` reusa fila sembrada (`Product.objects.first()`) en vez de crear filas nuevas, para evitar colisión de secuencia de Postgres — mismo patrón que Task 4. 5/5 tests verdes. La suite completa `products.tests` tiene 10 fails + 4 errors PRE-EXISTENTES (es_publico/top_sellers/serializers/create_multiple) ajenos a esta task, confirmados en develop limpio.
> NOTA Task 4: services.py y signals.py YA existían (seeder post_migrate); se AÑADIÓ (append), no se sobreescribió. apps.ready ya importaba products.signals.

> NOTA (2026-11-13): `**/migrations/` está en `.gitignore` del repo enid-store y NINGUNA migración se trackea. Las migraciones se regeneran con `makemigrations`; no se commitean (desviación necesaria del texto literal del plan). Helpers de test reusan filas sembradas por el post_migrate del entorno para evitar colisiones de secuencia de Postgres.

## Verificación final (antes de dar por completo)

- [x] Backend tests de la feature verdes ✅ (2026-11-13) — 39/39 OK (`products.tests.test_certification_model/test_certification_endpoint/test_auto_candidate/test_manual_sale` + `revenue`). Suite completa `products order item_order revenue`: 126 tests, los 27 fails/errors restantes son PRE-EXISTENTES y ajenos (colisión seed `categories_category_pkey`, `source`, `top_sellers`, `es_publico`, imágenes). **Fix aplicado:** colisión `products/tests.py` vs `products/tests/` rompía el discovery de todo el app → se movió a `products/tests/test_image_integration.py` (commit `eba13e1` en enid-store/develop).
- [x] Frontend certificación verde ✅ (2026-11-13) — `ProductCertificationConfig.spec.js` 3/3 OK. Suites `FormCheckout`/`import.meta` rojas son config pre-existente ajena a la feature.
- [x] Verificación manual en browser como admin ✅ (2026-11-13) — vista `/agregar-producto` (ProductListAdmin). (1) Badge visible: "● Candidato" (amarillo) → "● Certificado" (verde). (2) Botón Certificar aparece solo en candidate, desaparece al certificar. (3) Transición candidate→certified vía PATCH `/enid/productos/1/certification/` → 200 (con auto-refresh de token). (4) Venta manual: orden creada (37→38), `status=delivered`, `source=admin_manual`.
  - 🐛 **BUG encontrado y corregido:** `ProductConfig.vue onProductUpdated` reasignaba el prop readonly `this.product` → `TypeError: 'set' on proxy ... property 'product'` → badge no refrescaba en vivo (backend sí persistía). Fix: `Object.assign(this.product, updated)` (commit `9785a3b` en service-store/develop). Verificado: badge ahora refresca en vivo.
  - NOTA: los 502 de `landings/*` ("Configurar Landings") son service-landings caído (infra pre-existente), ajeno a esta feature.
  - 🐛 **BUG #2 encontrado y corregido:** `ManualSaleForm` no deshabilitaba el botón ni tenía guard de re-entrada → doble click (o replay del interceptor tras 401→refresh) creaba órdenes duplicadas (se observó una orden `admin_manual` de más). Fix: flag `submitting` + `:disabled` + early-return en `submit()` (commit `b84662b` en service-store/develop). Test de regresión RED→GREEN sin mocks. Verificado en browser: doble click → una sola orden.
