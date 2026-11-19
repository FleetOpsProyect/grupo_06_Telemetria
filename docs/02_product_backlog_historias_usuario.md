# Product Backlog Refinado — Historias de Usuario

Este documento compila de forma exhaustiva las Historias de Usuario (**HU-01** a **HU-06**) asignadas al microservicio **Telemetría y Rutas** (`grupo_06_Telemetria`), especificando sus criterios de aceptación, contratos de entrada/salida, códigos de error, persistencia en PostgreSQL (Supabase) y mensajería asíncrona sobre **AWS SNS/SQS**.

---

## HU-01: Iniciar Ruta Asociada a Asignación Activa

| Parámetro | Detalle |
| :--- | :--- |
| **Identificador** | **HU-01** |
| **Rol / Actor** | Conductor (Operario) |
| **Acción** | Requiero iniciar la ruta asociada a mi asignación activa mediante la orden de inicio. |
| **Beneficio** | Para registrar el inicio formal del viaje, fijar las coordenadas de salida en el Centro de Operaciones y permitir que el sistema vincule los consumos de combustible y la telemetría a este recorrido. |
| **Prioridad** | **Alta** |
| **Dependencias** | Validación de JWT en API Gateway (rol `CONDUCTOR`), dependencia síncrona con Asignaciones (`GET /asignaciones/{id}`, timeout `2.0 s`, Circuit Breaker) y publicación de evento `route_started_event` en AWS SNS (`fleetops-events` / `fleetops-telemetria_events`). |

### Criterios de Aceptación

1. **Parámetros del cuerpo (`POST /rutas/iniciar`):**
   * El sistema debe recibir un cuerpo JSON con el campo obligatorio `asignacion_id` (tipo texto / UUID, identificador de la asignación).
   * Si el campo está ausente, vacío o no cumple el formato esperado, el sistema debe responder `400 Bad Request` con:
     ```json
     {
       "codigo": "DATOS_INVALIDOS",
       "mensaje": "El campo asignacion_id es obligatorio"
     }
     ```
   * Si el cuerpo no es un JSON válido, debe responder `400 Bad Request` con:
     ```json
     {
       "codigo": "JSON_INVALIDO",
       "mensaje": "El formato del cuerpo JSON es inválido"
     }
     ```
   * En ningún caso de error `400` se debe crear el registro en la base de datos.

2. **Validación síncrona con Asignaciones:**
   * El sistema debe invocar síncronamente `GET /asignaciones/{id}` al microservicio de Asignaciones antes de guardar.
   * Si Asignaciones responde `404 Not Found`, Telemetría debe responder `404 Not Found` con:
     ```json
     {
       "codigo": "ASIGNACION_NO_ENCONTRADA",
       "mensaje": "No existe una asignación con id <asignacion_id>"
     }
     ```
   * Si la asignación existe pero su estado es distinto de `PENDIENTE` (ej. ya está `EN_CURSO`, `FINALIZADA` o `CANCELADA`), debe responder `409 Conflict` con:
     ```json
     {
       "codigo": "ASIGNACION_NO_PENDIENTE",
       "mensaje": "La asignación no se encuentra en estado PENDIENTE para iniciar ruta"
     }
     ```

3. **Captura y persistencia de referencias:**
   * De la respuesta síncrona exitosa de Asignaciones, Telemetría debe extraer y guardar en su tabla local `routes` los campos `vehicle_id` (`vehiculo_id`) y `driver_id` (`conductor_id`) vinculados a esa asignación.
   * Estos identificadores son indispensables para emitir los eventos hacia Vehículos, Combustible y Reportes Operativos, y permitir la trazabilidad histórica.

