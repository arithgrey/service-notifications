# Earnings Dashboard — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dashboard de ingresos para admins con 4 endpoints Django de agregación + vistas Vue de gráficas, cobros pendientes y cobros recibidos.

**Architecture:** Nueva Django app `revenue` con 4 `APIView`s que agregan sobre `Order`/`ItemOrder`. Frontend Vue en `service-store` con `chart.js`+`vue-chartjs` para gráficas; sin Pinia, estado local en `Rendimiento.vue`.

**Tech Stack:** Django REST Framework, Python 3.8, Vue 3, chart.js 4, vue-chartjs 5, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-11-12-earnings-dashboard-design.md`

## Global Constraints

- Montos en MXN: formato `$#,###.## MXN` en frontend
- `Order.created_at` está en UTC — agrupar en UTC
- Solo `IsAdminUser` puede acceder a los 4 endpoints
- Meses futuros en comparison devuelven `null` (no `0`)
- `pct` en by-product redondeado a 1 decimal
- Sin mocks en tests — solo Django TestCase con objetos reales
- `year` default = año actual; `month` default = mes actual
- Statuses recibidos: `payment_confirmed`, `delivered`, `cash_on_delivery`
- Statuses pendientes: `pending`, `preparing`, `ready_for_shipping`, `in_transit`, `ready_for_pickup`
- Statuses excluidos (no cuentan): `returned`, `refund_processed`, `canceled`
- `chart.js` v4 + `vue-chartjs` v5 (compatibles entre sí)

---

### Task 1: Backend — revenue app scaffold + endpoints monthly y summary

**Files:**
- Create: `enid-store/enid/revenue/__init__.py`
- Create: `enid-store/enid/revenue/apps.py`
- Create: `enid-store/enid/revenue/urls.py`
- Create: `enid-store/enid/revenue/serializers.py`
- Create: `enid-store/enid/revenue/views.py` (MonthlyRevenueView + SummaryRevenueView)
- Create: `enid-store/enid/revenue/tests/__init__.py`
- Create: `enid-store/enid/revenue/tests/test_monthly.py`
- Create: `enid-store/enid/revenue/tests/test_summary.py`
- Modify: `enid-store/enid/enid/settings.py` → añadir `'revenue'` a INSTALLED_APPS
- Modify: `enid-store/enid/enid/urls.py` → añadir `path('revenue/', include('revenue.urls'))`

**Interfaces:**
- Produces: `GET /enid/revenue/monthly/?year=YYYY` → `[{"month": int, "recibidos": float, "pendientes": float}]` (12 items)
- Produces: `GET /enid/revenue/summary/?year=YYYY&month=MM` → `{"recibidos": float, "pendientes": float, "total": float}`

- [x] **Step 1: Crear la app revenue (scaffold)** ✅ (2026-11-13)

Dentro del contenedor enid-store (`docker exec <SERVICENAME>_service ...`):

```bash
docker exec microservice_enid_service python manage.py startapp revenue
```

Si falla por nombre del contenedor, verifica con `docker ps | grep enid`. Luego mueve los archivos a `enid-store/enid/revenue/` si se crearon en otro directorio.

Crear manualmente si es más rápido:

```python
# enid-store/enid/revenue/__init__.py
# (vacío)
```

```python
# enid-store/enid/revenue/apps.py
from django.apps import AppConfig

class RevenueConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'revenue'
```

- [x] **Step 2: Escribir tests que fallan — test_monthly.py** ✅ (2026-11-13)

```python
# enid-store/enid/revenue/tests/test_monthly.py
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import User
from order.models import Order
from item_order.models import ItemOrder
from address.models import Address
from state.models import State
from products.models import Product
from categories.models import Category
from datetime import datetime
import pytz


RECIBIDOS = ['payment_confirmed', 'delivered', 'cash_on_delivery']
PENDIENTES = ['pending', 'preparing', 'ready_for_shipping', 'in_transit', 'ready_for_pickup']
EXCLUIDOS  = ['returned', 'refund_processed', 'canceled']


def _make_address():
    state, _ = State.objects.get_or_create(name="CDMX")
    return Address.objects.create(
        postal_code='12345', street='Calle', number=1,
        interior_number=1, colony='Col', delegation_or_municipality='Del',
        city='CDMX', state=state, phone_number='5551234567'
    )


def _make_user(username='test@test.com'):
    return User.objects.create_user(username=username, password='pass', email=username)


def _make_product():
    cat, _ = Category.objects.get_or_create(name='Cat')
    return Product.objects.create(
        name='Prod', price=100, description='desc',
        category=cat, stock=10
    )


def _make_order(address, user, status_val, year, month, price=100, qty=1):
    dt = datetime(year, month, 15, 12, 0, 0, tzinfo=pytz.UTC)
    order = Order.objects.create(
        shipping_address=address, user=user, status=status_val
    )
    Order.objects.filter(pk=order.pk).update(created_at=dt)
    order.refresh_from_db()
    product = _make_product()
    ItemOrder.objects.create(order=order, product=product, quantity=qty, price=price)
    return order


class MonthlyRevenueTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser('admin@t.com', 'admin@t.com', 'pass')
        self.client.force_authenticate(user=self.admin)
        self.address = _make_address()
        self.user = _make_user()

    def test_returns_12_months(self):
        resp = self.client.get('/revenue/monthly/', {'year': 2025})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 12)
        months = [d['month'] for d in resp.data]
        self.assertEqual(months, list(range(1, 13)))

    def test_recibidos_sum_correct(self):
        _make_order(self.address, self.user, 'payment_confirmed', 2025, 3, price=500, qty=2)
        _make_order(self.address, self.user, 'delivered', 2025, 3, price=300, qty=1)
        resp = self.client.get('/revenue/monthly/', {'year': 2025})
        march = next(d for d in resp.data if d['month'] == 3)
        self.assertEqual(float(march['recibidos']), 1300.0)
        self.assertEqual(float(march['pendientes']), 0.0)

    def test_pendientes_sum_correct(self):
        _make_order(self.address, self.user, 'pending', 2025, 5, price=200, qty=3)
        resp = self.client.get('/revenue/monthly/', {'year': 2025})
        may = next(d for d in resp.data if d['month'] == 5)
        self.assertEqual(float(may['pendientes']), 600.0)

    def test_excluidos_not_counted(self):
        _make_order(self.address, self.user, 'canceled', 2025, 7, price=999, qty=1)
        resp = self.client.get('/revenue/monthly/', {'year': 2025})
        july = next(d for d in resp.data if d['month'] == 7)
        self.assertEqual(float(july['recibidos']), 0.0)
        self.assertEqual(float(july['pendientes']), 0.0)

    def test_empty_months_return_zero(self):
        resp = self.client.get('/revenue/monthly/', {'year': 2099})
        for d in resp.data:
            self.assertEqual(float(d['recibidos']), 0.0)
            self.assertEqual(float(d['pendientes']), 0.0)

    def test_requires_admin(self):
        regular = _make_user('regular@t.com')
        self.client.force_authenticate(user=regular)
        resp = self.client.get('/revenue/monthly/', {'year': 2025})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
```

