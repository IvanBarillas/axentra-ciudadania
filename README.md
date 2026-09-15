# Ciudadanía

Identidad ciudadana para Axentra OS — paquete de Django instalable, **no**
una carpeta dentro de `axentra-core-django`. Se instala como dependencia
(`uv add git+...`) en cualquier instalación que decida activarlo; el Core
nunca gana código de negocio propio por esto.

Ver `docs/decision-separado-de-security-user.md` para el porqué de un
modelo propio en vez de reutilizar `security.User`.

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
`INSTALLED_APPS`.

## Estado

- [x] Modelo `Ciudadano` (UUID, correo+contraseña, verificación de correo).
- [ ] Registro (alta + envío de verificación).
- [ ] Login (sesión propia, ver nota de `AUTH_USER_MODEL` abajo).
- [ ] Verificación de correo.
- [ ] `module_manifest.py` / `permissions.py` — pendiente de decidir el
      alcance exacto (ver nota abajo).

## Nota real: por qué no hay `AUTH_USER_MODEL`

`axentra-core-django` ya fija `AUTH_USER_MODEL = security.User` para el
personal. Django solo admite uno por proyecto, así que `Ciudadano` nunca
puede ser ese modelo — el login de un ciudadano no puede usar
`django.contrib.auth.login()`/`authenticate()`. Se maneja con una llave
propia en la sesión (`request.session["ciudadano_id"]`) y verificación
manual de contraseña vía `django.contrib.auth.hashers` — completamente en
paralelo al sistema de auth de personal, nunca mezclado.

## Nota pendiente de confirmar con el cliente: alcance de `module_manifest.py`

El contrato de satélite de Axentra OS (`module_manifest.py` +
`permissions.py` + `axentra_module_gate`) está pensado para que **personal**
navegue el Hub interno — no aplica a las vistas públicas de registro/login
de un ciudadano (un ciudadano nunca entra al Hub). Falta decidir: ¿este
paquete incluye también un panel para que el personal busque/gestione
cuentas ciudadanas (eso sí usaría el contrato de satélite normal), o
`ciudadania` es puramente el modelo + las vistas públicas, sin ninguna
pieza visible en el Hub? Ver conversación del 2026-09-14 en el repo de
`hermes-platform` para el contexto completo de esta decisión pendiente.