4. **Unicidad de ruta por asignación (409):**
   * Bajo el supuesto del MVP de que una asignación tiene una sola ruta, la columna `assignment_id` en `routes` tiene restricción `UNIQUE`.
   * Si ya existe una ruta registrada para esa asignación (en estado `EN_CURSO`, `FINALIZADA` o `INTERRUMPIDA`), debe responder `409 Conflict` con:
     ```json
     {
       "codigo": "RUTA_DUPLICADA",
       "mensaje": "Ya existe una ruta registrada para la asignación <asignacion_id>"
     }
     ```
   * Si llegan dos peticiones simultáneas con el mismo `asignacion_id`, exactamente una debe responder `201 Created` y la otra `409 Conflict`.

5. **Éxito y estado inicial (201 Created):**
   * Con datos válidos, el sistema debe guardar la ruta en la tabla `routes` con:
     * `id`: Identificador único UUID.
     * `assignment_id` (`asignacion_id`): Identificador de la asignación.
     * `vehicle_id` (`vehiculo_id`): Identificador del vehículo asociado.
     * `driver_id` (`conductor_id`): Identificador del conductor.
     * `status` (`estado`): `"EN_CURSO"`.
     * `started_at` (`hora_inicio`): Timestamp actual en UTC (formato ISO-8601).
     * `origin_latitude` / `origin_longitude`: Por defecto fija simulando salida desde el Centro de Operaciones de FleetCorp (`3.4516`, `-76.5320`).
   * Debe responder código `201 Created` con el detalle inicial de la ruta:
     ```json
     {
       "id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
       "asignacion_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
       "vehiculo_id": "a3bb189e-8bf9-3888-9912-ace4e6543001",
       "conductor_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
       "estado": "EN_CURSO",
       "hora_inicio": "2026-10-29T08:00:00Z",
       "origen_latitud": 3.4516,
       "origen_longitud": -76.5320
     }
     ```
   * Un `GET /rutas/{id}` o `GET /rutas/asignacion/{asignacion_id}` posterior debe devolver exactamente los mismos datos.

6. **Publicación de evento (`route_started_event` vía AWS SNS + Outbox):**
   * En la misma transacción ACID se registra el evento en `outbox_events` (y en `events` para auditoría) y se publica en el tópico **AWS SNS** (`fleetops-events` / `fleetops-telemetria_events`).
   * Sobre estándar (*Event Envelope*):
     ```json
     {
       "evento_id": "3b29a1f4-90e8-4c12-b34e-89a1c89f0123",
       "tipo_evento": "route_started_event",
       "origen": "fleetops-telemetria",
       "timestamp": "2026-10-29T08:00:00Z",
       "version": "1.0",
       "payload": {
         "ruta_id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
         "asignacion_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
         "vehiculo_id": "a3bb189e-8bf9-3888-9912-ace4e6543001",
         "conductor_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
         "estado": "EN_CURSO",
         "hora_inicio": "2026-10-29T08:00:00Z"
       }
     }
     ```
   * El MS Asignaciones escucha este evento desde su cola SQS para cambiar su asignación a `EN_CURSO`; Combustible y Reportes Operativos pueden actualizar su estado local mediante *Event-Carried State Transfer*.

7. **Asignaciones caída y Circuit Breaker (503 Service Unavailable):**
   * Si Asignaciones no responde dentro del timeout configurado (por variable de entorno, valor inicial `2.0 s`), responde con error 5xx o tiene el Circuit Breaker abierto, el sistema debe responder `503` con:
     ```json
     {
       "codigo": "DEPENDENCIA_NO_DISPONIBLE",
       "mensaje": "No fue posible validar la asignación, intente nuevamente"
     }
     ```
   * Tras **5 fallos consecutivos**, el sistema debe abrir el circuito durante **30 s** sin hacer llamadas salientes.

8. **Fallo de persistencia (503):**
   * Si la base de datos PostgreSQL de Telemetría no responde, debe responder `503 Service Unavailable` con:
     ```json
     {
       "codigo": "SERVICIO_NO_DISPONIBLE",
       "mensaje": "Servicio de persistencia no disponible"
     }
     ```
   * No debe emitir eventos y debe registrar el fallo en logs estructurados (y tabla `logs` cuando aplique) con nivel `ERROR`.

