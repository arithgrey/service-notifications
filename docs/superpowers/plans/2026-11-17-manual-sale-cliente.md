# Venta Manual con Datos de Cliente — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extender la venta manual para asociar cliente (existente o nuevo) y dirección de envío opcional a cada `Order`.

**Architecture:** Se añade un `@action clientes` a `ProductVuewSet` para búsqueda de usuarios, y se extiende `manual_sale` para resolver `Order.user` y `Order.shipping_address` a partir de los campos opcionales del payload. El frontend agrega búsqueda con autocomplete, campos de email/nombre y un sub-form de dirección colapsable.

**Tech Stack:** Django 4 + DRF (backend), Vue 2 + Axios (frontend), Postgres real via contenedor, Jest (frontend unit tests).

**Spec:** `docs/superpowers/specs/2026-11-17-manual-sale-cliente-design.md`

## Global Constraints

- Sin mocks — tests de integración con Postgres real del contenedor `enid_store_service`.
- TDD estricto — el test DEBE fallar antes de implementar.
- Sin hardcode — estados se cargan desde `enid/estado`, no array estático.
- Imports absolutos: `from products.services import ...`, `@/components/...`.
- Rutas Django sin `/enid/` — el prefijo lo agrega nginx.
- Sin PII en logs — solo ids/pks.
- Rama única `develop` en ambos repos (`enid-store` y `service-store`).
- Todos los comandos corren dentro de contenedores — NUNCA en el host.
- Backend container: `enid_store_service` (working dir: `/app`)
- Frontend container: `service-store-frontend-1` (working dir: `/app`)

---

### Task 1: GET /productos/clientes/ — Búsqueda de clientes

**Repo:** `enid-store/enid/`

**Files:**
- Create: `products/tests/test_client_search.py`
- Modify: `products/views.py` (añadir `@action clientes` a `ProductVuewSet`)

**Interfaces:**
- Produces: `GET /productos/clientes/?q=<str>` → `200 [{id, email, name, last_address|null}]` o `400 {error}` si `q` vacío.

---

- [ ] **Step 1: Escribir el test que debe fallar**

Crear `products/tests/test_client_search.py` con este contenido exacto:

```python
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from order.models import Order
from address.models import Address
from state.models import State

User = get_user_model()

URL = '/productos/clientes/'


def _make_state():
    return State.objects.first()


def _make_address(state):
    return Address.objects.create(
        street='Av. Hidalgo',
        number=10,
        interior_number=1,
        colony='Centro',
        delegation_or_municipality='Cuauhtémoc',
        city='CDMX',
        postal_code='06600',
        phone_number='5512345678',
        state=state,
    )


class ClientSearchTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser('admin@t.com', 'admin@t.com', 'pass')

    def test_search_by_email_returns_client_with_last_address(self):
        state = _make_state()
        addr = _make_address(state)
        user = User.objects.create_user('ana@ejemplo.com', 'ana@ejemplo.com', 'pass',
                                        first_name='Ana', last_name='García')
        Order.objects.create(status='delivered', source='admin_manual', shipping_address=addr, user=user)

        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(URL, {'q': 'ana@ejemplo.com'})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['id'], user.id)
        self.assertEqual(resp.data[0]['email'], 'ana@ejemplo.com')
        self.assertEqual(resp.data[0]['name'], 'Ana García')
        self.assertEqual(resp.data[0]['last_address']['street'], 'Av. Hidalgo')
        self.assertEqual(resp.data[0]['last_address']['postal_code'], '06600')

    def test_search_by_partial_name_returns_matches(self):
        User.objects.create_user('luis@t.com', 'luis@t.com', 'pass',
                                 first_name='Luis', last_name='Pérez')
        User.objects.create_user('otro@t.com', 'otro@t.com', 'pass',
                                 first_name='Carlos', last_name='Ramírez')

        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(URL, {'q': 'Luis'})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [r['name'] for r in resp.data]
        self.assertIn('Luis Pérez', names)
        self.assertNotIn('Carlos Ramírez', names)

    def test_empty_query_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(URL, {'q': ''})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_query_param_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_results_returns_empty_list(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(URL, {'q': 'zzznoresult'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

    def test_user_without_orders_has_null_last_address(self):
        User.objects.create_user('solo@t.com', 'solo@t.com', 'pass',
                                 first_name='Solo', last_name='User')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(URL, {'q': 'solo@t.com'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data[0]['last_address'])

    def test_non_admin_returns_403(self):
        plain = User.objects.create_user('plain@t.com', 'plain@t.com', 'pass')
        self.client.force_authenticate(user=plain)
        resp = self.client.get(URL, {'q': 'algo'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
```

