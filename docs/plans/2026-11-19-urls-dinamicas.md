# URLs dinámicas (mismo-origen) — Plan de Implementación

**Spec:** docs/specs/2026-11-19-urls-dinamicas-design.md
**Work Item:** #0
**Branch:** develop

## Task 1: Imágenes con URL relativa

- [x] **Step 1: Investigar origen de `http://localhost/uploads/...` en la API** ✅ (2026-11-19)
  - Archivos: `enid-store/enid/image/`, `products/` (solo lectura)
  - Esperado: causa documentada en este plan.
  - **Hallazgo (verificado):** `ImageSerializer` (`image/serializers.py`) expone DOS campos:
    - `image`: `ImageField` de DRF, `use_url` por defecto; con `request` en contexto arma URL absoluta con el `Host` del request. Probado en VPS: `Host: localhost` → `http://localhost/uploads/X`; `Host: enidservice.tech` → `http://enidservice.tech/uploads/X`. Este es el origen de las URLs `localhost`.
    - `get_image_url`: `settings.DOMAIN + image.url` → `http://enidservice.tech:8000/uploads/X` (fijo, sin `/uploads/` en nginx :8000).
  - **Consumo en frontend:** casi todos los componentes usan `get_image_url` (ej. `ProductDetail.vue:133`, `RecentProducts.vue:245`). `ProductCard.vue:5` usa `product.image` (campo distinto de producto, no verificado).
  - **Consecuencia para Step 3:** basta cambiar `get_image_url` a ruta relativa; el frontend no cambia para imágenes. `revenue/views.py:152` ya devuelve `image.url` relativo.
  - **Pendiente:** verificar origen de `product.image` en `ProductCard.vue:5` (Step 6/7).
- [x] **Step 2: Test de integración (RED) — imagen devuelve ruta relativa** ✅ (2026-11-19 10:35)
  - Archivos: `enid-store/enid/image/tests/` (Testcontainers + Postgres real, sin mocks)
  - Esperado: test falla con el código actual.
  - **Hecho:** `image/tests/test_image_url_integration.py` (3 tests, Postgres real del compose; patrón de `order/tests/`, sin testcontainers: no hay en requirements). Se eliminó el stub vacío `image/tests.py`. RED verificado: `docker exec enid_store_service python manage.py test image --noinput` → 3 FAIL (URL absoluta con host fijo; `None` sin DOMAIN).
- [x] **Step 3: `get_image_url` devuelve `self.image.url`; test GREEN** ✅ (2026-11-19)
  - Archivos: `enid-store/enid/image/models.py`
  - Esperado: test pasa dentro del contenedor (`docker exec`).
  - **Hecho:** 3/3 GREEN. Suite completa: 36 fallos/errores preexistentes (idénticos antes y después, ninguno nuevo); no son de este plan.

## Task 2: nginx mismo-origen

- [x] **Step 4: Rutas de API en el bloque :80 de `proxy.conf`** ✅ (2026-11-19)
  - Archivos: `reverse_proxy_nginx/proxy.conf`
  - Esperado: `curl http://localhost/enid/...` y `/oauth/...` llegan al upstream (no 404 de nginx).
  - **Hecho:** 9 locations en :80 (sin CORS, mismo-origen). `nginx -t` OK. `/enid/categorias/` → 200 (igual que :8000). Resto → 502: upstreams (oauth 8083, lead, stock, landings, faqs, references) no levantados localmente; nginx rutea (no 404). Re-verificar con servicios arriba en Step 9.
- [x] **Step 5: `server_name _` y retirar mapa CORS con hosts fijos** ✅ (2026-11-19)
  - Archivos: `reverse_proxy_nginx/proxy.conf`
  - Esperado: `nginx -t` OK; funciona con Host = IP, dominio y localhost.
  - **Hecho:** `server_name _` en ambos bloques; mapa ahora `default $http_origin` (sin hosts fijos, solo afecta :8000 transitorio). `nginx -t` OK. Host=localhost/127.0.0.1 → 200. Host=IP/dominio → 400 por `DisallowedHost` de Django (verificado directo en :8085; `ALLOWED_HOSTS` local), NO nginx: se resuelve en Step 8 (`ALLOWED_HOSTS=*`). CORS :8000 refleja Origin OK.

## Task 3: Frontend relativo

- [x] **Step 6: `baseURL` relativo, quitar `VITE_APP_API`** ✅ (2026-11-19)
  - Archivos: `service-store/src/axiosInstance.js`, `service-store/env.example`
  - Esperado: peticiones salen al mismo origen; E2E Playwright de login OK.
  - **Hecho:** `baseURL = '/'` (no `''`: las rutas sin slash inicial, ej. `oauth/login/refresh-token/`, colgarían de la ruta actual). Test `tests/e2e/login_same_origin.spec.js` (login real vía nginx :80 → oauth real, sin mocks). RED real: origin `http://localhost:8000` ≠ `http://localhost`. GREEN: 1 passed, exit 0. Verificación de `/oauth/` llegando a upstream real (pendiente de Step 4): OK (`/oauth/user/exists/` 200, `/oauth/login/sigin/` 200).
  - **Hallazgo de entorno (aprobado por usuario):** el admin local tenía password en plano; la UI manda `sha256(password)`. Se reseteó en la DB local de service-oauth (`set_password(sha256('enidservice@gmail.com'))`), solo datos locales, no versionado. Se arrancaron contenedores detenidos: oauth, oauth postgres, frontend, enid_store_e2e. El spec previo `manual_sale_cliente` no se corrió.
- [ ] **Step 7: Revisar `google.js` y `EcommerceHelper.js`**
  - Archivos: `service-store/src/config/google.js`, `service-store/src/helpers/EcommerceHelper.js`
  - Esperado: sin hosts hardcodeados, o justificación documentada.

## Task 4: Interruptor APP_ENV

- [ ] **Step 8: `APP_ENV` en compose de enid-store y service-store**
  - Archivos: `enid-store/enid/docker-compose.yml`, `service-store/docker-compose.yml`, `service-store/Dockerfile.prod` (nuevo, build estático)
  - Esperado: `APP_ENV=dev` → Vite HMR; `prod` → build estático, `DEBUG=False`, `ALLOWED_HOSTS=*`, puertos a `127.0.0.1`.

## Task 5: Verificación real en VPS

- [ ] **Step 9: push `develop`, `git pull` en VPS, rebuild y E2E**
  - Archivos: ninguno (operación)
  - Esperado: login, listado de productos e imágenes OK por IP (y dominio si DNS apunta). Exit code 0.

---
**Progreso:** 6/9 Steps (66%)
⏸️ SIGUIENTE: Step 7