9. **Frontera:**
   * El conductor no envía coordenadas desde el frontend al iniciar, solo la orden de inicio.
   * Telemetría no cambia el estado de la asignación directamente; solo publica el evento en AWS SNS para que Asignaciones lo haga.

---

## HU-02: Consultar Ruta Activa e Historial Propio del Conductor

| Parámetro | Detalle |
| :--- | :--- |
| **Identificador** | **HU-02** |
| **Rol / Actor** | Conductor (Operario) |
| **Acción** | Requiero consultar la información de mi ruta activa actual y de mis rutas anteriores asociadas a mis asignaciones mediante mis credenciales autenticadas. |
| **Beneficio** | Para conocer en tiempo real el estado, horario, coordenadas y distancia de mi recorrido en curso o revisar el historial de mis trayectos finalizados e interrumpidos, garantizando mediante el middleware de autorización que solo pueda acceder a mis propias rutas. |
| **Prioridad** | **Alta** |
| **Dependencias** | Middleware de autorización JWT (rol `CONDUCTOR` y extracción de `conductor_id`). Consulta de solo lectura sobre la base de datos local sin llamadas HTTP salientes ni dependencia con Combustible (Combustible mantiene su propia réplica vía ECST). |

### Criterios de Aceptación

1. **Autorización y extracción de identidad por middleware (JWT):**
   * Toda petición a `GET /route/assignment/{asignacion_id}` o a la consulta de rutas propias del conductor (`GET /route`) debe pasar por el middleware de autorización con un token JWT válido con rol `CONDUCTOR`.
   * El sistema debe extraer el `conductor_id` directamente del token autenticado (nunca confiando en un identificador enviado libremente por el cliente en parámetros o cuerpo).
   * Si falta el token o es inválido, responde `401 Unauthorized` con `codigo: "NO_AUTENTICADO"`.

2. **Aislamiento de datos por conductor (Anti-IDOR / 403 Forbidden):**
   * Al consultar una ruta por `asignacion_id`, el sistema debe verificar que el `conductor_id` registrado en la ruta coincida con el `conductor_id` autenticado en el middleware.
   * Si la ruta existe pero pertenece a otro conductor, debe rechazar la petición respondiendo `403 Forbidden` con:
     ```json
     {
       "codigo": "ACCESO_DENEGADO",
       "mensaje": "No tiene permisos para consultar rutas de otro conductor"
     }
     ```

3. **Consulta de ruta activa o histórica por asignación (`GET /route/assignment/{asignacion_id}` - 200 OK):**
   * Si `asignacion_id` es válido y pertenece al conductor autenticado, el sistema consulta su base de datos local y responde `200 OK` con `id`, `asignacion_id`, `vehiculo_id`, `conductor_id`, `estado` (`EN_CURSO`, `FINALIZADA` o `INTERRUMPIDA`), `hora_inicio`, `hora_fin` (`null` si está `EN_CURSO`), `distancia_recorrida_km` (`null` si está `EN_CURSO`), `origen` y `destino` (`null` si está `EN_CURSO`).
   * Si `asignacion_id` está vacío o tiene formato inválido, responde `400 Bad Request` con `codigo: "DATOS_INVALIDOS"`.

4. **Consulta del historial propio de rutas del conductor (`GET /route` filtrado por middleware - 200 OK):**
   * Cuando un usuario con rol `CONDUCTOR` solicita sus rutas (activa y anteriores), el middleware de autorización restringe automáticamente la consulta al `conductor_id` del token.
   * Permite filtrar opcionalmente por `estado` (`EN_CURSO`, `FINALIZADA`, `INTERRUMPIDA`) y paginar (`page`, `size`), devolviendo los resultados ordenados descendentemente por `hora_inicio`.
   * Si el conductor aún no tiene rutas registradas, responde `200 OK` con `contenido: []` y `total: 0`.

