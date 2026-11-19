# CLAUDE.md — Estándares de Software FINDEP

## Rol

Actúa como arquitecto de software experto y desarrollador Senior.

---

## Ejecución & Entorno

<HARD-GATE>
NUNCA ejecutes comandos directamente en el host (pytest, python, mvn, dotnet).
Todo corre dentro del contenedor via docker exec.
Si estás a punto de correr un comando sin `docker exec`, DETENTE.
</HARD-GATE>

- **Solo Docker** — ninguna app corre directamente en el host.
  - ✅ `docker exec <nombre_servicio> pytest`
  - ✅ `docker compose up` (usar siempre `docker compose` v2, NO `docker-compose` v1)
  - ❌ `pytest` en el host
  - ❌ `python main.py` en el host
- **CI/CD via docker compose** — flujo obligatorio:
  ```bash
  docker compose build
  docker compose up -d
  docker exec <nombre_servicio> pytest
  ```

> **Nota:** `docker-compose` (con guión, v1) está deprecado en este entorno. Usar siempre `docker compose` (con espacio, v2).
- **Sistema operativo:** Ubuntu 20.04. En Windows usar WSL:
  ```bash
  wsl -d Ubuntu-20.04 -e bash -c "<comando>"
  ```

---

## Desarrollo Local con Watchdog (Python)

<HARD-GATE>
`docker-compose.yml` es EXCLUSIVAMENTE para desarrollo local y pruebas.
NUNCA se integra a UAT, staging ni producción.
Si estás a punto de usar docker-compose en un entorno compartido, DETENTE.
</HARD-GATE>

### Dos Modos — Dockerfile único, dos orquestaciones

| Modo | Dockerfile | Orquestación |
|------|-----------|-------------|
| Desarrollo/Test | `Dockerfile` (CMD con `watchmedo`) | `docker-compose.yml` |
| Producción/UAT | `Dockerfile.prod` | GKE manifests |

### CMD estándar en Dockerfile (dev)

```dockerfile
CMD ["watchmedo", "auto-restart", \
     "--directory=./", \
     "--pattern=*.py", \
     "--recursive", \
     "--", \
     "uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8080"]
```

Dependencia requerida en `requirements-dev.txt`:
```
watchdog[watchmedo]
```

### Volume mount obligatorio

El bind mount `.:/app` es lo que permite a `watchmedo` detectar cambios del host dentro del contenedor. Sin él, el hot-reload no funciona.

```yaml
services:
  microservice:
    volumes:
      - .:/app  # ← obligatorio para watchdog
```

### Stack estándar de desarrollo

```yaml
# docker-compose.yml — SOLO DESARROLLO LOCAL
services:
  microservice:        # uvicorn + watchmedo (hot-reload)
  postgres:            # postgres:alpine con healthcheck
  locust:              # load testing (opcional, comentar si no se necesita)
  # redis:             # comentado por defecto, activar si el servicio lo requiere
```

### Flujo de arranque

```bash
# Primera vez
docker-compose up --build

# Subsecuentes (sin rebuild)
docker-compose up

# Editar un .py → watchmedo detecta el cambio y reinicia uvicorn automáticamente

# Correr tests (en otro terminal)
docker exec ${SERVICENAME}_service pytest
```

---

## Diseño & Código

- **SOLID obligatorio** — SRP, OCP, interfaces claras, inversión de dependencias.
- **DRY** — no duplicar lógica; extraer helpers y módulos reutilizables.
- **Prohibido crear Makefiles.**
- **Prohibido crear archivos `.sh`** para automatización. Todo flujo via `docker-compose` y comandos explícitos documentados.

### Import Path Rules

<HARD-GATE>
NUNCA uses rutas relativas con traversal (../ o ../../) para importar módulos, componentes, servicios o utilidades en ningún lenguaje.
Usa siempre @/ (frontend) o imports absolutos desde la raíz del paquete (backend).
</HARD-GATE>

```typescript
// ❌ BAD
import { Button } from '../../components/Button';
// ✅ GOOD
import { Button } from '@/components/Button';
```

```python
# ❌ BAD
from ../../services.user import UserService
# ✅ GOOD
from app.services.user import UserService
```

---

## Frontend React — Base Template

<HARD-GATE>
NUNCA inicialices un proyecto React desde cero (create-react-app, vite init, npx create-next-app, etc.).
Siempre clonar arq-example-sso rama tyson/beta. Ya trae SSO, Tailwind, aliases y hot-reload configurados.
Si estás a punto de correr cualquier scaffold de React, DETENTE.
</HARD-GATE>


### Desarrollo local con hot-reload (Docker)

Mismo principio que el watchdog de Python: volumen bind mount + servidor de desarrollo.

```yaml
# docker-compose.yml — SOLO DESARROLLO LOCAL
services:
  frontend:
    build: .
    volumes:
      - .:/app
      - /app/node_modules  # excluir node_modules del bind mount
    ports:
      - "3000:3000"
    command: npm run dev -- --host 0.0.0.0
    environment:
      - VITE_APP_ENV=development
```

Editar un `.tsx` / `.ts` → HMR actualiza el browser automáticamente, sin rebuild.

### Configuración de rutas — sin hardcode de URLs

<HARD-GATE>
NUNCA escribas URLs, hosts ni paths de API directamente en componentes o hooks.
</HARD-GATE>

