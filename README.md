# Ciudadanía

Identidad ciudadana para Axentra OS — paquete de Django instalable, **no**
una carpeta dentro de `axentra-core-django`. Se instala como dependencia
(`uv add git+...`) en cualquier instalación que decida activarlo; el Core
nunca gana código de negocio propio por esto.

## Desarrollo local

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py test
```

Usa `devproject/` como proyecto Django mínimo solo para desarrollar y
probar este paquete de forma aislada — no es lo que se despliega. Quien
instale `ciudadania` de verdad lo hace dentro de su propio proyecto
Django (p. ej. `axentra-core-django`), agregando `"ciudadania"` a
`INSTALLED_APPS` e incluyendo `ciudadania.urls` bajo el prefijo que elija.

## Estado

- [x] Modelo `Ciudadano` (UUID, correo+contraseña con Argon2, baja lógica).
- [x] Registro público (`ciudadania:registro`) + correo de verificación.
- [x] Verificación de correo por token firmado y con vencimiento (2 días).
- [x] Login propio (`ciudadania:login`) — rechaza sin correo verificado.
- [x] `obtener_datos_publicos(id)` — snapshot de solo lectura para que
      otros satélites (Trámites, Reportes) resuelvan un UUID sin importar
      el modelo `Ciudadano` (ver `services.py`).
- [ ] `module_manifest.py` / `permissions.py` — **decidido que NO aplica**
      (ver más abajo): sin panel en el Hub para v1.

## Decisión: sin panel en el Hub (v1)

El contrato de satélite de Axentra OS (`module_manifest.py` +
`permissions.py` + `axentra_module_gate`) está pensado para que
**personal** navegue el Hub interno — un ciudadano nunca entra ahí.
Cuando personal necesite ver "qué ciudadano tiene tal trámite/reporte
pendiente", esa pantalla vive dentro de **Trámites**/**Reportes** (que ya
tienen su propio panel de Hub), llamando a
`ciudadania.services.obtener_datos_publicos(id)` para pintar el
nombre/correo — nunca un panel propio de `ciudadania`. Si algún día hace
falta administrar cuentas ciudadanas en volumen, se resuelve primero con
Django Admin (superusuarios), como ya hace el Core con
`DepartmentAccessGrant` — construir un panel de Hub dedicado solo si eso
no alcanza.

## Nota real: por qué no hay `AUTH_USER_MODEL`

`axentra-core-django` ya fija `AUTH_USER_MODEL = security.User` para el
personal. Django solo admite uno por proyecto, así que `Ciudadano` nunca
puede ser ese modelo — el login de un ciudadano no usa
`django.contrib.auth.login()`/`authenticate()`. Se maneja con una llave
propia en la sesión (`request.session["ciudadano_id"]`, ver
`services.iniciar_sesion`/`ciudadano_actual`) y verificación manual de
contraseña vía `Ciudadano.check_password()` — completamente en paralelo
al sistema de auth de personal, nunca mezclado.

## Nota real: por qué el correo usa `send_mail` y no `enqueue_email`

El Core exige que todo correo pase por
`apps.shared.notifications.enqueue_email()` — pero eso es código de
`axentra-core-django`, y `ciudadania` debe poder instalarse en cualquier
proyecto Django, no solo ahí. Por eso usa el `send_mail()` estándar de
Django, respetando el `EMAIL_BACKEND` que defina quien lo instale. Si
`axentra-core-django` quiere que estos correos también pasen por su cola
de Django-Q2, lo resuelve con un `EMAIL_BACKEND` propio que delegue a
`enqueue_email` — sin tocar una línea de este paquete.

## Pendiente antes de instalarlo en `axentra-core-django` de verdad

- Repo en GitHub (por ahora solo existe localmente — decisión explícita:
  trabajo local primero).
- Definir el mecanismo real de plantillas/estilos: las de este paquete
  son HTML mínimo a propósito (sin CSS/Tailwind), pensadas para que quien
  instale el paquete las sobreescriba con su propio `templates/ciudadania/`
  si quiere otro diseño (patrón estándar de apps de Django reutilizables).