5. **Sin ruta registrada para la asignación (404 Not Found):**
   * Si no existe ninguna ruta asociada a `asignacion_id`, responde `404 Not Found` con:
     ```json
     {
       "codigo": "RUTA_NO_ENCONTRADA",
       "mensaje": "No existe una ruta asociada a la asignación <asignacion_id>"
     }
     ```

6. **Frontera y solo lectura:**
   * La consulta se resuelve **exclusivamente contra la base de datos local de Telemetría** (cero llamadas HTTP hacia otros microservicios) y no tiene ninguna asociación con el microservicio de Combustible (que gestiona su propia réplica de datos mediante *Event-Carried State Transfer*).
   * Es una operación estrictamente de solo lectura que no muta estados ni atributos de las rutas.

7. **Rendimiento y fallo de persistencia (503 Service Unavailable):**
   * La consulta debe responder en **menos de 200 ms (P95)** y timeout máximo de `1.0 s`, respaldada por índices locales sobre `(assignment_id, status)` y `driver_id`.
   * Si la base de datos local no responde, el sistema responde `503 Service Unavailable` con `codigo: "SERVICIO_NO_DISPONIBLE"` y escribe el fallo en el log con nivel `ERROR`.

---

## HU-03: Finalizar Ruta Activa y Calcular Distancia Simulada

| Parámetro | Detalle |
| :--- | :--- |
| **Identificador** | **HU-03** |
| **Rol / Actor** | Conductor (Operario) |
| **Acción** | Requiero finalizar mi ruta activa registrando la orden de término para calcular la distancia simulada. |
| **Beneficio** | Para cerrar el viaje, generar matemáticamente los kilómetros recorridos y propagar la información para que Vehículos actualice su odómetro y Asignaciones finalice la asignación. |
| **Prioridad** | **Alta** |
| **Dependencias** | Simulación geoespacial Haversine (Patrón Strategy), cálculo de kilometraje, **Transactional Outbox** (`outbox_events`) y publicación de `route_completed_event` en AWS SNS (`fleetops-events` / `fleetops-telemetria_events`). |

### Criterios de Aceptación

1. **Parámetros del cuerpo (`POST /rutas`):**
   * El sistema debe recibir una petición en `POST /rutas` con el cuerpo JSON obligatorio conteniendo `asignacion_id` (y opcionalmente `destino_latitud`, `destino_longitud` si se proveen coordenadas simuladas desde el cliente; de lo contrario, el servidor genera el destino simulado).
   * Si `asignacion_id` no viene, debe responder `400 Bad Request` con:
     ```json
     {
       "codigo": "DATOS_INVALIDOS",
       "mensaje": "El campo asignacion_id es obligatorio"
     }
     ```
   * Si el cuerpo no es JSON válido, responde `400 Bad Request` con `codigo: "JSON_INVALIDO"`.

2. **Validación de ruta en curso (404 y 409):**
   * El sistema busca en la tabla `routes` la ruta asociada a esa `assignment_id`.
   * Si no existe ninguna ruta para esa asignación, debe responder `404 Not Found` con:
     ```json
     {
       "codigo": "RUTA_NO_ENCONTRADA",
       "mensaje": "No existe una ruta asociada a la asignación <asignacion_id>"
     }
     ```
   * Si la ruta existe pero su estado ya es `FINALIZADA` o `INTERRUMPIDA`, debe responder `409 Conflict` con:
     ```json
     {
       "codigo": "ESTADO_RUTA_INVALIDO",
       "mensaje": "La ruta no se encuentra en estado EN_CURSO para ser finalizada"
     }
     ```
   * Si llegan dos peticiones simultáneas para finalizar la misma ruta, la transición atómica garantiza que exactamente una responda `200 OK` y la otra `409 Conflict`.