- [ ] **Step 2: Verificar que los tests fallan (RED)**

```bash
docker exec enid_store_service python manage.py test products.tests.test_client_search -v 2
```

Esperado: `AttributeError: type object 'ProductVuewSet' has no attribute 'clientes'` o similar. Si pasa, el endpoint ya existe — detente e investiga.

- [ ] **Step 3: Implementar el `@action clientes` en `products/views.py`**

Agregar estos imports al inicio del archivo (junto a los existentes):

```python
from django.contrib.auth import get_user_model
from django.db.models import Q
```

Agregar el método dentro de `ProductVuewSet`, después del método `certification` (línea ~107) y antes de `manual_sale`:

```python
    @action(detail=False, methods=['GET'], url_path='clientes',
            permission_classes=[IsAdminUser])
    def clientes(self, request):
        q = request.query_params.get('q', '').strip()
        if not q:
            return Response({'error': 'El parámetro q es requerido'}, status=400)

        UserModel = get_user_model()
        users = UserModel.objects.filter(
            Q(email__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)
        )[:20]

        result = []
        for u in users:
            last_order = Order.objects.filter(
                user=u, shipping_address__isnull=False
            ).order_by('-created_at').first()

            addr = None
            if last_order and last_order.shipping_address:
                a = last_order.shipping_address
                addr = {
                    'street': a.street,
                    'number': a.number,
                    'interior_number': a.interior_number,
                    'colony': a.colony,
                    'delegation_or_municipality': a.delegation_or_municipality,
                    'city': a.city,
                    'state': a.state_id,
                    'postal_code': a.postal_code,
                    'phone_number': a.phone_number,
                    'additional_details': a.additional_details or '',
                }

            result.append({
                'id': u.id,
                'email': u.email,
                'name': f'{u.first_name} {u.last_name}'.strip(),
                'last_address': addr,
            })

        return Response(result)
```

- [ ] **Step 4: Verificar que los tests pasan (GREEN)**

```bash
docker exec enid_store_service python manage.py test products.tests.test_client_search -v 2
```

Esperado: `OK` — 7 tests pasando.

- [ ] **Step 5: Commit en `develop` (repo `enid-store`)**

```bash
cd /home/arithgrey/enid/enid-store/enid
git add products/views.py products/tests/test_client_search.py
git commit -m "#0: Task 1 - GET /productos/clientes/ search endpoint

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Extender POST /productos/manual-sale/ con cliente y dirección

**Repo:** `enid-store/enid/`

**Files:**
- Create: `products/tests/test_manual_sale_customer.py`
- Modify: `products/views.py` (extender `manual_sale`)

**Interfaces:**
- Consumes: `customer_id?`, `customer_email?`, `customer_name?`, `address?` en payload de `POST /productos/manual-sale/`
- Produces: `201 {order_id, status, customer_id|null, customer_email|null}`

---

- [ ] **Step 1: Escribir los tests que deben fallar**

Crear `products/tests/test_manual_sale_customer.py`:

```python
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from order.models import Order
from address.models import Address
from state.models import State
from products.models import Product

User = get_user_model()
URL = '/productos/manual-sale/'


def _make_product():
    p = Product.objects.first()
    p.certification = 'published'
    p.certified_at = None
    p.save(update_fields=['certification', 'certified_at'])
    return p


def _base_payload(product):
    return {
        'items': [{'product': product.id, 'quantity': 1, 'price': 100}],
        'status': 'delivered',
    }


def _address_payload():
    state = State.objects.first()
    return {
        'street': 'Calle Morelos',
        'number': 5,
        'interior_number': 1,
        'colony': 'Juárez',
        'delegation_or_municipality': 'Cuauhtémoc',
        'city': 'CDMX',
        'state': state.id,
        'postal_code': '06600',
        'phone_number': '5598765432',
        'additional_details': '',
    }


class ManualSaleCustomerTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser('admin@ms.com', 'admin@ms.com', 'pass')
        self.client.force_authenticate(user=self.admin)

    def test_sale_with_customer_id_assigns_user(self):
        product = _make_product()
        user = User.objects.create_user('existing@t.com', 'existing@t.com', 'pass')
        payload = {**_base_payload(product), 'customer_id': user.id}

        resp = self.client.post(URL, payload, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(pk=resp.data['order_id'])
        self.assertEqual(order.user_id, user.id)
        self.assertEqual(resp.data['customer_id'], user.id)
        self.assertEqual(resp.data['customer_email'], user.email)

    def test_sale_with_nonexistent_customer_id_returns_400(self):
        product = _make_product()
        payload = {**_base_payload(product), 'customer_id': 999999}

        resp = self.client.post(URL, payload, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sale_with_new_email_creates_user_and_assigns(self):
        product = _make_product()
        payload = {
            **_base_payload(product),
            'customer_email': 'nuevo@t.com',
            'customer_name': 'Luis Pérez',
        }

        resp = self.client.post(URL, payload, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='nuevo@t.com')
        self.assertEqual(user.first_name, 'Luis')
        self.assertEqual(user.last_name, 'Pérez')
        order = Order.objects.get(pk=resp.data['order_id'])
        self.assertEqual(order.user_id, user.id)

    def test_sale_with_existing_email_reuses_user(self):
        product = _make_product()
        existing = User.objects.create_user('reuse@t.com', 'reuse@t.com', 'pass')
        payload = {**_base_payload(product), 'customer_email': 'reuse@t.com'}

        resp = self.client.post(URL, payload, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(pk=resp.data['order_id'])
        self.assertEqual(order.user_id, existing.id)
        self.assertEqual(User.objects.filter(email='reuse@t.com').count(), 1)

    def test_sale_with_empty_customer_email_returns_400(self):
        product = _make_product()
        payload = {**_base_payload(product), 'customer_email': ''}

        resp = self.client.post(URL, payload, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sale_with_address_creates_and_assigns_shipping_address(self):
        product = _make_product()
        payload = {**_base_payload(product), 'address': _address_payload()}

        resp = self.client.post(URL, payload, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(pk=resp.data['order_id'])
        self.assertIsNotNone(order.shipping_address)
        self.assertEqual(order.shipping_address.street, 'Calle Morelos')
        self.assertEqual(order.shipping_address.postal_code, '06600')

    def test_sale_without_customer_or_address_is_retrocompatible(self):
        product = _make_product()

        resp = self.client.post(URL, _base_payload(product), format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(pk=resp.data['order_id'])
        self.assertIsNone(order.user)
        self.assertIsNone(order.shipping_address)

    def test_sale_with_address_missing_required_field_returns_400(self):
        product = _make_product()
        addr = _address_payload()
        del addr['street']
        payload = {**_base_payload(product), 'address': addr}

        resp = self.client.post(URL, payload, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
```

- [ ] **Step 2: Verificar que los tests fallan (RED)**

```bash
docker exec enid_store_service python manage.py test products.tests.test_manual_sale_customer -v 2
```

Esperado: la mayoría fallan porque `manual_sale` no maneja `customer_id`/`customer_email`/`address` aún.

- [ ] **Step 3: Extender `manual_sale` en `products/views.py`**

Agregar este import al inicio (junto a los existentes, si no está):

```python
from address.models import Address
```

Reemplazar el método `manual_sale` completo por esta implementación:

```python
    @action(detail=False, methods=['post'], url_path='manual-sale',
            permission_classes=[IsAdminUser])
    def manual_sale(self, request):
        items = request.data.get('items') or []
        status_val = request.data.get('status', 'delivered')
        sale_date = request.data.get('sale_date') or None
        customer_id = request.data.get('customer_id')
        customer_email = request.data.get('customer_email')
        customer_name = request.data.get('customer_name', '')
        address_data = request.data.get('address')

        if not items:
            return Response({'error': 'Se requiere al menos un item'}, status=400)
        if status_val not in RECIBIDOS:
            return Response(
                {'error': f'status inválido; usar uno de {RECIBIDOS}'}, status=400
            )

        # Resolver usuario
        UserModel = get_user_model()
        user = None
        if customer_id is not None:
            user = UserModel.objects.filter(pk=customer_id).first()
            if user is None:
                return Response({'error': f'Usuario {customer_id} no existe'}, status=400)
        elif customer_email is not None:
            if not customer_email:
                return Response({'error': 'customer_email no puede ser vacío'}, status=400)
            parts = customer_name.split(' ', 1)
            first_name = parts[0] if parts else ''
            last_name = parts[1] if len(parts) > 1 else ''
            user, created = UserModel.objects.get_or_create(
                email=customer_email,
                defaults={
                    'username': customer_email,
                    'first_name': first_name,
                    'last_name': last_name,
                },
            )

        # Resolver dirección
        ADDRESS_REQUIRED = ['street', 'number', 'interior_number', 'colony',
                             'delegation_or_municipality', 'city', 'state',
                             'postal_code', 'phone_number']
        shipping_address = None
        if address_data is not None:
            missing = [f for f in ADDRESS_REQUIRED if not address_data.get(f)]
            if missing:
                return Response(
                    {'error': f'Campos de dirección requeridos faltantes: {missing}'}, status=400
                )
            shipping_address = Address(
                street=address_data['street'],
                number=address_data['number'],
                interior_number=address_data['interior_number'],
                colony=address_data['colony'],
                delegation_or_municipality=address_data['delegation_or_municipality'],
                city=address_data['city'],
                state_id=address_data['state'],
                postal_code=address_data['postal_code'],
                phone_number=address_data['phone_number'],
                additional_details=address_data.get('additional_details', ''),
            )

        # Validar productos antes de crear nada
        resolved = []
        for it in items:
            product = Product.objects.filter(pk=it.get('product')).first()
            if not product:
                return Response({'error': 'Producto inexistente'}, status=400)
            resolved.append((product, it.get('quantity', 1), it.get('price')))

        with transaction.atomic():
            if shipping_address is not None:
                shipping_address.save()
            order = Order.objects.create(
                status=status_val,
                source='admin_manual',
                sale_date=sale_date,
                user=user,
                shipping_address=shipping_address,
            )
            for product, quantity, price in resolved:
                ItemOrder.objects.create(
                    order=order, product=product, quantity=quantity, price=price
                )

        return Response({
            'order_id': order.id,
            'status': order.status,
            'customer_id': user.id if user else None,
            'customer_email': user.email if user else None,
        }, status=201)
```

- [ ] **Step 4: Verificar que los tests pasan (GREEN)**

```bash
docker exec enid_store_service python manage.py test products.tests.test_manual_sale_customer -v 2
```

Esperado: `OK` — 8 tests pasando.

- [ ] **Step 5: Verificar que los tests anteriores (Task 1 + test_manual_sale.py) siguen verdes**

```bash
docker exec enid_store_service python manage.py test products.tests -v 2
```

Esperado: `OK` — todos los tests de products pasando.

- [ ] **Step 6: Commit en `develop` (repo `enid-store`)**

```bash
cd /home/arithgrey/enid/enid-store/enid
git add products/views.py products/tests/test_manual_sale_customer.py
git commit -m "#0: Task 2 - Extender manual-sale con cliente y dirección

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Frontend — ManualSaleForm.vue con búsqueda, cliente y dirección

**Repo:** `service-store/`

**Files:**
- Modify: `src/components/Products/ManualSaleForm.vue`
- Modify: `tests/unit/components/Products/ManualSaleForm.spec.js`

**Interfaces:**
- Consumes: `GET enid/productos/clientes/?q=<str>` → `[{id, email, name, last_address|null}]`
- Produces: payload `POST enid/productos/manual-sale/` con `customer_id?`, `customer_email?`, `customer_name?`, `address?`

---

- [ ] **Step 1: Escribir los nuevos tests que deben fallar**

Agregar al final de `tests/unit/components/Products/ManualSaleForm.spec.js` (después del `describe` existente):

```js
describe('ManualSaleForm - búsqueda de cliente y dirección', () => {
  const product = { id: 1, name: 'Producto X', price: 100 };

  it('renderiza el input de búsqueda de cliente', () => {
    const wrapper = mount(ManualSaleForm, { props: { product } });
    expect(wrapper.find('[data-test="ms-search"]').exists()).toBe(true);
  });

  it('renderiza los campos de email y nombre de cliente', () => {
    const wrapper = mount(ManualSaleForm, { props: { product } });
    expect(wrapper.find('[data-test="ms-email"]').exists()).toBe(true);
    expect(wrapper.find('[data-test="ms-customer-name"]').exists()).toBe(true);
  });

  it('la sección de dirección está oculta por defecto', () => {
    const wrapper = mount(ManualSaleForm, { props: { product } });
    expect(wrapper.find('[data-test="ms-address-section"]').exists()).toBe(false);
  });

  it('al activar el toggle de dirección aparece la sección de campos', async () => {
    const wrapper = mount(ManualSaleForm, { props: { product } });
    await wrapper.find('[data-test="ms-address-toggle"]').setValue(true);
    expect(wrapper.find('[data-test="ms-address-section"]').exists()).toBe(true);
  });

  it('con selectedCustomer seteado los campos email y nombre muestran sus valores', async () => {
    const wrapper = mount(ManualSaleForm, { props: { product } });
    wrapper.vm.selectedCustomer = { id: 42, email: 'ana@t.com', name: 'Ana García', last_address: null };
    wrapper.vm.email = 'ana@t.com';
    wrapper.vm.customerName = 'Ana García';
    await wrapper.vm.$nextTick();

    expect(wrapper.find('[data-test="ms-email"]').element.value).toBe('ana@t.com');
    expect(wrapper.find('[data-test="ms-customer-name"]').element.value).toBe('Ana García');
  });

  it('selectClient() rellena email, nombre y customer_id', async () => {
    const wrapper = mount(ManualSaleForm, { props: { product } });
    const cliente = { id: 42, email: 'ana@t.com', name: 'Ana García', last_address: null };
    wrapper.vm.selectClient(cliente);
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.email).toBe('ana@t.com');
    expect(wrapper.vm.customerName).toBe('Ana García');
    expect(wrapper.vm.selectedCustomer).toEqual(cliente);
    expect(wrapper.vm.showDropdown).toBe(false);
  });

  it('selectClient() con last_address activa el toggle y rellena addressForm', async () => {
    const wrapper = mount(ManualSaleForm, { props: { product } });
    const cliente = {
      id: 42,
      email: 'ana@t.com',
      name: 'Ana García',
      last_address: {
        street: 'Av. Hidalgo', number: 10, interior_number: 1,
        colony: 'Centro', delegation_or_municipality: 'Cuauhtémoc',
        city: 'CDMX', state: 9, postal_code: '06600',
        phone_number: '5512345678', additional_details: '',
      },
    };
    wrapper.vm.selectClient(cliente);
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.showAddress).toBe(true);
    expect(wrapper.vm.addressForm.street).toBe('Av. Hidalgo');
    expect(wrapper.vm.addressForm.state).toBe(9);
  });
});
```

- [ ] **Step 2: Verificar que los nuevos tests fallan (RED)**

```bash
docker exec service-store-frontend-1 npm run test:unit -- --testPathPattern=ManualSaleForm
```

Esperado: varios `Cannot find element` y `is not a function`. Los tests del `describe` existente deben seguir en verde.

- [ ] **Step 3: Reemplazar el template de `ManualSaleForm.vue`**

Reemplazar el `<template>` completo del archivo `src/components/Products/ManualSaleForm.vue`:

```html
<template>
  <form class="manual-sale-form space-y-4" @submit.prevent="submit">
    <div class="pb-3 border-b border-gray-200">
      <h4 class="text-base font-semibold text-gray-900">Registrar venta manual</h4>
      <p class="mt-1 text-sm text-gray-500">{{ product.name }}</p>
    </div>

    <!-- Búsqueda de cliente -->
    <div class="relative">
      <label class="block text-sm font-medium text-gray-700 mb-1">Buscar cliente (email o nombre)</label>
      <input
        data-test="ms-search"
        v-model="searchQuery"
        @input="onSearchInput"
        type="text"
        placeholder="Escribe email o nombre..."
        class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
      />
      <ul
        v-if="showDropdown"
        class="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-md shadow-lg max-h-48 overflow-y-auto"
      >
        <li
          v-if="searchResults.length === 0"
          class="px-3 py-2 text-sm text-gray-500 italic"
        >
          Cliente nuevo — se creará al registrar
        </li>
        <li
          v-for="cliente in searchResults"
          :key="cliente.id"
          @click="selectClient(cliente)"
          class="px-3 py-2 text-sm text-gray-800 hover:bg-indigo-50 cursor-pointer"
        >
          {{ cliente.name }} — {{ cliente.email }}
        </li>
      </ul>
    </div>

    <!-- Email y nombre del cliente -->
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">Email del cliente <span class="text-gray-400 font-normal">(opcional)</span></label>
      <input
        data-test="ms-email"
        v-model="email"
        type="email"
        class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
      />
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">Nombre completo <span class="text-gray-400 font-normal">(opcional)</span></label>
      <input
        data-test="ms-customer-name"
        v-model="customerName"
        type="text"
        class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
      />
    </div>

    <!-- Toggle dirección -->
    <div class="flex items-center gap-2">
      <input
        id="ms-address-toggle"
        data-test="ms-address-toggle"
        v-model="showAddress"
        type="checkbox"
        class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
      />
      <label for="ms-address-toggle" class="text-sm font-medium text-gray-700">¿Agregar dirección de envío?</label>
    </div>

    <!-- Sub-form de dirección (colapsable) -->
    <div v-if="showAddress" data-test="ms-address-section" class="space-y-3 p-3 bg-gray-50 rounded-md border border-gray-200">
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Calle</label>
          <input v-model="addressForm.street" type="text" class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Número</label>
          <input v-model.number="addressForm.number" type="number" class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Número interior</label>
          <input v-model.number="addressForm.interior_number" type="number" class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Colonia</label>
          <input v-model="addressForm.colony" type="text" class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Municipio / Delegación</label>
          <input v-model="addressForm.delegation_or_municipality" type="text" class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Ciudad</label>
          <input v-model="addressForm.city" type="text" class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Estado</label>
          <select v-model.number="addressForm.state" class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm">
            <option value="" disabled>Selecciona un estado</option>
            <option v-for="s in states" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">CP</label>
          <input v-model="addressForm.postal_code" type="text" maxlength="10" class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Teléfono</label>
          <input v-model="addressForm.phone_number" type="tel" class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm" />
        </div>
        <div class="col-span-2">
          <label class="block text-sm font-medium text-gray-700 mb-1">Detalles adicionales <span class="text-gray-400 font-normal">(opcional)</span></label>
          <input v-model="addressForm.additional_details" type="text" class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm" />
        </div>
      </div>
    </div>

    <!-- Campos existentes -->
    <div>
      <label for="ms-qty" class="block text-sm font-medium text-gray-700 mb-1">Cantidad</label>
      <input
        id="ms-qty"
        v-model.number="quantity"
        type="number"
        min="1"
        data-test="ms-qty"
        class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
      />
    </div>

    <div>
      <label for="ms-price" class="block text-sm font-medium text-gray-700 mb-1">Precio</label>
      <div class="relative">
        <span class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-gray-500 text-sm">$</span>
        <input
          id="ms-price"
          v-model.number="price"
          type="number"
          min="0"
          step="0.01"
          data-test="ms-price"
          class="block w-full rounded-md border border-gray-300 pl-7 pr-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
        />
      </div>
    </div>

    <div>
      <label for="ms-status" class="block text-sm font-medium text-gray-700 mb-1">Estado</label>
      <select
        id="ms-status"
        v-model="status"
        data-test="ms-status"
        class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
      >
        <option value="delivered">Entregado</option>
        <option value="payment_confirmed">Pago Confirmado</option>
        <option value="cash_on_delivery">Pagado contra Entrega</option>
      </select>
    </div>

    <div>
      <label for="ms-date" class="block text-sm font-medium text-gray-700 mb-1">
        Fecha de venta <span class="text-gray-400 font-normal">(opcional)</span>
      </label>
      <input
        id="ms-date"
        v-model="saleDate"
        type="datetime-local"
        data-test="ms-date"
        class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
      />
    </div>

    <button
      type="submit"
      data-test="ms-submit"
      :disabled="submitting"
      class="w-full inline-flex items-center justify-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {{ submitting ? 'Registrando…' : 'Registrar venta' }}
    </button>
  </form>
</template>
```

- [ ] **Step 4: Reemplazar el `<script>` de `ManualSaleForm.vue`**

Reemplazar el bloque `<script>` completo:

```html
<script>
export default {
  name: 'ManualSaleForm',
  props: { product: { type: Object, required: true } },
  data() {
    return {
      quantity: 1,
      price: this.product.price,
      status: 'delivered',
      saleDate: '',
      submitting: false,
      // búsqueda
      searchQuery: '',
      searchResults: [],
      showDropdown: false,
      searchTimeout: null,
      // cliente
      selectedCustomer: null,
      email: '',
      customerName: '',
      // dirección
      showAddress: false,
      states: [],
      addressForm: {
        street: '',
        number: null,
        interior_number: null,
        colony: '',
        delegation_or_municipality: '',
        city: '',
        state: '',
        postal_code: '',
        phone_number: '',
        additional_details: '',
      },
    };
  },
  async mounted() {
    try {
      const { data } = await this.$axios.get('enid/estado');
      this.states = data;
    } catch (e) {
      // estados no disponibles, el select queda vacío
    }
  },
  methods: {
    onSearchInput() {
      clearTimeout(this.searchTimeout);
      if (this.searchQuery.length < 2) {
        this.showDropdown = false;
        return;
      }
      this.searchTimeout = setTimeout(() => this.fetchClients(), 300);
    },
    async fetchClients() {
      try {
        const { data } = await this.$axios.get('enid/productos/clientes/', {
          params: { q: this.searchQuery },
        });
        this.searchResults = data.slice(0, 8);
        this.showDropdown = true;
      } catch (e) {
        this.showDropdown = false;
      }
    },
    selectClient(cliente) {
      this.selectedCustomer = cliente;
      this.email = cliente.email;
      this.customerName = cliente.name;
      this.showDropdown = false;
      if (cliente.last_address) {
        this.showAddress = true;
        this.addressForm = { ...cliente.last_address };
      }
    },
    async submit() {
      if (this.submitting) return;
      this.submitting = true;
      try {
        const payload = {
          items: [{ product: this.product.id, quantity: this.quantity, price: this.price }],
          status: this.status,
          sale_date: this.saleDate ? new Date(this.saleDate).toISOString() : null,
          ...(this.selectedCustomer ? { customer_id: this.selectedCustomer.id } : {}),
          ...(this.email && !this.selectedCustomer ? { customer_email: this.email } : {}),
          ...(this.customerName && !this.selectedCustomer ? { customer_name: this.customerName } : {}),
          ...(this.showAddress ? { address: { ...this.addressForm } } : {}),
        };
        const { data } = await this.$axios.post('enid/productos/manual-sale/', payload);
        this.$emit('sale-registered', data);
      } finally {
        this.submitting = false;
      }
    },
  },
};
</script>
```

- [ ] **Step 5: Verificar que todos los tests del spec pasan (GREEN)**

```bash
docker exec service-store-frontend-1 npm run test:unit -- --testPathPattern=ManualSaleForm
```

Esperado: todos los tests del describe original + los 7 nuevos en verde.

- [ ] **Step 6: Commit en `develop` (repo `service-store`)**

```bash
cd /home/arithgrey/enid/service-store
git add src/components/Products/ManualSaleForm.vue tests/unit/components/Products/ManualSaleForm.spec.js
git commit -m "#0: Task 3 - ManualSaleForm con búsqueda de cliente y dirección

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Progreso: 3/3 Tasks (100%) ✅

- [x] Task 1: GET /productos/clientes/ search endpoint ✅ (2026-11-17)
- [x] Task 2: Extender POST /productos/manual-sale/ ✅ (2026-11-17)
- [x] Task 3: ManualSaleForm.vue — búsqueda, cliente y dirección ✅ (2026-11-17)