- [x] **Step 3: Escribir tests que fallan — test_summary.py** ✅ (2026-11-13)

```python
# enid-store/enid/revenue/tests/test_summary.py
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import User
from order.models import Order
from item_order.models import ItemOrder
from address.models import Address
from state.models import State
from products.models import Product
from categories.models import Category
from datetime import datetime
import pytz
from revenue.tests.test_monthly import _make_address, _make_user, _make_order


class SummaryRevenueTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser('admin@t.com', 'admin@t.com', 'pass')
        self.client.force_authenticate(user=self.admin)
        self.address = _make_address()
        self.user = _make_user()

    def test_summary_recibidos_and_pendientes(self):
        _make_order(self.address, self.user, 'payment_confirmed', 2025, 4, price=400, qty=2)
        _make_order(self.address, self.user, 'pending', 2025, 4, price=100, qty=3)
        resp = self.client.get('/revenue/summary/', {'year': 2025, 'month': 4})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(float(resp.data['recibidos']), 800.0)
        self.assertEqual(float(resp.data['pendientes']), 300.0)
        self.assertEqual(float(resp.data['total']), 1100.0)

    def test_summary_total_equals_sum(self):
        _make_order(self.address, self.user, 'delivered', 2025, 6, price=250, qty=1)
        resp = self.client.get('/revenue/summary/', {'year': 2025, 'month': 6})
        self.assertAlmostEqual(
            float(resp.data['total']),
            float(resp.data['recibidos']) + float(resp.data['pendientes'])
        )

    def test_summary_excludes_canceled(self):
        _make_order(self.address, self.user, 'canceled', 2025, 8, price=999, qty=1)
        resp = self.client.get('/revenue/summary/', {'year': 2025, 'month': 8})
        self.assertEqual(float(resp.data['total']), 0.0)

    def test_summary_empty_month_returns_zeros(self):
        resp = self.client.get('/revenue/summary/', {'year': 2099, 'month': 1})
        self.assertEqual(float(resp.data['recibidos']), 0.0)
        self.assertEqual(float(resp.data['pendientes']), 0.0)
        self.assertEqual(float(resp.data['total']), 0.0)
```

- [x] **Step 4: Correr tests para verificar que fallan** ✅ (2026-11-13)

```bash
docker exec microservice_enid_service python manage.py test revenue.tests.test_monthly revenue.tests.test_summary -v 2
```

Esperado: `ModuleNotFoundError: No module named 'revenue'` o similar (la app no existe aún en INSTALLED_APPS).

- [x] **Step 5: Registrar revenue en settings.py** ✅ (2026-11-13)

```python
# enid-store/enid/enid/settings.py — añadir en INSTALLED_APPS
'revenue',
```

- [x] **Step 6: Crear serializers.py** ✅ (2026-11-13)

```python
# enid-store/enid/revenue/serializers.py
from rest_framework import serializers


class MonthlyRevenueSerializer(serializers.Serializer):
    month = serializers.IntegerField()
    recibidos = serializers.DecimalField(max_digits=14, decimal_places=2)
    pendientes = serializers.DecimalField(max_digits=14, decimal_places=2)


class SummaryRevenueSerializer(serializers.Serializer):
    recibidos = serializers.DecimalField(max_digits=14, decimal_places=2)
    pendientes = serializers.DecimalField(max_digits=14, decimal_places=2)
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
```

- [x] **Step 7: Crear views.py con MonthlyRevenueView y SummaryRevenueView** ✅ (2026-11-13)

```python
# enid-store/enid/revenue/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.db.models import Sum, Q, DecimalField
from django.db.models.functions import ExtractMonth
from django.utils import timezone
from item_order.models import ItemOrder
from order.models import Order
from revenue.serializers import MonthlyRevenueSerializer, SummaryRevenueSerializer
from decimal import Decimal

RECIBIDOS = ['payment_confirmed', 'delivered', 'cash_on_delivery']
PENDIENTES = ['pending', 'preparing', 'ready_for_shipping', 'in_transit', 'ready_for_pickup']


def _order_amount(order_qs):
    """Sum price*quantity for each order. Returns dict {order_id: amount}."""
    return (
        ItemOrder.objects
        .filter(order__in=order_qs)
        .values('order_id')
        .annotate(amount=Sum('price' * 'quantity', output_field=DecimalField()))
    )


def _monthly_sums(year, group):
    return (
        ItemOrder.objects
        .filter(order__created_at__year=year, order__status__in=group)
        .annotate(month=ExtractMonth('order__created_at'))
        .values('month')
        .annotate(total=Sum('price' * 'quantity', output_field=DecimalField()))
    )


class MonthlyRevenueView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        year = int(request.query_params.get('year', timezone.now().year))
        recibidos_qs = _monthly_sums(year, RECIBIDOS)
        pendientes_qs = _monthly_sums(year, PENDIENTES)

        recibidos_map = {r['month']: r['total'] for r in recibidos_qs}
        pendientes_map = {r['month']: r['total'] for r in pendientes_qs}

        data = [
            {
                'month': m,
                'recibidos': recibidos_map.get(m, Decimal('0.00')),
                'pendientes': pendientes_map.get(m, Decimal('0.00')),
            }
            for m in range(1, 13)
        ]
        return Response(MonthlyRevenueSerializer(data, many=True).data)


class SummaryRevenueView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()
        year = int(request.query_params.get('year', now.year))
        month = int(request.query_params.get('month', now.month))

        def _sum(statuses):
            result = (
                ItemOrder.objects
                .filter(
                    order__created_at__year=year,
                    order__created_at__month=month,
                    order__status__in=statuses,
                )
                .aggregate(total=Sum('price' * 'quantity', output_field=DecimalField()))
            )
            return result['total'] or Decimal('0.00')

        recibidos = _sum(RECIBIDOS)
        pendientes = _sum(PENDIENTES)
        data = {'recibidos': recibidos, 'pendientes': pendientes, 'total': recibidos + pendientes}
        return Response(SummaryRevenueSerializer(data).data)
```