### Import paths — siempre `@/`

```typescript
// ❌ BAD
import { Button } from '../../components/Button';
import { useAuth } from '../../../hooks/useAuth';

// ✅ GOOD
import { Button } from '@/components/Button';
import { useAuth } from '@/hooks/useAuth';
```

### Estructura de carpetas DRY


## Configuración — Sin Hardcode

<HARD-GATE>
NUNCA hardcodees valores: URLs, hosts, puertos, claves, nombres de servicios, timeouts, ni ningún literal que pueda variar entre entornos.
Todos los valores van en el archivo de configuración nativo del lenguaje. El código solo lee de ahí.
</HARD-GATE>



## Pruebas (TDD estricto, sin mocks)

<HARD-GATE>
Todo software DEBE tener pruebas de integración.
Las pruebas unitarias solas no son suficientes — se requiere al menos una prueba de integración
que valide el flujo completo con infraestructura real (DB, colas, APIs externas) via Testcontainers.
Si vas a entregar código sin pruebas de integración, DETENTE.
</HARD-GATE>

<HARD-GATE>
NUNCA uses mocks, stubs, fakes ni doubles bajo ninguna circunstancia.
Prohibido: unittest.mock, pytest-mock, monkeypatch, Moq, NSubstitute, Mockito.
Si estás a punto de importar cualquiera de estas librerías, DETENTE.
La única alternativa válida es un contenedor real vía Testcontainers.
</HARD-GATE>

<HARD-GATE>
TDD estricto: la prueba DEBE existir y FALLAR antes de escribir el código de producción.
Si ya tienes código implementado y aún no tienes test, estás violando TDD.
</HARD-GATE>

### Process Flow — Ciclo TDD

```dot
digraph tdd_cycle {
    rankdir=LR;
    node [shape=box];

    "Escribir test (falla)" -> "Verificar que falla (RED)";
    "Verificar que falla (RED)" -> "Implementar mínimo código";
    "Implementar mínimo código" -> "Correr tests (GREEN)";
    "Correr tests (GREEN)" -> "Refactorizar";
    "Refactorizar" -> "Correr tests de nuevo";
    "Correr tests de nuevo" -> "Escribir test (falla)" [label="siguiente feature"];
}
```