3. **Simulación geoespacial (Fórmula de Haversine):**
   * El sistema captura `ended_at` (`hora_fin`, timestamp actual en UTC).
   * Recupera la coordenada de origen registrada al inicio (`lat: 3.4516, lon: -76.5320`).
   * Si no se suministran coordenadas de destino, genera una coordenada de destino simulada sumando un delta aleatorio dentro de un radio de **5 a 25 km** respecto al origen.
   * Calcula la distancia final del viaje en kilómetros mediante la fórmula matemática de Haversine (radio terrestre $R = 6371.0\text{ km}$):
     $$d = 2R \cdot \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)}\right)$$
   * El resultado `distance_traveled_km` (`distancia_recorrida_km`) se redondea a **2 decimales** (ej. `18.45 km`).
   * Si la duración entre inicio y fin es menor a 1 minuto, asigna una distancia mínima de salvaguarda de **0.50 km**.

4. **Persistencia y cambio de estado:**
   * El sistema actualiza el registro de la ruta en `routes`:
     * `status` pasa de `EN_CURSO` a `FINALIZADA`.
     * Guarda `ended_at`, `destination_latitude`, `destination_longitude` y `distance_traveled_km`.
   * **Ningún registro se elimina de la base de datos (historial inmutable).**

5. **Éxito (200 OK):**
   * Con la ruta finalizada, el sistema responde `200 OK` con el resumen completo del viaje:
     ```json
     {
       "id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
       "asignacion_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
       "estado": "FINALIZADA",
       "hora_inicio": "2026-10-29T08:00:00Z",
       "hora_fin": "2026-10-29T10:30:00Z",
       "distancia_recorrida_km": 18.45,
       "origen": {
         "latitud": 3.4516,
         "longitud": -76.5320
       },
       "destino": {
         "latitud": 3.4372,
         "longitud": -76.5225
       }
     }
     ```

6. **Publicación de evento (`route_completed_event` en AWS SNS):**
   * Dentro de la misma transacción ACID del cierre de ruta, se inserta el evento en `outbox_events` (con `publication_status = PENDING`) y el worker en segundo plano lo publica hacia el tópico **AWS SNS** (`fleetops-events` / `fleetops-telemetria_events`).
   * Sobre estándar:
     ```json
     {
       "evento_id": "7f8a912b-10c9-4b34-89d1-02b4d5e6f789",
       "tipo_evento": "route_completed_event",
       "origen": "fleetops-telemetria",
       "timestamp": "2026-10-29T10:30:00Z",
       "version": "1.0",
       "payload": {
         "ruta_id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
         "asignacion_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
         "vehiculo_id": "a3bb189e-8bf9-3888-9912-ace4e6543001",
         "conductor_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
         "estado": "FINALIZADA",
         "hora_inicio": "2026-10-29T08:00:00Z",
         "hora_fin": "2026-10-29T10:30:00Z",
         "distancia_recorrida_km": 18.45
       }
     }
     ```
   * Consumidores:
     * **Vehículos:** Suma `distancia_recorrida_km` a su `kilometraje_actual`.
     * **Asignaciones:** Pasa la asignación a `FINALIZADA`.

7. **Tolerancia a fallos de mensajería (Transactional Outbox):**
   * Si **AWS SNS** está temporalmente inaccesible, el evento queda guardado en la tabla local `outbox_events` en la misma transacción del cambio de ruta.
   * La respuesta `200 OK` al conductor **no debe fallar** si la base de datos local confirmó la transacción; el worker reintentará el envío y marcará `publication_status = PUBLISHED`.

8. **Fallo de persistencia (503):**
   * Si la base de datos local no responde, la transacción ejecuta rollback y el sistema debe responder `503 Service Unavailable` con `codigo: "SERVICIO_NO_DISPONIBLE"` sin emitir eventos.

---

## HU-04: Procesar Interrupción Imprevista de Asignación por Incidente Grave