> **Nota sobre `price * 'quantity'`:** Django ORM no soporta directamente `price * 'quantity'` en un `Sum`. Usa `F()` expressions:
> ```python
> from django.db.models import F
> Sum(F('price') * F('quantity'), output_field=DecimalField())
> ```
> Aplica esta corrección en todos los lugares donde aparezca `Sum('price' * 'quantity', ...)`.

- [x] **Step 8: Crear urls.py** ✅ (2026-11-13)

```python
# enid-store/enid/revenue/urls.py
from django.urls import path
from revenue.views import MonthlyRevenueView, SummaryRevenueView

urlpatterns = [
    path('monthly/', MonthlyRevenueView.as_view(), name='revenue-monthly'),
    path('summary/', SummaryRevenueView.as_view(), name='revenue-summary'),
]
```

- [x] **Step 9: Registrar en enid/urls.py** ✅ (2026-11-13)

```python
# enid-store/enid/enid/urls.py — añadir en urlpatterns
path('revenue/', include('revenue.urls')),
```

- [x] **Step 10: Correr tests para verificar que pasan** ✅ (2026-11-13) — 19/19 PASS

```bash
docker exec microservice_enid_service python manage.py test revenue.tests.test_monthly revenue.tests.test_summary -v 2
```

Esperado: todos PASS.

- [x] **Step 11: Commit** ✅ (2026-11-13)

```bash
git add enid-store/enid/revenue/ enid-store/enid/enid/settings.py enid-store/enid/enid/urls.py
git commit -m "#0: Task 1 - revenue app + monthly y summary endpoints (TDD)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Backend — endpoints comparison y by-product

**Files:**
- Modify: `enid-store/enid/revenue/views.py` → añadir `ComparisonRevenueView` y `ByProductRevenueView`
- Modify: `enid-store/enid/revenue/serializers.py` → añadir `ComparisonSerializer` y `ByProductSerializer`
- Modify: `enid-store/enid/revenue/urls.py` → añadir 2 rutas
- Create: `enid-store/enid/revenue/tests/test_comparison.py`
- Create: `enid-store/enid/revenue/tests/test_by_product.py`

**Interfaces:**
- Consumes: helpers `_monthly_sums`, `RECIBIDOS`, `PENDIENTES` de Task 1
- Produces: `GET /enid/revenue/comparison/?year=YYYY` → `[{"month": int, "current": float|null, "previous": float|null}]` (12 items)
- Produces: `GET /enid/revenue/by-product/?year=YYYY&month=MM` → `[{"id": int, "name": str, "image": str|null, "amount": float, "pct": float}]`

- [x] **Step 1: Escribir tests que fallan — test_comparison.py** ✅ (2026-11-13)

```python
# enid-store/enid/revenue/tests/test_comparison.py
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import User
from revenue.tests.test_monthly import _make_address, _make_user, _make_order


class ComparisonRevenueTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser('admin@t.com', 'admin@t.com', 'pass')
        self.client.force_authenticate(user=self.admin)
        self.address = _make_address()
        self.user = _make_user()

    def test_returns_12_months(self):
        resp = self.client.get('/revenue/comparison/', {'year': 2025})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 12)

    def test_current_year_data_correct(self):
        _make_order(self.address, self.user, 'payment_confirmed', 2025, 3, price=1000, qty=1)
        resp = self.client.get('/revenue/comparison/', {'year': 2025})
        march = next(d for d in resp.data if d['month'] == 3)
        self.assertEqual(float(march['current']), 1000.0)

    def test_previous_year_data_correct(self):
        _make_order(self.address, self.user, 'delivered', 2024, 3, price=500, qty=2)
        resp = self.client.get('/revenue/comparison/', {'year': 2025})
        march = next(d for d in resp.data if d['month'] == 3)
        self.assertEqual(float(march['previous']), 1000.0)

    def test_future_months_current_year_are_null(self):
        """Meses futuros del año actual devuelven null para current."""
        import datetime
        from django.utils import timezone
        current_month = timezone.now().month
        current_year = timezone.now().year
        resp = self.client.get('/revenue/comparison/', {'year': current_year})
        for d in resp.data:
            if d['month'] > current_month:
                self.assertIsNone(d['current'], f"month {d['month']} should be null")
```

- [x] **Step 2: Escribir tests que fallan — test_by_product.py** ✅ (2026-11-13)

```python
# enid-store/enid/revenue/tests/test_by_product.py
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import User
from order.models import Order
from item_order.models import ItemOrder
from products.models import Product
from categories.models import Category
from revenue.tests.test_monthly import _make_address, _make_user, _make_order
from datetime import datetime
import pytz


def _make_order_with_products(address, user, status_val, year, month, items):
    """
    items = [(product, price, qty), ...]
    """
    from order.models import Order
    from item_order.models import ItemOrder
    dt = datetime(year, month, 15, 12, 0, 0, tzinfo=pytz.UTC)
    order = Order.objects.create(shipping_address=address, user=user, status=status_val)
    Order.objects.filter(pk=order.pk).update(created_at=dt)
    for product, price, qty in items:
        ItemOrder.objects.create(order=order, product=product, quantity=qty, price=price)
    return order


class ByProductRevenueTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser('admin@t.com', 'admin@t.com', 'pass')
        self.client.force_authenticate(user=self.admin)
        self.address = _make_address()
        self.user = _make_user()
        cat, _ = Category.objects.get_or_create(name='Cat')
        self.prod_a = Product.objects.create(name='Kit Pesas', price=100, description='d', category=cat, stock=5)
        self.prod_b = Product.objects.create(name='Carpa 3x3', price=100, description='d', category=cat, stock=5)

    def test_ordered_by_amount_desc(self):
        _make_order_with_products(
            self.address, self.user, 'payment_confirmed', 2025, 6,
            [(self.prod_a, 100, 3), (self.prod_b, 100, 1)]
        )
        resp = self.client.get('/revenue/by-product/', {'year': 2025, 'month': 6})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        amounts = [d['amount'] for d in resp.data]
        self.assertEqual(amounts, sorted(amounts, reverse=True))

    def test_pct_sums_to_100(self):
        _make_order_with_products(
            self.address, self.user, 'payment_confirmed', 2025, 6,
            [(self.prod_a, 100, 3), (self.prod_b, 100, 1)]
        )
        resp = self.client.get('/revenue/by-product/', {'year': 2025, 'month': 6})
        total_pct = sum(d['pct'] for d in resp.data)
        self.assertAlmostEqual(total_pct, 100.0, places=0)

    def test_amount_calculation(self):
        _make_order_with_products(
            self.address, self.user, 'delivered', 2025, 7,
            [(self.prod_a, 500, 2)]
        )
        resp = self.client.get('/revenue/by-product/', {'year': 2025, 'month': 7})
        self.assertEqual(float(resp.data[0]['amount']), 1000.0)

    def test_image_field_present(self):
        _make_order_with_products(
            self.address, self.user, 'payment_confirmed', 2025, 8,
            [(self.prod_a, 100, 1)]
        )
        resp = self.client.get('/revenue/by-product/', {'year': 2025, 'month': 8})
        self.assertIn('image', resp.data[0])
```

- [x] **Step 3: Correr tests para verificar que fallan** ✅ (2026-11-13)

```bash
docker exec microservice_enid_service python manage.py test revenue.tests.test_comparison revenue.tests.test_by_product -v 2
```

Esperado: `AttributeError` o `404` (views no existen aún).

- [x] **Step 4: Añadir serializers para comparison y by-product** ✅ (2026-11-13)

```python
# Añadir al final de enid-store/enid/revenue/serializers.py

class ComparisonSerializer(serializers.Serializer):
    month = serializers.IntegerField()
    current = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    previous = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)


class ByProductSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    image = serializers.CharField(allow_null=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    pct = serializers.FloatField()
```

- [x] **Step 5: Implementar ComparisonRevenueView y ByProductRevenueView en views.py** ✅ (2026-11-13)

```python
# Añadir imports al inicio de views.py
from django.utils import timezone
from revenue.serializers import (
    MonthlyRevenueSerializer, SummaryRevenueSerializer,
    ComparisonSerializer, ByProductSerializer
)
from products.models import Product
```

```python
# Añadir al final de views.py

def _year_total_by_month(year, statuses):
    """Returns {month: total} for given year and statuses (recibidos+pendientes combined)."""
    qs = (
        ItemOrder.objects
        .filter(order__created_at__year=year, order__status__in=statuses)
        .annotate(month=ExtractMonth('order__created_at'))
        .values('month')
        .annotate(total=Sum(F('price') * F('quantity'), output_field=DecimalField()))
    )
    return {r['month']: r['total'] for r in qs}


ALL_COUNTED = RECIBIDOS + PENDIENTES


class ComparisonRevenueView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()
        year = int(request.query_params.get('year', now.year))
        current_map = _year_total_by_month(year, ALL_COUNTED)
        previous_map = _year_total_by_month(year - 1, ALL_COUNTED)
        current_month = now.month if year == now.year else 12

        data = []
        for m in range(1, 13):
            current_val = current_map.get(m, Decimal('0.00')) if m <= current_month else None
            previous_val = previous_map.get(m, Decimal('0.00'))
            data.append({'month': m, 'current': current_val, 'previous': previous_val})
        return Response(ComparisonSerializer(data, many=True).data)


class ByProductRevenueView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()
        year = int(request.query_params.get('year', now.year))
        month = int(request.query_params.get('month', now.month))
        is_current_month = (year == now.year and month == now.month)
        statuses = ALL_COUNTED if is_current_month else RECIBIDOS + PENDIENTES

        rows = (
            ItemOrder.objects
            .filter(
                order__created_at__year=year,
                order__created_at__month=month,
                order__status__in=statuses,
            )
            .values('product_id')
            .annotate(amount=Sum(F('price') * F('quantity'), output_field=DecimalField()))
            .order_by('-amount')
        )

        total = sum(r['amount'] for r in rows) or Decimal('1')
        product_ids = [r['product_id'] for r in rows]
        products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

        data = []
        for r in rows:
            p = products.get(r['product_id'])
            image_url = None
            if p and hasattr(p, 'image') and p.image:
                image_url = str(p.image)
            data.append({
                'id': r['product_id'],
                'name': p.name if p else '',
                'image': image_url,
                'amount': r['amount'],
                'pct': round(float(r['amount'] / total * 100), 1),
            })
        return Response(ByProductSerializer(data, many=True).data)
```

> **Nota sobre Product.image:** Verifica el nombre real del campo de imagen en `products/models.py`. Puede ser `image`, `photo`, `picture`, u otro. Ajusta `p.image` al nombre real del campo.

- [x] **Step 6: Añadir rutas en urls.py** ✅ (2026-11-13)

```python
# enid-store/enid/revenue/urls.py — reemplazar contenido completo
from django.urls import path
from revenue.views import (
    MonthlyRevenueView, SummaryRevenueView,
    ComparisonRevenueView, ByProductRevenueView,
)

urlpatterns = [
    path('monthly/', MonthlyRevenueView.as_view(), name='revenue-monthly'),
    path('summary/', SummaryRevenueView.as_view(), name='revenue-summary'),
    path('comparison/', ComparisonRevenueView.as_view(), name='revenue-comparison'),
    path('by-product/', ByProductRevenueView.as_view(), name='revenue-by-product'),
]
```

- [x] **Step 7: Correr todos los tests de revenue** ✅ (2026-11-13) — 19/19 PASS

```bash
docker exec microservice_enid_service python manage.py test revenue -v 2
```

Esperado: todos PASS.

- [x] **Step 8: Commit** ✅ (2026-11-13)

```bash
git add enid-store/enid/revenue/
git commit -m "#0: Task 2 - revenue comparison y by-product endpoints (TDD)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Frontend — setup chart.js + router + EarningsDashboard layout

**Files:**
- Modify: `service-store/package.json` → añadir `chart.js` y `vue-chartjs`
- Create: `service-store/src/views/Earnings/EarningsDashboard.vue`
- Create: `service-store/src/views/Earnings/Rendimiento.vue` (stub)
- Create: `service-store/src/views/Earnings/CobrosPendientes.vue` (stub)
- Create: `service-store/src/views/Earnings/CobrosRecibidos.vue` (stub)
- Modify: `service-store/src/router/index.js` → añadir `/ingresos`

**Interfaces:**
- Produces: ruta `/ingresos` protegida → renderiza `EarningsDashboard.vue` con sub-rutas

- [x] **Step 1: Instalar chart.js y vue-chartjs** ✅ (2026-11-13)

```bash
docker exec service-store_service npm install chart.js@^4 vue-chartjs@^5
```

Si el contenedor se llama diferente, verifica con `docker ps | grep store`.

- [x] **Step 2: Crear directorios** ✅ (2026-11-13)

```bash
mkdir -p service-store/src/views/Earnings
mkdir -p service-store/src/components/Earnings
```

- [x] **Step 3: Crear EarningsDashboard.vue** ✅ (2026-11-13)

```vue
<!-- service-store/src/views/Earnings/EarningsDashboard.vue -->
<template>
  <div class="flex h-full">
    <aside class="w-56 border-r border-gray-200 p-6 flex-shrink-0">
      <h2 class="text-xl font-semibold text-gray-800 mb-6">Ingresos</h2>
      <nav class="space-y-1">
        <router-link
          v-for="tab in tabs"
          :key="tab.to"
          :to="tab.to"
          class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-100 transition-colors"
          active-class="bg-pink-50 text-pink-700 font-medium"
        >
          <span>{{ tab.label }}</span>
        </router-link>
      </nav>
    </aside>
    <main class="flex-1 overflow-y-auto p-8">
      <router-view />
    </main>
  </div>
</template>

<script setup>
const tabs = [
  { to: '/ingresos/rendimiento', label: 'Rendimiento' },
  { to: '/ingresos/pendientes', label: 'Cobros pendientes' },
  { to: '/ingresos/recibidos', label: 'Cobros recibidos' },
]
</script>
```

- [x] **Step 4: Crear stubs de las 3 sub-vistas** ✅ (2026-11-13)

```vue
<!-- service-store/src/views/Earnings/Rendimiento.vue -->
<template>
  <div>
    <h3 class="text-lg font-semibold text-gray-800 mb-4">Rendimiento</h3>
    <!-- TODO: implementado en Task 4 -->
  </div>
</template>
<script setup></script>
```

```vue
<!-- service-store/src/views/Earnings/CobrosPendientes.vue -->
<template>
  <div>
    <h3 class="text-lg font-semibold text-gray-800 mb-4">Cobros pendientes</h3>
    <!-- TODO: implementado en Task 5 -->
  </div>
</template>
<script setup></script>
```

```vue
<!-- service-store/src/views/Earnings/CobrosRecibidos.vue -->
<template>
  <div>
    <h3 class="text-lg font-semibold text-gray-800 mb-4">Cobros recibidos</h3>
    <!-- TODO: implementado en Task 5 -->
  </div>
</template>
<script setup></script>
```

- [x] **Step 5: Añadir rutas en router/index.js** ✅ (2026-11-13)

Busca el archivo en `service-store/src/router/index.js`. Añade dentro del array de rutas (respeta el guard de auth existente — copia el patrón `meta: { requiresAuth: true }` de otras rutas admin):

```javascript
{
  path: '/ingresos',
  component: () => import('@/views/Earnings/EarningsDashboard.vue'),
  meta: { requiresAuth: true },
  redirect: '/ingresos/rendimiento',
  children: [
    {
      path: 'rendimiento',
      component: () => import('@/views/Earnings/Rendimiento.vue'),
    },
    {
      path: 'pendientes',
      component: () => import('@/views/Earnings/CobrosPendientes.vue'),
    },
    {
      path: 'recibidos',
      component: () => import('@/views/Earnings/CobrosRecibidos.vue'),
    },
  ],
},
```

> **Nota:** El guard de auth en este proyecto puede usar `meta.requiresAuth` o puede ser un guard de Vuex/store. Revisa cómo están protegidas otras rutas admin (ej. la ruta de OrderDetail) y replica exactamente ese patrón.

- [x] **Step 6: Verificar navegación en browser** ✅ (2026-11-13) — sin errores de compilación, guard redirige correctamente

```bash
# El frontend ya debe estar corriendo con docker compose up
# Navegar a http://localhost/ingresos o http://localhost:5173/ingresos
# Verificar que se ve el sidebar con los 3 tabs y el contenido stub
```

- [x] **Step 7: Commit** ✅ (2026-11-13)

```bash
git add service-store/src/views/Earnings/ service-store/src/router/ service-store/package.json service-store/package-lock.json
git commit -m "#0: Task 3 - earnings dashboard layout + router (chart.js instalado)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Frontend — Rendimiento.vue: BarChart + MonthSummaryCard

**Files:**
- Create: `service-store/src/components/Earnings/BarChart.vue`
- Create: `service-store/src/components/Earnings/MonthSummaryCard.vue`
- Modify: `service-store/src/views/Earnings/Rendimiento.vue` → conectar BarChart + MonthSummaryCard

**Interfaces:**
- Consumes: `GET /enid/revenue/monthly/?year=YYYY` (Task 1)
- Consumes: `GET /enid/revenue/summary/?year=YYYY&month=MM` (Task 1)
- Produces: estado local `selectedYear` y `selectedMonth` que comparten las secciones

- [ ] **Step 1: Crear BarChart.vue**

```vue
<!-- service-store/src/components/Earnings/BarChart.vue -->
<template>
  <Bar :data="chartData" :options="chartOptions" />
</template>

<script setup>
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement,
  Title, Tooltip, Legend,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

const MONTH_LABELS = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

const props = defineProps({
  monthlyData: { type: Array, required: true },  // [{month, recibidos, pendientes}]
})
const emit = defineEmits(['month-click'])

const chartData = computed(() => ({
  labels: MONTH_LABELS,
  datasets: [
    {
      label: 'Recibidos',
      data: props.monthlyData.map(d => parseFloat(d.recibidos)),
      backgroundColor: '#E91E8C',
    },
    {
      label: 'Pendientes',
      data: props.monthlyData.map(d => parseFloat(d.pendientes)),
      backgroundColor: '#F9A8D4',
    },
  ],
}))

const chartOptions = {
  responsive: true,
  onClick: (_, elements) => {
    if (elements.length > 0) {
      emit('month-click', elements[0].index + 1)
    }
  },
  plugins: {
    legend: { position: 'top' },
    tooltip: {
      callbacks: {
        label: (ctx) => `$${ctx.parsed.y.toLocaleString('es-MX', { minimumFractionDigits: 2 })} MXN`,
      },
    },
  },
  scales: {
    y: {
      ticks: {
        callback: (val) => `$${val.toLocaleString('es-MX')}`,
      },
    },
  },
}
</script>
```

- [ ] **Step 2: Crear MonthSummaryCard.vue**

```vue
<!-- service-store/src/components/Earnings/MonthSummaryCard.vue -->
<template>
  <div class="rounded-2xl border border-gray-200 p-6 bg-white">
    <h4 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
      Resumen — {{ monthLabel }} {{ year }}
    </h4>
    <div class="grid grid-cols-3 gap-4 mb-4">
      <div>
        <p class="text-xs text-gray-400">Cobros recibidos</p>
        <p class="text-lg font-bold text-gray-800">{{ fmt(summary.recibidos) }}</p>
      </div>
      <div>
        <p class="text-xs text-gray-400">Cobros pendientes</p>
        <p class="text-lg font-bold text-gray-800">{{ fmt(summary.pendientes) }}</p>
      </div>
      <div>
        <p class="text-xs text-gray-400">Total</p>
        <p class="text-lg font-bold text-pink-700">{{ fmt(summary.total) }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
const MONTH_NAMES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

const props = defineProps({
  summary: { type: Object, required: true },  // {recibidos, pendientes, total}
  year: { type: Number, required: true },
  month: { type: Number, required: true },
})

const monthLabel = computed(() => MONTH_NAMES[props.month - 1])

function fmt(val) {
  return `$${parseFloat(val).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} MXN`
}
</script>

<script>
import { computed } from 'vue'
export default {}
</script>
```

> **Nota:** `MonthSummaryCard.vue` usa tanto `<script setup>` como `<script>`. Consolídalo usando sólo `<script setup>`:
> ```vue
> <script setup>
> import { computed } from 'vue'
> // ... resto del código
> </script>
> ```

- [ ] **Step 3: Implementar Rendimiento.vue con BarChart + MonthSummaryCard**

```vue
<!-- service-store/src/views/Earnings/Rendimiento.vue -->
<template>
  <div class="space-y-8">
    <div class="flex items-center justify-between">
      <h3 class="text-lg font-semibold text-gray-800">Rendimiento</h3>
      <select
        v-model="selectedYear"
        class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
      >
        <option v-for="y in availableYears" :key="y" :value="y">{{ y }}</option>
      </select>
    </div>

    <div v-if="loadingMonthly" class="h-64 flex items-center justify-center text-gray-400">
      Cargando gráfica...
    </div>
    <BarChart
      v-else
      :monthly-data="monthlyData"
      @month-click="selectedMonth = $event"
    />

    <MonthSummaryCard
      v-if="summary"
      :summary="summary"
      :year="selectedYear"
      :month="selectedMonth"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import axios from 'axios'
import BarChart from '@/components/Earnings/BarChart.vue'
import MonthSummaryCard from '@/components/Earnings/MonthSummaryCard.vue'

const currentYear = new Date().getFullYear()
const selectedYear = ref(currentYear)
const selectedMonth = ref(new Date().getMonth() + 1)
const monthlyData = ref([])
const summary = ref(null)
const loadingMonthly = ref(false)

const availableYears = computed(() => {
  const years = []
  for (let y = currentYear; y >= currentYear - 3; y--) years.push(y)
  return years
})

async function fetchMonthly() {
  loadingMonthly.value = true
  try {
    const { data } = await axios.get('/enid/revenue/monthly/', {
      params: { year: selectedYear.value }
    })
    monthlyData.value = data
  } finally {
    loadingMonthly.value = false
  }
}

async function fetchSummary() {
  const { data } = await axios.get('/enid/revenue/summary/', {
    params: { year: selectedYear.value, month: selectedMonth.value }
  })
  summary.value = data
}

watch(selectedYear, () => { fetchMonthly(); fetchSummary() })
watch(selectedMonth, fetchSummary)
onMounted(() => { fetchMonthly(); fetchSummary() })
</script>
```

- [ ] **Step 4: Verificar en browser**

```
http://localhost/ingresos/rendimiento
```

Verificar:
- Selector de año visible
- Gráfica de barras renderiza (puede estar vacía si no hay datos)
- Card de resumen visible
- Click en barra → card actualiza mes

- [ ] **Step 5: Commit**

```bash
git add service-store/src/components/Earnings/BarChart.vue service-store/src/components/Earnings/MonthSummaryCard.vue service-store/src/views/Earnings/Rendimiento.vue
git commit -m "#0: Task 4 - BarChart + MonthSummaryCard en Rendimiento.vue

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Frontend — Rendimiento.vue: LineChart + ProductIncomeList

**Files:**
- Create: `service-store/src/components/Earnings/LineChart.vue`
- Create: `service-store/src/components/Earnings/ProductIncomeList.vue`
- Modify: `service-store/src/views/Earnings/Rendimiento.vue` → añadir LineChart y ProductIncomeList

**Interfaces:**
- Consumes: `GET /enid/revenue/comparison/?year=YYYY` (Task 2)
- Consumes: `GET /enid/revenue/by-product/?year=YYYY&month=MM` (Task 2)

- [ ] **Step 1: Crear LineChart.vue**

```vue
<!-- service-store/src/components/Earnings/LineChart.vue -->
<template>
  <div>
    <div class="flex items-center justify-between mb-3">
      <h4 class="text-sm font-semibold text-gray-600">Comparación año a año</h4>
      <label class="flex items-center gap-2 text-sm text-gray-500 cursor-pointer">
        <input type="checkbox" v-model="showFuture" class="rounded" />
        Mostrar ingresos futuros
      </label>
    </div>
    <Line :data="chartData" :options="chartOptions" />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, Title, Tooltip, Legend,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

const MONTH_LABELS = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

const props = defineProps({
  comparisonData: { type: Array, required: true },  // [{month, current, previous}]
  year: { type: Number, required: true },
})

const showFuture = ref(false)

const currentData = computed(() =>
  props.comparisonData.map(d => {
    if (d.current === null && !showFuture.value) return null
    return d.current === null ? undefined : parseFloat(d.current)
  })
)

const previousData = computed(() =>
  props.comparisonData.map(d =>
    d.previous !== null ? parseFloat(d.previous) : null
  )
)

const chartData = computed(() => ({
  labels: MONTH_LABELS,
  datasets: [
    {
      label: `${props.year}`,
      data: currentData.value,
      borderColor: '#E91E8C',
      backgroundColor: 'rgba(233,30,140,0.1)',
      tension: 0.3,
      spanGaps: false,
    },
    {
      label: `${props.year - 1}`,
      data: previousData.value,
      borderColor: '#7C3AED',
      backgroundColor: 'rgba(124,58,237,0.1)',
      tension: 0.3,
      spanGaps: false,
    },
  ],
}))

const chartOptions = {
  responsive: true,
  plugins: {
    legend: { position: 'top' },
    tooltip: {
      callbacks: {
        label: (ctx) => ctx.parsed.y !== null
          ? `$${ctx.parsed.y.toLocaleString('es-MX', { minimumFractionDigits: 2 })} MXN`
          : 'Sin datos',
      },
    },
  },
}
</script>
```

- [ ] **Step 2: Crear ProductIncomeList.vue**

```vue
<!-- service-store/src/components/Earnings/ProductIncomeList.vue -->
<template>
  <div>
    <h4 class="text-sm font-semibold text-gray-600 mb-3">Ingresos por producto</h4>
    <ul class="space-y-3">
      <li
        v-for="item in products"
        :key="item.id"
        class="flex items-center gap-3"
      >
        <img
          :src="item.image || '/placeholder-product.png'"
          :alt="item.name"
          class="w-10 h-10 rounded-lg object-cover flex-shrink-0 bg-gray-100"
        />
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-gray-800 truncate">{{ item.name }}</p>
          <div class="flex items-center gap-2 mt-1">
            <div class="flex-1 bg-gray-100 rounded-full h-1.5">
              <div
                class="bg-pink-500 h-1.5 rounded-full"
                :style="{ width: `${item.pct}%` }"
              />
            </div>
            <span class="text-xs text-gray-400 flex-shrink-0">{{ item.pct }}%</span>
          </div>
        </div>
        <p class="text-sm font-semibold text-gray-800 flex-shrink-0">
          ${{ parseFloat(item.amount).toLocaleString('es-MX', { minimumFractionDigits: 2 }) }}
        </p>
      </li>
      <li v-if="products.length === 0" class="text-sm text-gray-400 py-4 text-center">
        Sin productos este mes
      </li>
    </ul>
  </div>
</template>

<script setup>
defineProps({
  products: { type: Array, required: true },  // [{id, name, image, amount, pct}]
})
</script>
```

- [ ] **Step 3: Integrar LineChart y ProductIncomeList en Rendimiento.vue**

Añade en el `<template>` de `Rendimiento.vue` (después de `MonthSummaryCard`):

```vue
<LineChart
  v-if="comparisonData.length"
  :comparison-data="comparisonData"
  :year="selectedYear"
/>

<ProductIncomeList :products="byProduct" />
```

Añade imports en `<script setup>`:
```javascript
import LineChart from '@/components/Earnings/LineChart.vue'
import ProductIncomeList from '@/components/Earnings/ProductIncomeList.vue'

const comparisonData = ref([])
const byProduct = ref([])

async function fetchComparison() {
  const { data } = await axios.get('/enid/revenue/comparison/', {
    params: { year: selectedYear.value }
  })
  comparisonData.value = data
}

async function fetchByProduct() {
  const { data } = await axios.get('/enid/revenue/by-product/', {
    params: { year: selectedYear.value, month: selectedMonth.value }
  })
  byProduct.value = data
}
```

Actualiza `watch` y `onMounted`:
```javascript
watch(selectedYear, () => { fetchMonthly(); fetchSummary(); fetchComparison(); fetchByProduct() })
watch(selectedMonth, () => { fetchSummary(); fetchByProduct() })
onMounted(() => { fetchMonthly(); fetchSummary(); fetchComparison(); fetchByProduct() })
```

- [ ] **Step 4: Verificar en browser**

```
http://localhost/ingresos/rendimiento
```

Verificar:
- Gráfica de líneas YoY visible
- Toggle "Mostrar ingresos futuros" oculta/muestra puntos futuros
- Lista de productos visible (vacía si no hay datos, con placeholder)

- [ ] **Step 5: Commit**

```bash
git add service-store/src/components/Earnings/LineChart.vue service-store/src/components/Earnings/ProductIncomeList.vue service-store/src/views/Earnings/Rendimiento.vue
git commit -m "#0: Task 5 - LineChart YoY + ProductIncomeList en Rendimiento.vue

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Frontend — CobrosPendientes + CobrosRecibidos

**Files:**
- Modify: `service-store/src/views/Earnings/CobrosPendientes.vue`
- Modify: `service-store/src/views/Earnings/CobrosRecibidos.vue`

**Interfaces:**
- Consumes: `GET /enid/order-search/?status=<status>` — endpoint existente, reutiliza `OrderSearchSerializer`
- Produces: tablas de órdenes con columnas ID · Fecha · Cliente · Total · Status · Acciones

- [ ] **Step 1: Verificar el endpoint existente de order-search**

```bash
# En browser o curl, verificar que el endpoint responde:
curl -s "http://localhost:8000/order-search/?status=pending" | head -c 500
```

Verificar los campos disponibles en la respuesta. Los campos que necesitamos son: `id`, `created_at`, `user` (nombre), `items` (para calcular total), `status`.

- [ ] **Step 2: Implementar CobrosPendientes.vue**

```vue
<!-- service-store/src/views/Earnings/CobrosPendientes.vue -->
<template>
  <div>
    <h3 class="text-lg font-semibold text-gray-800 mb-6">Cobros pendientes</h3>

    <div v-if="loading" class="text-gray-400 py-8 text-center">Cargando...</div>
    <div v-else-if="orders.length === 0" class="text-gray-400 py-8 text-center">
      No hay cobros pendientes
    </div>
    <table v-else class="w-full text-sm border-collapse">
      <thead>
        <tr class="border-b border-gray-200">
          <th class="text-left py-2 px-3 text-gray-500 font-medium">#</th>
          <th class="text-left py-2 px-3 text-gray-500 font-medium">Fecha</th>
          <th class="text-left py-2 px-3 text-gray-500 font-medium">Cliente</th>
          <th class="text-right py-2 px-3 text-gray-500 font-medium">Total</th>
          <th class="text-left py-2 px-3 text-gray-500 font-medium">Status</th>
          <th class="py-2 px-3"></th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="order in orders"
          :key="order.id"
          class="border-b border-gray-100 hover:bg-gray-50"
        >
          <td class="py-2 px-3 text-gray-700 font-mono">#{{ order.id }}</td>
          <td class="py-2 px-3 text-gray-600">{{ fmtDate(order.created_at) }}</td>
          <td class="py-2 px-3 text-gray-700">{{ order.user?.username || '—' }}</td>
          <td class="py-2 px-3 text-right font-semibold text-gray-800">{{ fmtTotal(order.items) }}</td>
          <td class="py-2 px-3">
            <span class="inline-block bg-yellow-100 text-yellow-800 text-xs px-2 py-0.5 rounded-full">
              {{ order.status }}
            </span>
          </td>
          <td class="py-2 px-3 text-right">
            <router-link
              :to="`/orden/${order.id}`"
              class="text-pink-600 hover:text-pink-700 text-xs font-medium"
            >
              Ver →
            </router-link>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const PENDING_STATUSES = ['pending', 'preparing', 'ready_for_shipping', 'in_transit', 'ready_for_pickup']

const orders = ref([])
const loading = ref(false)

async function fetchOrders() {
  loading.value = true
  try {
    const all = await Promise.all(
      PENDING_STATUSES.map(s =>
        axios.get('/enid/order-search/', { params: { status: s } }).then(r => r.data)
      )
    )
    orders.value = all.flat().sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  } finally {
    loading.value = false
  }
}

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' })
}

function fmtTotal(items = []) {
  const total = items.reduce((s, i) => s + parseFloat(i.price) * i.quantity, 0)
  return `$${total.toLocaleString('es-MX', { minimumFractionDigits: 2 })} MXN`
}

onMounted(fetchOrders)
</script>
```

- [ ] **Step 3: Implementar CobrosRecibidos.vue**

Igual que `CobrosPendientes.vue` pero con estos cambios:
- `const RECEIVED_STATUSES = ['payment_confirmed', 'delivered', 'cash_on_delivery']`
- Título: "Cobros recibidos"
- Badge verde: `bg-green-100 text-green-800`
- El resto del template es idéntico — copia y ajusta

```vue
<!-- service-store/src/views/Earnings/CobrosRecibidos.vue -->
<template>
  <div>
    <h3 class="text-lg font-semibold text-gray-800 mb-6">Cobros recibidos</h3>
    <!-- Mismo template que CobrosPendientes.vue — reemplaza el badge:
         bg-green-100 text-green-800 -->
    <!-- Copiar tabla completa de CobrosPendientes.vue y ajustar el badge -->
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const RECEIVED_STATUSES = ['payment_confirmed', 'delivered', 'cash_on_delivery']

const orders = ref([])
const loading = ref(false)

async function fetchOrders() {
  loading.value = true
  try {
    const all = await Promise.all(
      RECEIVED_STATUSES.map(s =>
        axios.get('/enid/order-search/', { params: { status: s } }).then(r => r.data)
      )
    )
    orders.value = all.flat().sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  } finally {
    loading.value = false
  }
}

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' })
}

