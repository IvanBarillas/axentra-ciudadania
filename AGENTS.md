# Ciudadanía (`ciudadania`) — instrucciones para agentes

Satélite del Core (`../axentra-core-django`). Reglas comunes del workspace: `../AGENTS.md`;
estado y decisiones vigentes: `../HANDOFF.md`. Decisiones y notas de diseño: `README.md` y `docs/`.

## Alcance
- Este agente edita SOLO este repo. Si necesita algo del Core u otro módulo, no lo toca:
  escribe la petición y la pasa al integrador.
- Nunca editar `../axentra-os-playground` (solo se usa para probar).

## Qué es
- Paquete `ciudadania`: identidad del ciudadano (registro, verificación de correo, login propio,
  recuperación y cambio de contraseña/correo, protección de fuerza bruta), expediente
  (documentos, `EventoExpediente`) y `SeguimientoProceso` (una instancia por cada vez que el
  ciudadano agrega un proceso de otro satélite), más el panel `/ciudadano/cuenta/` con sidebar
  dinámico por satélite.
- **Sin panel en el Hub y sin `module_manifest.py`** (decisión firme). Entra al directorio público
  por `ciudadania/public_entry.py` (`get_public_entry()`), nunca como tarjeta de personal.
- Deliberadamente NO es `AUTH_USER_MODEL` (el Core usa `security.User`) y usa `send_mail` estándar,
  no `enqueue_email()` del Core. No cambiar eso sin decisión.
- Interruptor de encendido: `CIUDADANIA_HABILITADA` (apagado = 404 en vistas públicas).
  URL pública del directorio: `CIUDADANIA_PUBLIC_BASE_URL`.

## Fronteras
- Posee: `Ciudadano`, `TipoDocumento` (con semilla), documentos, `EventoExpediente`,
  `SeguimientoProceso`, `IntentoAcceso`.
- Es agnóstico a los satélites: eventos y seguimientos guardan `satelite_origen`, `referencia` y
  `url_relativa` en texto libre; nunca importar ni conocer URLs de otro módulo.
- API pública para otros módulos: `ciudadania/services.py` (`ciudadano_actual`,
  `obtener_datos_publicos`, `iniciar_seguimiento`, `marcar_paso_en_seguimiento`,
  `concluir_seguimiento`, ...). No exponer modelos.

## Comandos
- Pruebas: `uv run python3 manage.py test ciudadania`
- CSS: `python3 tools/tailwind.py build` (fuente `assets/css/tailwind.css`, salida
  `ciudadania/static/ciudadania/css/tailwind.css`; enlazar con `{% static %}`).
- Tailwind v4 aquí: las variantes `[&_p]:` / `[&_label]:` no compilan; usar CSS plano.
- Django: un `{% block %}` no puede repetirse en el mismo template.
- Prueba en vivo: playground `:9999`, `/ciudadano/...`; ciudadano de prueba descartable, borrarlo después.

## Convenciones
- GitFlow estricto: rama `feature|fix|docs/...` desde `develop` → pruebas → merge `--no-ff` a
  `develop` → reprobar → `--ff-only` a `main` → push de ambas → borrar la rama. Nada directo a
  `main`/`develop`, ni siquiera docs.
- Migraciones: no editar las existentes; agregar nuevas.
- Comentarios solo para el porqué no obvio.

## Antes de dar algo por terminado
1. Pruebas en verde. 2. Verificado en vivo (curl con cookies o navegador). 3. Datos de prueba borrados.
