# URLs dinámicas (mismo-origen) — Plan de Implementación

**Spec:** docs/specs/2026-11-19-urls-dinamicas-design.md
**Work Item:** #0
**Branch:** develop

## Task 1: Imágenes con URL relativa

- [ ] **Step 1: Investigar origen de `http://localhost/uploads/...` en la API**
  - Archivos: `enid-store/enid/image/`, `products/` (solo lectura)
  - Esperado: causa documentada en este plan.
- [ ] **Step 2: Test de integración (RED) — imagen devuelve ruta relativa**
  - Archivos: `enid-store/enid/image/tests/` (Testcontainers + Postgres real, sin mocks)
  - Esperado: test falla con el código actual.
- [ ] **Step 3: `get_image_url` devuelve `self.image.url`; test GREEN**
  - Archivos: `enid-store/enid/image/models.py`
  - Esperado: test pasa dentro del contenedor (`docker exec`).

## Task 2: nginx mismo-origen

- [ ] **Step 4: Rutas de API en el bloque :80 de `proxy.conf`**
  - Archivos: `reverse_proxy_nginx/proxy.conf`
  - Esperado: `curl http://localhost/enid/...` y `/oauth/...` llegan al upstream (no 404 de nginx).
- [ ] **Step 5: `server_name _` y retirar mapa CORS con hosts fijos**
  - Archivos: `reverse_proxy_nginx/proxy.conf`
  - Esperado: `nginx -t` OK; funciona con Host = IP, dominio y localhost.

## Task 3: Frontend relativo

- [ ] **Step 6: `baseURL` relativo, quitar `VITE_APP_API`**
  - Archivos: `service-store/src/axiosInstance.js`, `service-store/env.example`
  - Esperado: peticiones salen al mismo origen; E2E Playwright de login OK.
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
**Progreso:** 0/9 Steps (0%)
⏸️ SIGUIENTE: Step 1