| Parámetro | Detalle |
| :--- | :--- |
| **Identificador** | **HU-04** |
| **Rol / Actor** | Sistema (actor interno - MS Incidentes / MS Asignaciones) |
| **Acción** | Requiero procesar la interrupción imprevista de una asignación por incidente grave para cerrar la ruta y calcular la distancia parcial. |
| **Beneficio** | Para asegurar que la ruta activa quede cerrada como `INTERRUMPIDA` y los kilómetros recorridos hasta el momento del siniestro se reporten al odómetro del vehículo sin pérdida de datos. |
| **Prioridad** | **Media** |
| **Dependencias** | Reacción asíncrona ante el Proceso 2B (Gestión de Siniestros Críticos). Consumo desde cola AWS SQS `q.telemetria`, idempotencia en `processed_events` y desvío a `q.telemetria.dlq`. |

### Criterios de Aceptación

1. **Suscripción y cola (AWS SNS/SQS):**
   * El sistema debe consumir eventos mediante *polling* desde la cola **AWS SQS** `q.telemetria`, suscrita al tópico **AWS SNS** `fleetops-events`, escuchando el evento `severe_incident_reported_event` (y/o eventos de interrupción de asignación).
   * La URL/ARN de la cola y tópico, así como la región y credenciales/IAM de AWS, deben leerse obligatoriamente de variables de entorno.

2. **Validación del mensaje y sobre estándar (Tolerant Reader):**
   * El mensaje entrante debe tener el sobre estándar (`evento_id`, `tipo_evento`, `version`, `timestamp`/`fecha_evento`, `origen`, `payload`/`datos`).
   * El cuerpo del evento debe incluir obligatoriamente `asignacion_id`.
   * Los campos adicionales (como `incidente_id`, `severidad`, `coords`, `reasignacion_resultado`) deben **ignorarse sin error** (*Tolerant Reader*).
   * Si el mensaje no es JSON válido o le falta `asignacion_id`, el sistema debe desviarlo a la DLQ (`q.telemetria.dlq` en AWS SQS) sin reintentos y escribir en el log con nivel `ERROR` el `evento_id` y el campo faltante.

3. **Idempotencia (*Idempotent Consumer*):**
   * El sistema debe guardar el `evento_id` de cada evento procesado en la tabla `processed_events` (y registrar auditoría en `events`).
   * Si llega de nuevo un evento con un `evento_id` ya procesado, debe confirmarlo en SQS (`DeleteMessage`) sin cambios en la base de datos ni reprocesamiento.

4. **Búsqueda y cierre de ruta activa:**
   * El sistema consulta su tabla `routes` buscando una ruta asociada a `asignacion_id` en estado `EN_CURSO`.
   * Si no existe ninguna ruta para esa asignación, o si la ruta ya estaba `FINALIZADA` o `INTERRUMPIDA`, el sistema debe confirmar el mensaje en SQS sin error y escribir en el log con nivel `INFO` que no había ruta activa por cerrar.

5. **Cálculo parcial y transición de estado:**
   * Si la ruta está `EN_CURSO`, el sistema captura la hora actual como `ended_at` (`hora_fin`).
   * Simula una posición intermedia proporcional al tiempo transcurrido desde el inicio y calcula la distancia parcial recorrida con la fórmula de Haversine.
   * Actualiza el estado de la ruta a `INTERRUMPIDA`.
   * **Bajo ninguna circunstancia se elimina el registro de la ruta; se conserva su historial completo para auditoría y trazabilidad del incidente.**

6. **Emisión de evento con estado `INTERRUMPIDA` (`route_completed_event`):**
   * Tras guardar el cambio e insertar en `outbox_events` dentro de la misma transacción, el sistema publica en **AWS SNS** (`fleetops-events`) el evento `route_completed_event` con `estado: "INTERRUMPIDA"` y la distancia parcial calculada.
   * Efecto en otros servicios:
     * **Vehículos:** Escucha el evento y suma la distancia parcial a su `kilometraje_actual`.
     * **Asignaciones:** Al encontrarse ya en `INTERRUMPIDA_POR_INCIDENTE` por el Proceso 2B, lo descarta según sus reglas de catálogo de estados.