| Prohibido | Alternativa obligatoria |
|-----------|------------------------|
| `unittest.mock`, `patch`, `MagicMock` | Contenedor real de DB via Testcontainers |
| `pytest-mock`, `monkeypatch` | Servicio real en `docker-compose.test.yml` |
| `Moq`, `NSubstitute` (C#) | Testcontainers + base de datos real |
| `Mockito` (Java) | Testcontainers + infraestructura real |

```bash
docker-compose -f docker-compose.test.yml up -d
docker exec <nombre_servicio> pytest          # Python
docker exec <nombre_servicio> mvn test        # Java
docker exec <nombre_servicio> dotnet test     # C#
```


### Rama Única por Repo — `develop` ⭐

<HARD-GATE>
En TODOS los repos de este monorepo —el meta-repo `enid` y cada servicio/frontend anidado
(service-store, enid-store, service_leads, service_stock, service-faqs, service-landings,
service-oauth, service-references, reverse_proxy_nginx, service-notifications, etc.)— se
trabaja SIEMPRE y ÚNICAMENTE sobre la rama `develop`.

- NUNCA crear otras ramas (nada de `feature/...`, `fix/...`, `tyson/beta`, etc.).
- Al terminar cada Step/Task del plan, COMMITEAR en `develop` (no dejar cambios colgando).
- Todo avance vive commiteado en `develop`. Ningún progreso se queda sin commit ni vagando
  en otra rama.

Si estás a punto de hacer `git checkout -b` o estar en una rama distinta de `develop` en
cualquier repo, DETENTE.
</HARD-GATE>

**Por qué:** los servicios son repos git anidados dentro del meta-repo `enid`. Si el código
queda sin commitear o en ramas sueltas, el avance se pierde al cambiar de contexto o hacer
`/clear`. `develop` es la ÚNICA rama de integración viva, igual en todos los repos.

### Flujo Local → Push → Prod (VPS) ⭐

<HARD-GATE>
El código SOLO se modifica en LOCAL, en la rama `develop` de cada repo (misma regla de arriba).
NUNCA se edita código directamente en el VPS (`/home/enid`). El VPS solo hace `git pull`.
Si estás a punto de editar un archivo de código por SSH en el VPS, DETENTE.
</HARD-GATE>

1. **Local:** desarrollar y probar en `develop` (docker compose local), commit por Step.
2. **Push:** `git push origin develop` en el/los repos tocados, cuando se logra algo
   verificado (tests/E2E en verde). No se pushea trabajo roto ni a medias.
3. **Prod (VPS `/home/enid`):** `git pull` en cada repo tocado y levantar con
   `docker compose` (rebuild si cambió Dockerfile o dependencias).

**Excepción:** en el VPS solo se editan archivos de entorno no versionados (`.env`).
Cualquier otro cambio nace en local y llega por pull.

**Por qué:** si se edita en el VPS, el código de prod diverge del repo y el siguiente
`git pull` choca o pisa el cambio. Local → push → pull mantiene una sola fuente de verdad.

### Process Flow — Git Workflow

```dot
digraph git_workflow {
    node [shape=box];

    "master" -> "git checkout -b feature/WI-[ID]-desc";
    "git checkout -b feature/WI-[ID]-desc" -> "Desarrollar + tests";
    "Desarrollar + tests" -> "git commit -m '#[ID]: descripción'";
    "git commit -m '#[ID]: descripción'" -> "git push origin feature/...";
    "git push origin feature/..." -> "Crear PR en Azure DevOps";
    "Crear PR en Azure DevOps" -> "Review + Merge a master" [label="aprobado"];
}
```

1. **Plan primero** — no se escribe código sin plan aprobado.
2. **Branch desde master:** `feature/WI-[ID]-descripcion` o `fix/WI-[ID]-descripcion`
3. **Commits con Work Item:** `#[WorkItemId]: descripción`
4. **PR obligatorio** — push a feature branch y crear PR.

---

## Workflow Spec → Plan → Ejecución ⭐ CRÍTICO

<HARD-GATE>
ANTES de escribir cualquier código verifica:
1. ¿Existe un spec aprobado? Si NO → pide el spec al usuario. No hay plan sin spec.
2. ¿Existe un plan en docs/plans/? Si NO → crea el plan primero. No hay código sin plan.
3. ¿Leíste el plan y ubicaste el siguiente step? Si NO → lee el plan AHORA.
No escribas ni una línea de código sin haber confirmado los tres puntos.
</HARD-GATE>

### Process Flow — Spec → Plan → Ejecución

```dot
digraph spec_plan_exec {
    node [shape=box];

    "Spec aprobado" -> "Crear plan en docs/plans/";
    "Crear plan en docs/plans/" -> "Ejecutar Step 1";
    "Ejecutar Step 1" -> "Marcar [x] en plan";
    "Marcar [x] en plan" -> "Commit checkpoint";
    "Commit checkpoint" -> "/clear";
    "/clear" -> "Leer plan (SIGUIENTE step)" [label="nueva sesión"];
    "Leer plan (SIGUIENTE step)" -> "Ejecutar Step N";
    "Ejecutar Step N" -> "Marcar [x] en plan";
}
```

**Orden obligatorio:**

1. **Spec primero** — documento aprobado. Sin spec no hay plan.
2. **Plan después** — Tasks con Steps y checkboxes `[ ]`. Sin plan no hay código.
3. **Ejecución step a step** — un Step por sesión. Al terminar: `[x]`, commit, `/clear`.

### Estructura del Plan

**Ubicación:** `docs/plans/YYYY-MM-DD-nombre-feature.md`

```markdown
# [Nombre Feature] — Plan de Implementación

**Spec:** [ruta al doc de diseño]
**Work Item:** #[ID]
**Branch:** feature/WI-[ID]-[descripcion]

## Task 1: [Nombre]

- [ ] **Step 1: [acción concreta]**
  - Archivos: `ruta/al/archivo.py`
  - Esperado: [resultado verificable]

---
**Progreso:** 0/N Steps (0%)
```

### Checkpoint Obligatorio (antes de /clear)

```bash
# 1. Marcar step: [ ] → [x] ✅ (YYYY-MM-DD HH:MM) y señalar ⏸️ SIGUIENTE
# 2. Commit
git add <archivos-del-step>
git commit -m "#[WI]: Step N - descripción"
# 3. /clear
```

### Al Iniciar Sesión Nueva ⭐

<HARD-GATE>
ANTES de escribir código en una sesión nueva, ejecuta esto y declara el resultado:
  cat docs/plans/[plan-file].md | grep -A5 "⏸️ SIGUIENTE"
  git log --oneline -3
Declara explícitamente: "Próximo step: [N] — toca [archivo X]".
PROHIBIDO escribir código sin haber hecho este review.
</HARD-GATE>

---

## docker-compose.test.yml — Tests con Testcontainers

El archivo `docker-compose.test.yml` es exclusivamente para correr tests de integración con testcontainers. Requiere montar el docker socket para que el contenedor pueda levantar subcontenedores.

```yaml
services:
  backend-test:
    build: .
    container_name: <servicio>-test
    volumes:
      - .:/app
      - /var/run/docker.sock:/var/run/docker.sock  # ← obligatorio para testcontainers
    environment:
      - APP_ENV=test
    command: tail -f /dev/null
```

Flujo de test:

```bash
docker-compose -f docker-compose.test.yml up -d
docker exec <servicio>-test pytest tests/ -v
docker-compose -f docker-compose.test.yml down
```

---

---

## Reverse Proxy nginx — CORS y Routing

### Arquitectura local

```
Browser (localhost)
  │
  ├─ puerto 80  → nginx → localhost:5173 (frontend Vue/React)
  └─ puerto 8000 → nginx → microservicios (8083, 8085–8089)
```

nginx corre con `network_mode: host` → accede a los servicios en `localhost:<puerto>`.

---

### Problema 1: Path mismatch entre frontend y nginx

El frontend llama sin prefijo (`/enid/`, `/oauth/`, `/lead/`).  
nginx debe rutar **sin `/api/`** y hacer strip del segmento de namespace:

```nginx
# ✅ CORRECTO — strip /enid/, upstream recibe /categorias/
location /enid/ {
    proxy_pass http://localhost:8085/;
}

# ❌ MAL — el frontend nunca llama /api/enid/
location /api/enid/ {
    proxy_pass http://localhost:8085/;
}
```

**Regla:** el nombre del `location` block = el prefijo que usa el frontend en sus llamadas axios.

**Excepción — cuando el servicio incluye el prefijo en sus propias rutas** (ej. service-landings expone `landings/templates/`):

```nginx
# Mantener prefijo: /landings/X → upstream recibe /landings/X
location /landings/ {
    proxy_pass http://localhost:8088/landings/;
}
```

Mapa completo de este proyecto:

| Frontend llama | nginx location | upstream:puerto | Strip prefix |
|---|---|---|---|
| `/enid/*` | `/enid/` | 8085 | sí → `/*` |
| `/oauth/*` | `/oauth/` | 8083 | sí → `/*` |
| `/logout/` | `/logout/` | 8083 | no → `/logout/` |
| `/lead/*` | `/lead/` | 8086 | sí → `/*` |
| `/stock/*` | `/stock/` | 8087 | sí → `/*` |
| `/landings/*` | `/landings/` | 8088 | mantiene → `/landings/*` |
| `/faqs/*` | `/faqs/` | 8089 | sí → `/*` |
| `/references/*` | `/references/` | 8082 | sí → `/*` |

---

### Problema 2: CORS bloqueado

**Causa raíz:** los servicios Django tienen `CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='').split(',')`. Si la env var está vacía → lista `['']` → Django no agrega headers → browser bloquea.

**Solución: centralizar CORS en nginx** (no en cada servicio).

```nginx
# 1. Reflejar el origin del request (compatible con credentials: true)
map $http_origin $cors_origin {
    default                 "";
    "http://localhost"      "http://localhost";
    "http://localhost:5173" "http://localhost:5173";
}

server {
    listen 8000;

    # 2. Eliminar headers CORS del upstream para evitar duplicados
    proxy_hide_header Access-Control-Allow-Origin;
    proxy_hide_header Access-Control-Allow-Credentials;
    proxy_hide_header Access-Control-Allow-Methods;
    proxy_hide_header Access-Control-Allow-Headers;

    location /enid/ {
        # 3. Responder OPTIONS (preflight) sin llegar al upstream
        if ($request_method = OPTIONS) {
            add_header Access-Control-Allow-Origin $cors_origin;
            add_header Access-Control-Allow-Credentials true;
            add_header Access-Control-Allow-Methods 'GET, POST, PUT, PATCH, DELETE, OPTIONS';
            add_header Access-Control-Allow-Headers 'Authorization, Content-Type, X-Store-Id';
            return 204;
        }
        # 4. Agregar CORS en cada respuesta real
        add_header Access-Control-Allow-Origin $cors_origin always;
        add_header Access-Control-Allow-Credentials true always;
        add_header Access-Control-Allow-Methods 'GET, POST, PUT, PATCH, DELETE, OPTIONS' always;
        add_header Access-Control-Allow-Headers 'Authorization, Content-Type, X-Store-Id' always;

        proxy_pass http://localhost:8085/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    # ... mismo patrón para cada location
}
```

**Por qué `$cors_origin` y no `*`:**  
`Access-Control-Allow-Credentials: true` es incompatible con `Access-Control-Allow-Origin: *`. El `map` refleja el origin exacto del request → mismo efecto que `*` pero compatible con credentials.

**Por qué `proxy_hide_header`:**  
Si un servicio upstream (ej. service-landings con `CORS_ALLOW_ALL_ORIGINS = True`) ya agrega sus propios headers CORS, se duplican y el browser rechaza la respuesta. `proxy_hide_header` a nivel server elimina los upstream antes de que nginx agregue los suyos.

---

### Diagnóstico rápido cuando hay errores CORS/routing

```bash
# 1. ¿OPTIONS preflight responde 204?
curl -s -o /dev/null -w "%{http_code}" -X OPTIONS http://localhost:8000/<ruta>/ \
  -H "Origin: http://localhost" -H "Access-Control-Request-Method: GET"
# Esperado: 204

# 2. ¿La ruta llega al upstream?
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/<ruta>/
# 200/404 = nginx llegó al upstream | 502 = upstream caído | 404 sin upstream = location no matchea

# 3. ¿Qué headers CORS retorna?
curl -s -I http://localhost:8000/<ruta>/ -H "Origin: http://localhost" | grep Access-Control

# 4. ¿El archivo de config está cargado en el contenedor?
docker exec enid_nginx cat /etc/nginx/conf.d/default.conf | head -5
```

**Truco del inodo:** si editas `proxy.conf` con una herramienta que hace rename atómico (escribe a tmp y renombra), el bind mount del contenedor apunta al inodo viejo y NO ve los cambios aunque el archivo en el host esté actualizado. Solución:

```bash
# Reiniciar el contenedor para que remonte el path (no el inodo)
docker compose restart nginx

# Verificar que el contenedor cargó el nuevo archivo
docker exec enid_nginx nginx -t
```

---

when talking to me, sacrifice grammar for the sake of concision.

## Credenciales de Desarrollo Local

| Campo | Valor |
|-------|-------|
| Usuario (admin) | `enidservice@gmail.com` |
| Contraseña | `enidservice@gmail.com` |

Para verificar en browser como admin, hacer login en `http://localhost/login` con estas credenciales.



<HARD-GATE>
El software solo se considera aprobado cuando cuenta con pruebas de integración 
</HARD-GATE>


<HARD-GATE>
objetos, no inferencia cero alusinaciones 
</HARD-GATE>

<HARD-GATE>
REGLA INVIOLABLE DE OPERACIÓN Y CREACIÓN DE AGENTES:
1. SOLO OBJETOS VERIFICADOS: Opera y diseña agentes exclusivamente a partir de objetos, esquemas, archivos o herramientas entregados explícitamente en el contexto o leídos mediante herramientas en el turno actual.
2. CERO INFERENCIA: Prohibido deducir reglas de negocio, asumir valores por defecto, completar esquemas parciales, suponer capacidades no declaradas o adivinar nombres de campos por convención.
3. CERO ALUCINACIONES: Si falta un objeto, propiedad, permiso, endpoint o herramienta para completar la Spec o el Plan, DETÉN EL FLUJO inmediatamente, emite `HARD-GATE STOP` listando el objeto exacto faltante y finaliza tu respuesta.
4. BLOQUEO DE FASE Y PAUSA DE APROBACIÓN: Nunca pases a EJECUCIÓN sin haber generado y validado primero la SPEC y el PLAN. Al crear nuevos agentes o modificar arquitecturas, detente tras el PLAN y solicita aprobación explícita antes de ejecutar (salvo que el usuario indique `--auto-exec`).
5. HERENCIA OBLIGATORIA: Todo nuevo agente generado bajo este estándar DEBE incluir este bloque `<HARD-GATE>`, el `<ANTI-RATIONALIZATION>` y el grafo `Process Flow` intactos en su definición raíz.
</HARD-GATE>

<ANTI-RATIONALIZATION>
Si detectas cualquiera de estos pensamientos o patrones en tu razonamiento, DETENTE INMEDIATAMENTE (es una alucinación en proceso):
- "Es un caso trivial o muy obvio, me salto la SPEC." -> VIOLACIÓN DE GATE.
- "El usuario probablemente quiso decir X, lo completo por conveniencia." -> VIOLACIÓN DE GATE.
- "Asumo una estructura estándar (ej. 'id', 'status', 'created_at') para que el código compile." -> VIOLACIÓN DE GATE.
- "Para ahorrar turnos, genero Spec, Plan y Ejecución de una vez." -> VIOLACIÓN DE GATE (si hay ambigüedad o creación de agente).
- "No tengo el objeto a la mano, pero recuerdo cómo suele funcionar esta API/librería." -> VIOLACIÓN DE GATE.
</ANTI-RATIONALIZATION>

### Process Flow — Spec → Plan → Ejecución

```dot
digraph agent_meta_standard {
    rankdir=LR;
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];
    edge [fontname="Helvetica", fontsize=10];

    // Entrada
    Objects [label="Objetos Base\n(Contexto / Schemas / Tools)", fillcolor="#E3F2FD", color="#1565C0"];

    // Fases
    Spec [label="1. SPEC\nInventario literal de objetos,\ntipos y restricciones", fillcolor="#F3E5F5", color="#6A1B9A"];
    Plan [label="2. PLAN\nGrafo de pasos deterministas\n(1 paso = 1 objeto validado)", fillcolor="#FFF3E0", color="#EF6C00"];
    Approval [label="PAUSA HITL\nEsperar aprobación\n(salvo --auto-exec)", shape=hexagon, fillcolor="#E0F7FA", color="#00838F"];
    Exec [label="3. EJECUCIÓN\nOutput exacto o Definición\ndel Nuevo Agente con Hard-Gate", fillcolor="#E8F5E9", color="#2E7D32"];

    // Compuertas de Control
    Gate_Spec [label="¿100% Objetos\nVerificados?", shape=diamond, fillcolor="#FFF9C4", color="#FBC02D"];
    Gate_Plan [label="¿Cero Inferencia\ny Trazabilidad 1:1?", shape=diamond, fillcolor="#FFF9C4", color="#FBC02D"];
    Gate_Inherited [label="¿Agente hijo hereda\n<HARD-GATE> + DOT?", shape=diamond, fillcolor="#FFF9C4", color="#FBC02D"];

    // Estado de Bloqueo
    Halt [label="HARD-GATE STOP\nBloqueo inmediato:\nListar objetos faltantes", shape=octagon, fillcolor="#FFEBEE", color="#C62828"];

    // Transiciones
    Objects -> Spec [label="Lectura literal"];
    Spec -> Gate_Spec;
    Gate_Spec -> Plan [label="SÍ"];
    Gate_Spec -> Halt [label="NO (Falta objeto)"];

    Plan -> Gate_Plan;
    Gate_Plan -> Approval [label="SÍ (Modo Creación)"];
    Gate_Plan -> Exec [label="SÍ (--auto-exec)"];
    Gate_Plan -> Halt [label="NO (Inferencia detectada)"];

    Approval -> Exec [label="Aprobado"];
    Approval -> Halt [label="Rechazado / Cambios"];

    Exec -> Gate_Inherited [label="Si genera agente"];
    Gate_Inherited -> Halt [label="NO (Violación estándar)"];
}
```


<HARD-GATE>
REGLA INVIOLABLE DE DESARROLLO Y VERIFICACIÓN E2E:
1. SOLO OBJETOS Y ENTORNOS VERIFICADOS: Desarrolla y prueba exclusivamente contra contratos, esquemas, endpoints, selectores DOM y comandos E2E entregados en el contexto o leídos mediante herramientas.
2. CERO INFERENCIA DE SELECTORES O RUTAS: Prohibido adivinar rutas de API, variables de entorno, puertos, credenciales o selectores UI (`data-testid`, clases, IDs). Si no están en los objetos base, detén el flujo.
3. CERO ALUCINACIONES DE RESULTADOS ("MOCKED PASS"): Prohibido afirmar que un flujo funciona basándose en lectura estática del código o simulando salidas en texto. Un desarrollo sin ejecución E2E real y log de salida verificado es un FALLO.
4. BLOQUEO DE ENTREGA (NO E2E = NO DONE): Ningún código o agente puede marcarse como completado sin haber ejecutado el suite E2E definido en la SPEC y obtenido exit code `0` (o validación explícita de todos los criterios de aceptación).
5. HERENCIA OBLIGATORIA: Todo agente o pipeline creado bajo este estándar DEBE incluir este `<HARD-GATE>`, el `<ANTI-RATIONALIZATION>` y el grafo `Process Flow` intactos.
</HARD-GATE>

<ANTI-RATIONALIZATION>
Si detectas cualquiera de estos pensamientos o excusas, DETENTE INMEDIATAMENTE (es una violación de calidad E2E):
- "El código es muy sencillo y claramente compila, no hace falta correr E2E." -> VIOLACIÓN DE GATE.
- "No tengo acceso al servidor levantado, así que asumo que el endpoint responde 200 OK." -> VIOLACIÓN DE GATE (Emite HARD-GATE STOP).
- "Las pruebas unitarias pasaron, con eso es suficiente." -> VIOLACIÓN DE GATE (Unitario != E2E).
- "Invento un `data-testid='submit-btn'` porque aún no leo el componente frontend." -> VIOLACIÓN DE GATE.
- "Fallo el E2E por un timeout, seguro es tema del entorno y doy la tarea por terminada." -> VIOLACIÓN DE GATE (Debe volver a Ejecución y re-verificar).
</ANTI-RATIONALIZATION>

### Process Flow — Spec → Plan → Ejecución → E2E

```dot
digraph dev_e2e_standard {
    rankdir=LR;
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];
    edge [fontname="Helvetica", fontsize=10];

    // Entrada
    Objects [label="Objetos Base\n(Contratos / Repo / Entorno E2E)", fillcolor="#E3F2FD", color="#1565C0"];

    // Fases
    Spec [label="1. SPEC\nObjetos, rutas reales y\ncriterios E2E verificables", fillcolor="#F3E5F5", color="#6A1B9A"];
    Plan [label="2. PLAN\nPasos de implementación +\nCasos de prueba E2E exactos", fillcolor="#FFF3E0", color="#EF6C00"];
    Exec [label="3. EJECUCIÓN\nImplementación de código\ny scripts E2E (sin mocks)", fillcolor="#E8F5E9", color="#2E7D32"];
    E2E [label="4. VERIFICACIÓN E2E\nEjecución real de extremo\na extremo + captura de logs", fillcolor="#E0F2F1", color="#00695C"];
    Done [label="DONE / ENTREGA\nCódigo + Evidencia E2E\n(Exit Code 0)", shape=doubleoctagon, fillcolor="#DCEDC8", color="#33691E"];

    // Compuertas de Control
    Gate_Spec [label="¿Contratos y\ncomando E2E\nverificados?", shape=diamond, fillcolor="#FFF9C4", color="#FBC02D"];
    Gate_Plan [label="¿100% trazable\ny cero suposiciones?", shape=diamond, fillcolor="#FFF9C4", color="#FBC02D"];
    Gate_E2E [label="¿E2E ejecutado\nrealmente y\n100% PASS?", shape=diamond, fillcolor="#FFF9C4", color="#FBC02D"];

    // Estado de Bloqueo
    Halt [label="HARD-GATE STOP\nBloqueo inmediato:\nFaltan objetos o entorno E2E", shape=octagon, fillcolor="#FFEBEE", color="#C62828"];

    // Transiciones
    Objects -> Spec [label="Inspección literal"];
    Spec -> Gate_Spec;
    Gate_Spec -> Plan [label="SÍ"];
    Gate_Spec -> Halt [label="NO (Falta objeto/runner)"];

    Plan -> Gate_Plan;
    Gate_Plan -> Exec [label="SÍ"];
    Gate_Plan -> Halt [label="NO (Inferencia)"];

    Exec -> E2E [label="Despliegue / Run"];
    E2E -> Gate_E2E;
    Gate_E2E -> Done [label="SÍ (Evidencia real)"];
    Gate_E2E -> Exec [label="NO (Fix & Re-test)"];
}
```

<HARD-GATE>
REGLA INVIOLABLE CERO MOCKS (SOLO INFRAESTRUCTURA REAL):
1. PROHIBICIÓN ABSOLUTA DE SIMULACIONES: Queda estrictamente prohibido crear, importar o utilizar `mocks`, `stubs`, `spies`, `fakes`, servidores simulados (`msw`, `nock`, `wiremock`), bases de datos en memoria (`sqlite :memory:`, `mongodb-memory-server`) o funciones dummy con datos hardcodeados.
2. OBJETOS E INFRAESTRUCTURA REAL: Todo código y prueba debe conectarse a instancias reales y verificadas (servicios activos, contenedores Docker de prueba, bases de datos reales o entornos staging) declarados explícitamente en los objetos de entrada.
3. BLOQUEO POR FALTA DE ENTORNO: Si una dependencia externa, credencial, contenedor o base de datos real no está disponible o levantada, DETÉN EL FLUJO inmediatamente y emite `HARD-GATE STOP: Infraestructura real no disponible [Nombre_Servicio]`. Nunca sustituyas una dependencia caída con un mock.
4. VERIFICACIÓN DE ESTADO PERSISTIDO: Ninguna prueba se considera válida si solo verifica que "se llamó a una función". Toda verificación debe comprobar el efecto real en el sistema (ej. registro escrito en la DB real, archivo creado en disco, respuesta HTTP real del servicio destino).
5. HERENCIA OBLIGATORIA: Todo agente o flujo generado bajo este estándar DEBE heredar este `<HARD-GATE>`, el `<ANTI-RATIONALIZATION>` y el grafo `Process Flow` intactos.
</HARD-GATE>

<ANTI-RATIONALIZATION>
Si detectas cualquiera de estas excusas o patrones en tu razonamiento, DETENTE INMEDIATAMENTE (es una violación de integridad real):
- "Uso `jest.mock()` / `unittest.mock` / `sinon` para aislar la lógica y que corra más rápido." -> VIOLACIÓN DE GATE (El aislamiento con mocks oculta fallos reales).
- "La base de datos o API externa no está levantada, así que creo un mock temporal para avanzar." -> VIOLACIÓN DE GATE (Emite HARD-GATE STOP).
- "Uso SQLite en memoria en lugar de PostgreSQL/MySQL real para simplificar." -> VIOLACIÓN DE GATE (Motores distintos tienen comportamientos distintos).
- "Retorno un JSON estático simulando la respuesta del servicio." -> VIOLACIÓN DE GATE.
- "Verifico con `expect(repo.save).toHaveBeenCalled()` en vez de consultar la base de datos." -> VIOLACIÓN DE GATE (Eso prueba el mock, no el sistema).
</ANTI-RATIONALIZATION>

### Process Flow — Spec → Plan → Ejecución → Verificación Real (Zero-Mocks)

```dot
digraph zero_mocks_standard {
    rankdir=LR;
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];
    edge [fontname="Helvetica", fontsize=10];

    // Entrada
    Infra [label="Objetos & Infra Real\n(DB viva / Servicios / Env)", fillcolor="#E3F2FD", color="#1565C0"];

    // Fases
    Spec [label="1. SPEC\nInventario de objetos +\nEndpoints/DBs reales activos", fillcolor="#F3E5F5", color="#6A1B9A"];
    Plan [label="2. PLAN\nFlujo de datos real\n(Cero capas simuladas)", fillcolor="#FFF3E0", color="#EF6C00"];
    Exec [label="3. EJECUCIÓN\nCódigo y tests conectados\na infraestructura real", fillcolor="#E8F5E9", color="#2E7D32"];
    Verify [label="4. AUDITORÍA & RUN\nEscaneo anti-mocks +\nEjecución contra sistema vivo", fillcolor="#E0F2F1", color="#00695C"];
    Done [label="DONE / VERIFICADO\n0 Mocks + Evidencia\nde estado real", shape=doubleoctagon, fillcolor="#DCEDC8", color="#33691E"];

    // Compuertas de Control
    Gate_Infra [label="¿Infraestructura real\nconectada y viva?", shape=diamond, fillcolor="#FFF9C4", color="#FBC02D"];
    Gate_Plan [label="¿100% dependencias\nreales en el plan?", shape=diamond, fillcolor="#FFF9C4", color="#FBC02D"];
    Gate_NoMocks [label="¿0 imports/uso de mocks\n+ Efecto real verificado?", shape=diamond, fillcolor="#FFF9C4", color="#FBC02D"];

    // Estado de Bloqueo
    Halt [label="HARD-GATE STOP\nBloqueo inmediato:\nFalta servicio real o\nse detectó un MOCK", shape=octagon, fillcolor="#FFEBEE", color="#C62828"];

    // Transiciones
    Infra -> Spec [label="Lectura literal"];
    Spec -> Gate_Infra;
    Gate_Infra -> Plan [label="SÍ (Conexión verificada)"];
    Gate_Infra -> Halt [label="NO (Servicio caído/faltante)"];

    Plan -> Gate_Plan;
    Gate_Plan -> Exec [label="SÍ (Cero mocks)"];
    Gate_Plan -> Halt [label="NO (Propone mock/stub)"];

    Exec -> Verify [label="Ejecución real"];
    Verify -> Gate_NoMocks;
    Gate_NoMocks -> Done [label="SÍ (Limpio y real)"];
    Gate_NoMocks -> Halt [label="NO (Mock detectado)"];
}
```

<HARD-GATE>
REGLA INVIOLABLE DE DATOS SEED (DATOS INICIALES REALES Y DETERMINISTAS):
1. SOLO SEEDS EXPLÍCITOS Y VERIFICADOS: Toda prueba debe ejecutarse contra datos `seed` reales definidos en archivos/scripts explícitos (`.sql`, `.json`, seeders de ORM, fixtures reales) entregados en el contexto o leídos mediante herramientas.
2. CERO INFERENCIA DE REGISTROS: Prohibido inventar IDs, correos, tokens, estados o relaciones asumiendo "que ya existen en la base de datos". Si el dato no está definido en el script de seed y cargado en el entorno real, no existe.
3. CERO ALUCINACIONES DE ESTADO INICIAL: Prohibido ejecutar pruebas sobre una base de datos vacía esperando que pasen por arte de magia, o escribir datos "al vuelo" dentro del test sin declararlos en la SPEC.
4. PRECONDICIÓN DE CARGA Y LIMPIEZA (SEED → RUN → CLEANUP): Ninguna prueba puede ejecutarse sin confirmar primero que el script `seed` se aplicó exitosamente sobre la infraestructura real (`exit code 0`), y debe garantizar estado determinista (idempotencia/reset controlado) antes de cada corrida.
5. HERENCIA OBLIGATORIA: Todo agente o pipeline creado bajo este estándar DEBE incluir este `<HARD-GATE>`, el `<ANTI-RATIONALIZATION>` y el grafo `Process Flow` intactos.
</HARD-GATE>

<ANTI-RATIONALIZATION>
Si detectas cualquiera de estas excusas o patrones en tu razonamiento, DETENTE INMEDIATAMENTE (es una violación de integridad de datos):
- "Uso `user_id = 1` asumiendo que es el administrador por defecto." -> VIOLACIÓN DE GATE (El ID debe provenir del objeto Seed verificado).
- "No hay script de seed, así que inserto datos improvisados con `faker` o valores aleatorios dentro del test." -> VIOLACIÓN DE GATE (Los datos aleatorios rompen el determinismo).
- "La base de datos ya tiene datos de pruebas anteriores, corro los tests encima de eso." -> VIOLACIÓN DE GATE (Estado contaminado = falsos positivos/negativos).
- "Simulo el objeto que devolvería el seed en memoria para no tocar la DB." -> VIOLACIÓN DE GATE (Violación Zero-Mocks + Zero-Seed).
- "Falta el archivo seed de este módulo, pero deduzco los campos obligatorios por el esquema." -> VIOLACIÓN DE GATE (Emite HARD-GATE STOP).
</ANTI-RATIONALIZATION>

### Process Flow — Spec → Plan → Seed → Ejecución & Verificación

```dot
digraph deterministic_seed_standard {
    rankdir=LR;
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];
    edge [fontname="Helvetica", fontsize=10];

    // Entrada
    Objects [label="Objetos Base\n(Esquemas + Scripts Seed + DB Real)", fillcolor="#E3F2FD", color="#1565C0"];

    // Fases
    Spec [label="1. SPEC\nInventario de entidades Seed,\nIDs reales y comando de carga", fillcolor="#F3E5F5", color="#6A1B9A"];
    Plan [label="2. PLAN\nSecuencia: Reset -> Seed ->\nTest E2E -> Verificación", fillcolor="#FFF3E0", color="#EF6C00"];
    SeedExec [label="3. CARGA DE SEED\nEjecución de seeders reales\nen DB/Entorno activo", fillcolor="#E1F5FE", color="#0277BD"];
    TestExec [label="4. EJECUCIÓN DE PRUEBAS\nTests deterministas leyendo\nlos registros del Seed", fillcolor="#E8F5E9", color="#2E7D32"];
    Done [label="DONE / VERIFICADO\nSeed aplicado + Tests PASS\nsobre datos reales", shape=doubleoctagon, fillcolor="#DCEDC8", color="#33691E"];

    // Compuertas de Control
    Gate_Spec [label="¿Archivos Seed y\ncomando verificados?", shape=diamond, fillcolor="#FFF9C4", color="#FBC02D"];
    Gate_Plan [label="¿100% referencias\ntrazables al Seed?", shape=diamond, fillcolor="#FFF9C4", color="#FBC02D"];
    Gate_Seeded [label="¿Seed cargado sin\nerrores en DB real?", shape=diamond, fillcolor="#FFF9C4", color="#FBC02D"];
    Gate_Pass [label="¿Assertions contra\ndatos Seed = PASS?", shape=diamond, fillcolor="#FFF9C4", color="#FBC02D"];

    // Estado de Bloqueo
    Halt [label="HARD-GATE STOP\nBloqueo inmediato:\nFalta script Seed o falló carga", shape=octagon, fillcolor="#FFEBEE", color="#C62828"];

    // Transiciones
    Objects -> Spec [label="Lectura literal"];
    Spec -> Gate_Spec;
    Gate_Spec -> Plan [label="SÍ"];
    Gate_Spec -> Halt [label="NO (Falta Seed/DB)"];

    Plan -> Gate_Plan;
    Gate_Plan -> SeedExec [label="SÍ (Determinista)"];
    Gate_Plan -> Halt [label="NO (Dato inventado)"];

    SeedExec -> Gate_Seeded;
    Gate_Seeded -> TestExec [label="SÍ (DB poblada)"];
    Gate_Seeded -> Halt [label="NO (Error en Seed)"];

    TestExec -> Gate_Pass;
    Gate_Pass -> Done [label="SÍ (Evidencia real)"];
    Gate_Pass -> Halt [label="NO (Fallo en test)"];
}
```