function fmtTotal(items = []) {
  const total = items.reduce((s, i) => s + parseFloat(i.price) * i.quantity, 0)
  return `$${total.toLocaleString('es-MX', { minimumFractionDigits: 2 })} MXN`
}

onMounted(fetchOrders)
</script>
```

> **Nota sobre la ruta del detalle de orden:** Verifica la ruta exacta del router para ver el detalle de una orden en este proyecto. Puede ser `/orden/:id`, `/orders/:id`, u otra. Ajusta el `:to` del `router-link` al path correcto.

- [ ] **Step 4: Verificar en browser**

```
http://localhost/ingresos/pendientes
http://localhost/ingresos/recibidos
```

Verificar:
- Tablas renderizan sin errores en consola
- Datos reales aparecen si existen órdenes
- Link "Ver →" navega al detalle correcto

- [ ] **Step 5: Commit**

```bash
git add service-store/src/views/Earnings/CobrosPendientes.vue service-store/src/views/Earnings/CobrosRecibidos.vue
git commit -m "#0: Task 6 - CobrosPendientes + CobrosRecibidos (tablas de órdenes)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

**Progreso:** 3/6 Tasks (50%) — ⏸️ SIGUIENTE: Task 4 Step 1 (crear BarChart.vue en service-store/src/components/Earnings/)