7. **Fallos transitorios y DLQ:**
   * Si la base de datos local no responde durante el procesamiento, el sistema debe reintentar hasta **3 veces** con espera creciente.
   * Si sigue fallando, el mensaje se envía a la DLQ `q.telemetria.dlq` en AWS SQS.
   * El mensaje solo debe eliminarse de SQS (`DeleteMessage`) después de confirmar la transacción que guarda el cambio de estado y el `evento_id` en `processed_events`.

8. **Frontera:**
   * El sistema no debe consultar síncronamente a Incidentes ni a Asignaciones, ni interactuar con talleres o grúas.
   * Su única responsabilidad es cerrar la ruta localmente y publicar los kilómetros parciales.

---

## HU-05: Consultar Listado, Detalle por Asignación y Detalle Histórico de Rutas

| Parámetro | Detalle |
| :--- | :--- |
| **Identificador** | **HU-05** |
| **Rol / Actor** | Gerencia / Administrador de Flota / Conductor / MS Reportes Operativos |
| **Acción** | Requiero consultar el listado paginado de rutas (con filtros), el detalle por identificador de ruta y el detalle por identificador de asignación. |
| **Beneficio** | Para que el conductor consulte su ruta asignada, Gerencia audite los trayectos de los vehículos y el servicio de Reportes Operativos calcule KPIs gerenciales (Proceso 6). |
| **Prioridad** | **Media** |
| **Dependencias** | Soporte síncrono al orquestador del Proceso 6 (`GET /rutas`) y consulta de ruta del conductor (`GET /rutas/asignacion/{asignacion_id}` y `GET /rutas/{id}`). |

### Criterios de Aceptación

1. **Parámetros de consulta (`GET /rutas`):**
   * El sistema debe aceptar los siguientes query params opcionales:
     * `asignacion_id` (texto, identificador de la asignación).
     * `vehiculo_id` (texto, identificador del vehículo).
     * `estado` (uno de: `EN_CURSO`, `FINALIZADA`, `INTERRUMPIDA`; sin filtro por defecto).
     * `fecha_desde` (formato `AAAA-MM-DD`).
     * `fecha_hasta` (formato `AAAA-MM-DD`).
     * `page` (entero $\ge 0$, por defecto `0`).
     * `size` (entero de `1` a `100`, por defecto `20`).
   * Si un parámetro no cumple la regla (ej. `size=0`, `size=150` o formato de fecha inválido), responde `400 Bad Request` con:
     ```json
     {
       "codigo": "DATOS_INVALIDOS",
       "mensaje": "Parámetros de consulta inválidos",
       "errores": [
         { "campo": "size", "detalle": "El tamaño debe estar entre 1 y 100" }
       ]
     }
     ```

2. **Respuesta paginada (`200 OK`):**
   * Estructura estándar obligatoria:
     ```json
     {
       "contenido": [
         {
           "id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
           "asignacion_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
           "vehiculo_id": "a3bb189e-8bf9-3888-9912-ace4e6543001",
           "distancia_recorrida_km": 18.45,
           "hora_inicio": "2026-10-29T08:00:00Z",
           "hora_fin": "2026-10-29T10:30:00Z",
           "estado": "FINALIZADA"
         }
       ],
       "page": 0,
       "size": 20,
       "total": 1
     }
     ```
   * En rutas `EN_CURSO`, `distancia_recorrida_km` y `hora_fin` retornan `null`.

3. **Orden estable y lista vacía:**
   * Resultados ordenados de forma **descendente por `started_at`** (`hora_inicio`, las rutas más recientes primero).
   * Si ninguna ruta cumple el filtro o `page` supera la última página, responde `200 OK` con `contenido: []` y `total: 0` (nunca `404`).

4. **Consulta por identificador de ruta (`GET /rutas/{id}`):**
   * Si el `id` (UUID) existe, responde `200 OK` con el objeto completo de la ruta incluyendo `conductor_id` y las coordenadas de origen y destino.
   * Si no existe, responde `404 Not Found` con `codigo: "RUTA_NO_ENCONTRADA"`.

