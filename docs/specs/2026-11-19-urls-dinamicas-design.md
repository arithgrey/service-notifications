# URLs dinámicas (mismo-origen) — Spec

**Work Item:** #0
**Rama:** `develop` (todos los repos)

## Problema (verificado en repo y VPS 82.180.161.54)

- `enid-store/enid/image/models.py:22-25`: `get_image_url` devuelve `settings.DOMAIN + image.url`; si `DOMAIN` vacío devuelve `None`.
- VPS: `DOMAIN=http://enidservice.tech:8000` en el contenedor `enid_store_service`. nginx :8000 NO tiene `location /uploads/` (404). Por IP, Django responde 400 (`ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,enidservice.tech`).
- `service-store/src/axiosInstance.js:3`: `baseURL = import.meta.env.VITE_APP_API` (`env.example`: `http://localhost:8000`).
- `reverse_proxy_nginx/proxy.conf`: `server_name localhost`; mapa CORS `$cors_origin` con hosts a mano; :80 solo rutea `/uploads/` y `/` (frontend :5173).
- `service-store/Dockerfile`: `CMD npm run dev` (Vite dev) también en el VPS.
- Mecanismo: `enid-store/enid/enid/settings.py` lee `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `DOMAIN` de `.env`.

## Objetivo

Cambiar entre dev y prod indicando solo `APP_ENV=dev|prod`. Ningún host/IP/dominio en código ni en config versionada.

## Diseño

1. El navegador habla solo con nginx :80 (mismo origen), en cualquier host.
2. Imágenes: URL relativa (`/uploads/X`), sin `DOMAIN`.
3. nginx :80 rutea los prefijos de API (`/enid/`, `/oauth/`, `/rbac/`, `/logout/`, `/lead/`, `/stock/`, `/landings/`, `/faqs/`, `/references/`) con el mismo mapa que ya existe en :8000.
4. Frontend: `baseURL` relativo; se elimina `VITE_APP_API`.
5. `APP_ENV=dev`: Vite con HMR, `ALLOWED_HOSTS=*`. `APP_ENV=prod`: build estático, `DEBUG=False`, `ALLOWED_HOSTS=*` (aprobado), puertos de servicios ligados a `127.0.0.1`.

## Decisiones aprobadas por el usuario

- `ALLOWED_HOSTS=*` en prod + puertos a `127.0.0.1`.
- Se usa docker compose en el VPS (excepción consciente a la regla de CLAUDE.md, a pedido del usuario).
- Flujo local → push `develop` → `git pull` en VPS (ver CLAUDE.md).

## Pendientes por verificar (no asumir)

- Origen de URLs `http://localhost/uploads/...` en la respuesta de la API.
- Si `src/config/google.js` y `src/helpers/EcommerceHelper.js` necesitan el mismo cambio.
- DNS de `enidservice.tech` (resuelve a IPv6 `2a02:4780:10:2d2f::1`; no confirmado que apunte al VPS).
- Valor de `VITE_APP_API` en el `.env` del VPS (no leído).

## Criterios de aceptación (E2E, exit code 0)

- Login y listado de productos funcionan vía `http://82.180.161.54` y, si el DNS apunta, vía dominio.
- Las imágenes de productos cargan (200 `image/*`) en ambos.
- Cambiar `APP_ENV` es el único cambio para pasar de dev a prod.
