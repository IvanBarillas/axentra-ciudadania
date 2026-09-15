# Panel del ciudadano y flujo de solicitudes de trámites

Este documento registra una decisión de producto/arquitectura discutida
con el cliente (Mario), no implementada — queda para que otro agente la
resuelva. No modifica código ni estructura de `ciudadania` por sí solo.

## Contexto: por qué existe este documento

Mientras se construía la primera integración real entre
`axentra-mod-situaciones-de-vida` y `axentra-mod-tramites` (un paso de
una situación de vida ahora enlaza de verdad al trámite público
correspondiente — ver `situaciones_de_vida/templatetags/
tramites_integracion.py` en ese repo), surgió la pregunta lógica
siguiente: si un ciudadano tiene sesión, ¿dónde ve "sus" trámites y
situaciones en curso?

La respuesta honesta, verificada contra el código real de los tres
repos (`ciudadania`, `axentra-mod-tramites`, `axentra-mod-situaciones-de-vida`):
**hoy no existe ningún lugar donde eso pueda vivir.** Este documento
propone, en orden de prioridad, qué construir para que exista.

## Aclaración importante: esto NO es el panel de Hub ya descartado

El README de este repo ya decidió, correctamente, que `ciudadania` **no**
debe tener panel de Hub (`module_manifest.py`/`permissions.py`) — ver
"Decisión: sin panel en el Hub (v1)". Esa decisión es sobre la consola
interna que navega el **personal** (funcionarios), y sigue siendo
correcta: un ciudadano nunca entra al Hub.

Lo que este documento propone es distinto y no contradice esa decisión:
un panel **para el propio ciudadano**, dentro de su sesión pública ya
existente (`ciudadania:cuenta`, después de `ciudadania:login`) — el
equivalente ciudadano de "Mi cuenta en el banco", no una consola
administrativa.

## Estado actual real (verificado, no supuesto)

- `ciudadania:cuenta` (`ciudadania/views.py:cuenta_view`) ya existe y ya
  es el destino real tras iniciar sesión (`login_view` redirige ahí).
  Hoy es un placeholder de 12 líneas, HTML sin estilo, con dos enlaces
  (cambiar contraseña, cambiar correo) — nada más. Es el ancla natural
  para crecer, no algo que crear desde cero.
- `axentra-mod-tramites` es, hoy, un **catálogo informativo**: ver
  detalle de un trámite, requisitos, descargar formatos, ver sedes. No
  existe ningún modelo de solicitud/expediente ni flujo de estados —
  un ciudadano no puede "iniciar" un trámite en el sentido de dejar una
  solicitud en proceso. Solo existe telemetría de visitas/descargas
  (`registrar_visita_bitacora`, `contar_descarga_view`).
- `axentra-mod-situaciones-de-vida` es, hoy, una guía de lectura: lista
  pasos y (desde hace poco) enlaza al trámite real cuando aplica. No
  hay ningún control para que el ciudadano marque un paso como hecho,
  ni conexión con `ciudadania` todavía (ni siquiera el saludo por
  nombre que ya tiene `axentra-mod-tramites` vía
  `portal/templatetags/ciudadania_integracion.py`).
- La integración `ciudadania` ↔ `axentra-mod-tramites` que sí existe
  (saludo por nombre en el navbar público) está documentada como
  **deliberadamente mínima**: "no relaciona ciudadanos con trámites —
  eso es un sistema de expedientes real, fuera de alcance" (ver el
  docstring de `ciudadano_actual_publico` en ese repo).

## Propuesta, en orden de prioridad

### 1. Panel del ciudadano (el ancla — hacer esto primero)

Convertir `ciudadania:cuenta` en un panel real: secciones "Mi cuenta"
(lo que ya hay), y espacios reservados para "Mis trámites" y "Mis
situaciones de vida" — aunque al inicio esas secciones no tengan datos
reales que mostrar. El objetivo es tener UN lugar real donde los
satélites que sí necesiten mostrarle algo al ciudadano logueado puedan
enganchar su UI, en vez de que cada satélite invente su propio "área de
ciudadano logueado" por separado.

No requiere que exista todavía el expediente (punto 2) ni el flujo de
solicitudes (punto 3) — es la pieza más barata y de mayor apalancamiento
para lo que sigue.

### 2. Expediente / línea de tiempo (evento genérico entre satélites)

Un modelo nuevo en `ciudadania` — algo como `EventoExpediente`
(ciudadano, tipo de evento, satélite de origen, referencia,
título/descripción, fecha) — con dos funciones de servicio, mismo
espíritu que `obtener_datos_publicos()`:

- `registrar_evento(ciudadano_id, ...)` — para que otros satélites
  (trámites, situaciones) escriban un evento cuando algo relevante pasa.
- `obtener_linea_de_tiempo(ciudadano_id)` — para que el panel (punto 1)
  la lea y la pinte, probablemente como timeline.

`ciudadania` es el dueño natural de este modelo porque ya es dueño de
la identidad — si cada satélite guardara su propio historial, se
repetiría el problema de fragmentación que ya se documentó para el
diseño visual de las páginas públicas (ver
`axentra-core-django/docs/apps/public-municipal-portal.md`).

Con esto, `axentra-mod-situaciones-de-vida` podría escribir un evento
liviano ("consultó/avanzó en tal situación") con relativamente poco
esfuerzo, una vez tenga detección de sesión de ciudadano (mismo patrón
que `ciudadania_integracion.py`, que **no existe todavía en este
repo** — es un prerequisito real, no solo un detalle).

### 3. Flujo real de solicitudes en `axentra-mod-tramites` (la pieza grande)

Esto fue una idea directa del cliente, discutida en la sesión que
originó este documento — vale la pena registrarla completa porque
tiene detalles concretos, no es solo "que se pueda iniciar un trámite":

- **El trámite debe estar versionado.** Cada `Tramite` necesitaría su
  propia definición de flujo (pasos, documentos requeridos por paso),
  y versionada de verdad: si cambian los requisitos de un trámite, las
  solicitudes ya en curso bajo la definición anterior no deben mutar
  solas.
- **Un modelo `Solicitud`** — instancia real: qué ciudadano, qué
  trámite (y qué versión de su definición), en qué paso va, historial
  de transiciones de estado.
- **Un modelo `Documento`** — archivo subido por el ciudadano (ej. acta
  de nacimiento, CURP), con estado propio (pendiente/aceptado/
  rechazado) y motivo cuando se rechaza (ej. "acta vencida", para que
  el ciudadano sepa qué corregir y reenviar).
- **Panel de revisión para el funcionario** — aceptar (pasa al
  siguiente paso) o rechazar (con motivo) cada documento/solicitud.
  Esto es una UI de revisión con estados reales, no un CRUD simple
  como los que ya existen en el dashboard de trámites (sedes,
  categorías, dependencias).
- **El flujo interno de un trámite es una cosa aparte del flujo de una
  situación de vida** — el cliente fue explícito en esto. Una
  "situación de vida" es una guía de lectura que apunta a trámites; el
  flujo de estados de un trámite (borrador → en validación → aceptado/
  rechazado → siguiente paso) es interno de `axentra-mod-tramites` y no
  debería modelarse ni vivir en `axentra-mod-situaciones-de-vida`.
- **Apagado elegante si `ciudadania` no está activo o no está
  instalado.** Esto es una condición explícita del cliente ("puede
  existir ciudadano o no, depende del cliente si paga o no lo quiere o
  no"): si `ciudadania` no está disponible, `axentra-mod-tramites` debe
  quedarse como está hoy — catálogo de solo consulta, sin botón de
  "iniciar trámite" — nunca romper ni degradar a medias. Mismo patrón
  ya probado de import seguro que usa `ciudadania_integracion.py`.
- El "diagramado" de los pasos de un trámite no necesita un diseñador
  visual desde el primer día — el mismo patrón de formset ordenado
  (agregar/quitar filas) ya construido para los pasos de
  `axentra-mod-situaciones-de-vida`
  (`situaciones_de_vida/templates/situaciones_de_vida/admin/partials/
  _paso_situacion_row.html` y su formset) sirve de base real para que
  un funcionario defina los pasos internos de un trámite.

## Qué NO se decidió todavía

- Si el modelo `EventoExpediente` vive tal cual o con otro nombre/forma.
- El diseño exacto de la máquina de estados de una `Solicitud`.
- Si el panel del ciudadano (punto 1) necesita su propio sistema de
  diseño o reutiliza el mismo patrón ya usado en las páginas públicas
  de `axentra-mod-situaciones-de-vida` (CSS precompilado local, sin
  CDN — ver ese repo, `situaciones_de_vida/templates/
  situaciones_de_vida/publico/_base_publica.html`).
- Prioridad relativa entre el punto 2 (expediente) y el punto 3 (flujo
  de solicitudes) más allá de "el punto 1 va primero, siempre".

## Siguiente paso sugerido

Empezar por el punto 1 (panel del ciudadano) sin comprometerse todavía
al punto 3 completo — es la pieza más barata, no depende de ninguna
otra, y le da un ancla real a todo lo demás.