5. **Consulta por identificador de asignación (`GET /rutas/asignacion/{asignacion_id}`):**
   * Permite al conductor o frontend consultar la información de la ruta (`EN_CURSO`, `FINALIZADA` o `INTERRUMPIDA`) asociada a una asignación específica (timeout `1.0 s`, rol `CONDUCTOR`).
   * Si existe, responde `200 OK` con los datos de la ruta.
   * Si no existe ruta asociada a esa asignación, responde `404 Not Found` con `codigo: "RUTA_NO_ENCONTRADA"`.

6. **Soporte al Proceso 6 (Reportes Operativos):**
   * `GET /rutas` es consultado síncronamente por el MS Reportes Operativos en su agregación paralela (*Scatter-Gather*) para calcular `distancia_total_recorrida_km` y `rutas_en_curso`.
   * Debe responder en **menos de 1.0 segundo** bajo carga normal, soportado por índices locales en `routes` sobre `(status, started_at)`.

7. **Fallo de persistencia (503):**
   * Si la base de datos no responde, responde `503 Service Unavailable` con `codigo: "SERVICIO_NO_DISPONIBLE"`.

---

## HU-06: Endpoint de Salud y Diagnóstico de Dependencias

| Parámetro | Detalle |
| :--- | :--- |
| **Identificador** | **HU-06** |
| **Rol / Actor** | Ingeniero de Infraestructura (DevOps / SRE) / AWS ALB |
| **Acción** | Requiero consultar el estado de salud y dependencias del microservicio de telemetría. |
| **Beneficio** | Para verificar la disponibilidad del microservicio, diagnosticar fallas de red y permitir que el balanceador de carga de AWS (ALB) y los contenedores Docker gestionen el tráfico operativo. |
| **Prioridad** | **Baja** |
| **Dependencias** | Mandatorio para probes de Docker/orquestación y balanceadores AWS ALB (timeout `150 ms`). |

### Criterios de Aceptación

1. **Acceso público y sin token:**
   * El endpoint síncrono `GET /health` debe responder sin exigir token JWT de Cognito, cabeceras de autorización ni validación de roles en el API Gateway (protegido únicamente por *Rate Limiting* en el Gateway).

2. **Sondeo activo de Base de Datos (PostgreSQL / Supabase):**
   * El sistema debe ejecutar una consulta de sondeo rápida (`SELECT 1`) contra su base de datos relacional local con un timeout de **1.0 segundo**.
   * Si la base de datos responde: `"database": "UP"`.
   * Si expira o falla: `"database": "DOWN"`.

3. **Sondeo activo de Mensajería (AWS SNS/SQS):**
   * El sistema debe verificar la conectividad y disponibilidad del servicio de mensajería **AWS SNS/SQS** (verificación de acceso al tópico `fleetops-events` y cola `q.telemetria` mediante SDK/cliente AWS) con un timeout de **1.0 segundo**.
   * Si el canal de mensajería está accesible y saludable: `"broker": "UP"`.
   * Si falla la conectividad o expira: `"broker": "DOWN"`.

4. **Éxito (`200 OK`):**
   * Si la base de datos y AWS SNS/SQS responden favorablemente:
     ```json
     {
       "status": "UP",
       "database": "UP",
       "broker": "UP",
       "timestamp": "2026-10-29T16:27:00Z"
     }
     ```

5. **Degradación o fallo de dependencias (`503 Service Unavailable`):**
   * Si la base de datos o AWS SNS/SQS fallan la prueba de conexión:
     ```json
     {
       "status": "DOWN",
       "database": "DOWN",
       "broker": "UP",
       "timestamp": "2026-10-29T16:27:00Z"
     }
     ```
   * Responde código HTTP `503` con indicador `codigo: "SERVICIO_DEGRADADO"`.

6. **Rendimiento no intrusivo:**
   * La ejecución del healthcheck debe tomar **menos de 150 milisegundos** en condiciones normales.
   * No debe dejar conexiones colgadas en el pool de SQLAlchemy ni saturar las peticiones hacia AWS SNS/SQS.
