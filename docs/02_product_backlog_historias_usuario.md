# Product Backlog Refinado — Historias de Usuario

Este documento compila de forma exhaustiva las Historias de Usuario (HU-01 a HU-06) asignadas al microservicio **Telemetría y Rutas**, especificando sus criterios de aceptación, contratos de entrada/salida, códigos de error y dependencias técnicas.

---

## HU-01: Iniciar Ruta Asociada a Asignación Activa

| Parámetro | Detalle |
| :--- | :--- |
| **Identificador** | **HU-01** |
| **Rol / Actor** | Conductor (Operario) |
| **Acción** | Requiero iniciar la ruta asociada a mi asignación activa mediante la orden de inicio. |
| **Beneficio** | Para registrar el inicio formal del viaje, fijar las coordenadas de salida en el Centro de Operaciones y permitir que el sistema vincule los consumos de combustible y la telemetría a este recorrido. |
| **Prioridad** | **Alta** |
| **Dependencias** | Dependencia síncrona con Asignaciones (`GET /asignaciones/{id}`) y emisión de evento a RabbitMQ (`telemetria.ruta.iniciada`). |

### Criterios de Aceptación

1. **Parámetros del cuerpo (`POST /rutas/iniciar`):**
   * El sistema debe recibir un cuerpo JSON con el campo obligatorio `asignacion_id` (tipo texto, identificador de la asignación).
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
   * De la respuesta síncrona exitosa de Asignaciones, Telemetría debe extraer y guardar en su base de datos local los campos `vehiculo_id` y `conductor_id` vinculados a esa asignación.
   * Estos identificadores son indispensables para emitir la finalización hacia Vehículos y permitir la trazabilidad histórica.

4. **Unicidad de ruta por asignación (409):**
   * Bajo el supuesto del MVP de que una asignación tiene una sola ruta, el sistema no debe permitir iniciar más de una ruta para la misma `asignacion_id`.
   * Si ya existe una ruta registrada para esa asignación (en estado `EN_CURSO`, `FINALIZADA` o `INTERRUMPIDA`), debe responder `409 Conflict` con:
     ```json
     {
       "codigo": "RUTA_DUPLICADA",
       "mensaje": "Ya existe una ruta registrada para la asignación <asignacion_id>"
     }
     ```
   * Si llegan dos peticiones simultáneas con el mismo `asignacion_id`, exactamente una debe responder `201 Created` y la otra `409 Conflict`.

5. **Éxito y estado inicial (201 Created):**
   * Con datos válidos, el sistema debe guardar la ruta en su base de datos con:
     * `id`: Identificador único (formato UUID o `ruta-<número>`).
     * `asignacion_id`: Identificador de la asignación.
     * `vehiculo_id`: Identificador del vehículo asociado.
     * `conductor_id`: Identificador del conductor.
     * `estado`: `"EN_CURSO"`.
     * `hora_inicio`: Timestamp actual en UTC (formato ISO-8601).
     * `coordenada_origen`: Por defecto fija simulando salida desde el Centro de Operaciones de FleetCorp:
       ```json
       {
         "latitud": 3.4516,
         "longitud": -76.5320
       }
       ```
   * Debe responder código `201 Created` con estos datos.
   * Un `GET /rutas/{id}` posterior debe devolver exactamente los mismos datos.

6. **Publicación de evento (`RutaIniciadaEvent`):**
   * Tras confirmar el guardado en base de datos, el sistema debe publicar el evento con routing key `telemetria.ruta.iniciada` en el exchange topic `fleetops.events`.
   * Sobre estándar:
     ```json
     {
       "evento_id": "evt-uuid",
       "tipo_evento": "RutaIniciadaEvent",
       "version": "1.0",
       "fecha_evento": "2026-10-05T08:00:00Z",
       "origen": "telemetria",
       "datos": {
         "ruta_id": "ruta-1001",
         "asignacion_id": "asig-8472",
         "vehiculo_id": "veh-501",
         "hora_inicio": "2026-10-05T08:00:00Z",
         "coordenada_origen": {
           "latitud": 3.4516,
           "longitud": -76.5320
         }
       }
     }
     ```
   * El MS Asignaciones escucha este evento para cambiar su asignación a `EN_CURSO`.

7. **Asignaciones caída y Circuit Breaker (503 Service Unavailable):**
   * Si Asignaciones no responde dentro del timeout configurado (por variable de entorno, valor inicial `2 s`), responde con error 5xx o tiene el Circuit Breaker abierto, el sistema debe responder `503` con:
     ```json
     {
       "codigo": "DEPENDENCIA_NO_DISPONIBLE",
       "mensaje": "No fue posible validar la asignación, intente nuevamente"
     }
     ```
   * Tras **5 fallos consecutivos**, el sistema debe abrir el circuito durante **30 s** sin hacer llamadas salientes.

8. **Fallo de persistencia (503):**
   * Si la base de datos de Telemetría no responde, debe responder `503 Service Unavailable` con:
     ```json
     {
       "codigo": "SERVICIO_NO_DISPONIBLE",
       "mensaje": "Servicio de persistencia no disponible"
     }
     ```
   * No debe emitir eventos y debe escribir el fallo en el log con nivel `ERROR`.

9. **Frontera:**
   * El conductor no envía coordenadas desde el frontend, solo la orden de inicio.
   * Telemetría no cambia el estado de la asignación directamente; solo publica el evento para que Asignaciones lo haga.

---

## HU-02: Consultar la Ruta en Curso de una Asignación para Combustible

| Parámetro | Detalle |
| :--- | :--- |
| **Identificador** | **HU-02** |
| **Rol / Actor** | Sistema (actor interno - MS Combustible) |
| **Acción** | Requiero consultar la ruta en curso de una asignación mediante sus parámetros de estado. |
| **Beneficio** | Para obtener el `ruta_id` y verificar que el vehículo esté en un recorrido activo antes de permitir el registro de tanqueos de combustible en la vía. |
| **Prioridad** | **Alta** |
| **Dependencias** | Consulta síncrona requerida por MS Combustible en el Proceso 5. Sin llamadas salientes HTTP. |

### Criterios de Aceptación

1. **Ubicación y mensaje de entrada:**
   * La acción ocurre en el consumidor asíncrono de Telemetría al escuchar la cola conectada al bus de eventos tras una solicitud de Combustible.
   * El mensaje entrante debe incluir obligatoriamente el identificador del evento, la asignación, el vehículo y el identificador de correlación de la solicitud.
   * Si el mensaje es inválido o faltan datos, se desvía a la DLQ (`q.telemetria.dlq`) sin reintentos y se registra en log con el mensaje: *"Mensaje de solicitud de tanqueo incompleto o inválido"*.

2. **Ruta activa confirmada (Aprobación - 200 OK equivalente):**
   * El sistema consulta en su base de datos local si existe una ruta para esa asignación en estado `EN_CURSO`.
   * Si existe, confirma el mensaje y publica el evento de aprobación con código HTTP lógico `200` (OK), incluyendo el código de correlación, la ruta y el vehículo hacia el bus de eventos para que Combustible autorice el tanqueo.

3. **Sin ruta activa (Rechazo - 404 Not Found / 409 Conflict):**
   * Si no existe ruta para la asignación (código lógico `404 Not Found`) o su estado es `FINALIZADA` o `INTERRUMPIDA` (código lógico `409 Conflict`), confirma el mensaje y emite un evento de rechazo con dicho código de estado y el identificador de correlación, indicando como motivo: *"No existe ruta activa en curso para la asignación"*, permitiendo que Combustible cancele el registro.

4. **Frontera y restricciones de negocio:**
   * La validación se resuelve **exclusivamente con la base de datos local de Telemetría**, con cero llamadas HTTP hacia otros servicios.
   * El microservicio tiene restringido validar costos, galones o mutar datos de la ruta; su única atribución es verificar la vigencia del viaje.

5. **Idempotencia y solo lectura:**
   * El sistema valida el identificador del evento en su tabla local `eventos_procesados`.
   * Si el mensaje ya fue atendido, se confirma de inmediato sin duplicar eventos de salida ni alterar registros en base de datos.

6. **Rendimiento:**
   * El procesamiento completo (consumo, validación local y emisión de respuesta) debe ejecutarse en **menos de 200 ms (P95)**, respaldado por un índice compuesto sobre `(asignacion_id, estado)`.

7. **Fallo de persistencia y reintentos (503 Service Unavailable):**
   * Si la base de datos local no responde durante la verificación, el mensaje se reintenta hasta **3 veces** con espera creciente.
   * Si el fallo persiste, se desvía a la DLQ (`q.telemetria.dlq`), se tipifica con código de error `503` y se escribe en el log como `ERROR` con el mensaje: *"Fallo de persistencia local al validar ruta para combustible"*.

---

## HU-03: Finalizar Ruta Activa y Calcular Distancia Simulada

| Parámetro | Detalle |
| :--- | :--- |
| **Identificador** | **HU-03** |
| **Rol / Actor** | Conductor (Operario) |
| **Acción** | Requiero finalizar mi ruta activa registrando la orden de término para calcular la distancia simulada. |
| **Beneficio** | Para cerrar el viaje, generar matemáticamente los kilómetros recorridos y propagar la información para que Vehículos actualice su odómetro y Asignaciones finalice la asignación. |
| **Prioridad** | **Alta** |
| **Dependencias** | Simulación geoespacial Haversine, cálculo de kilometraje y emisión de evento asíncrono hacia Vehículos y Asignaciones. |

### Criterios de Aceptación

1. **Parámetros del cuerpo (`POST /rutas`):**
   * El sistema debe recibir una petición en `POST /rutas` con el cuerpo JSON obligatorio conteniendo `asignacion_id` (o `ruta_id`).
   * Si el campo no viene, debe responder `400 Bad Request` con:
     ```json
     {
       "codigo": "DATOS_INVALIDOS",
       "mensaje": "El campo asignacion_id es obligatorio"
     }
     ```
   * Si el cuerpo no es JSON válido, responde `400 Bad Request` con `codigo: "JSON_INVALIDO"`.

2. **Validación de ruta en curso (404 y 409):**
   * El sistema busca en su base de datos la ruta asociada a esa `asignacion_id`.
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
   * Si llegan dos peticiones simultáneas para finalizar la misma ruta, exactamente una debe responder `200` y la otra `409`.

3. **Simulación geoespacial (Fórmula de Haversine):**
   * El sistema captura la `hora_fin` (timestamp actual en UTC).
   * Recupera la `coordenada_origen` registrada al inicio (`lat: 3.4516, lon: -76.5320`).
   * Para simular el viaje sin hardware GPS, genera una `coordenada_destino` sumando un delta aleatorio en latitud y longitud dentro de un radio de **5 a 25 km** respecto al origen.
   * Calcula la distancia final del viaje en kilómetros mediante la fórmula matemática de Haversine (radio terrestre $R = 6371.0\text{ km}$):
     $$d = 2R \cdot \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)}\right)$$
   * El resultado `distancia_recorrida_km` debe redondearse a **2 decimales** (ej. `15.50 km`).
   * Si la duración entre inicio y fin es menor a 1 minuto, debe asignar una distancia mínima de **0.50 km**.

4. **Persistencia y cambio de estado:**
   * El sistema actualiza el registro de la ruta en su base de datos:
     * Estado pasa de `EN_CURSO` a `FINALIZADA`.
     * Guarda `hora_fin`, `coordenada_destino` y `distancia_recorrida_km`.
   * **Ningún registro se elimina de la base de datos.**

5. **Éxito (200 OK):**
   * Con la ruta finalizada, el sistema responde `200 OK` con el resumen completo del viaje:
     ```json
     {
       "id": "ruta-1001",
       "asignacion_id": "asig-8472",
       "vehiculo_id": "veh-501",
       "distancia_recorrida_km": 15.50,
       "hora_inicio": "2026-10-05T08:00:00Z",
       "hora_fin": "2026-10-05T12:00:00Z",
       "coordenada_origen": {
         "latitud": 3.4516,
         "longitud": -76.5320
       },
       "coordenada_destino": {
         "latitud": 3.5200,
         "longitud": -76.4800
       },
       "estado": "FINALIZADA"
     }
     ```

6. **Publicación de evento (`RutaFinalizadaEvent`):**
   * Inmediatamente después de confirmar el guardado en base de datos, el sistema publica en el exchange `fleetops.events` el evento con routing key `telemetria.ruta.finalizada`.
   * Sobre estándar conteniendo en `datos`:
     ```json
     {
       "asignacion_id": "asig-8472",
       "vehiculo_id": "veh-501",
       "distancia_recorrida_km": 15.50,
       "estado_ruta": "FINALIZADA",
       "hora_inicio": "2026-10-05T08:00:00Z",
       "hora_fin": "2026-10-05T12:00:00Z"
     }
     ```
   * Consumidores:
     * **Vehículos:** Suma la distancia a su `kilometraje_actual`.
     * **Asignaciones:** Pasa la asignación a `FINALIZADA`.

7. **Tolerancia a fallos de mensajería (Transactional Outbox):**
   * Si el broker RabbitMQ está temporalmente inaccesible, el evento debe quedar guardado en la tabla local `outbox_eventos` en la misma transacción del cambio de ruta.
   * La respuesta `200 OK` al conductor **no debe fallar** si la base de datos local confirmó la transacción.

8. **Fallo de persistencia (503):**
   * Si la base de datos local no responde, el sistema debe responder `503 Service Unavailable` con `codigo: "SERVICIO_NO_DISPONIBLE"` sin emitir eventos.

---

## HU-04: Procesar Interrupción Imprevista de Asignación por Incidente

| Parámetro | Detalle |
| :--- | :--- |
| **Identificador** | **HU-04** |
| **Rol / Actor** | Sistema (actor interno - MS Asignaciones) |
| **Acción** | Requiero procesar la interrupción imprevista de una asignación por incidente para cerrar la ruta y calcular la distancia parcial. |
| **Beneficio** | Para asegurar que la ruta activa quede cerrada como `INTERRUMPIDA` y los kilómetros recorridos hasta el momento del accidente se reporten al odómetro del vehículo sin pérdida de datos. |
| **Prioridad** | **Media** |
| **Dependencias** | Reacción asíncrona ante el Proceso 2 (Reporte de Incidentes). Manejo de idempotencia y desvío a DLQ. |

### Criterios de Aceptación

1. **Suscripción y cola:**
   * El sistema debe consumir eventos desde la cola `q.telemetria`, enlazada al exchange `fleetops.events` (tipo topic) con la routing key `asignaciones.asignacion.interrumpida` (o `AsignacionInterrumpidaEvent`).
   * La URL de conexión al broker debe leerse obligatoriamente de una variable de entorno.

2. **Validación del mensaje y sobre estándar (Tolerant Reader):**
   * El mensaje entrante debe tener el sobre estándar (`evento_id`, `tipo_evento`, `version`, `fecha_evento`, `origen`, `datos`).
   * El nodo `datos` debe incluir obligatoriamente `asignacion_id`.
   * Los campos adicionales (como `incidente_id`, `reasignacion_resultado`) deben **ignorarse sin error**.
   * Si el mensaje no es JSON válido o le falta `asignacion_id`, el sistema debe desviarlo a la DLQ (`q.telemetria.dlq`) sin reintentos y escribir en el log con nivel `ERROR` el `evento_id` y el campo faltante.

3. **Idempotencia:**
   * El sistema debe guardar el `evento_id` de cada evento procesado en la tabla `eventos_procesados`.
   * Si llega de nuevo un evento con un `evento_id` ya procesado, debe confirmarlo (ACK manual) sin cambios en la base de datos ni reprocesamiento.

4. **Búsqueda y cierre de ruta activa:**
   * El sistema consulta su base de datos buscando una ruta asociada a `datos.asignacion_id` en estado `EN_CURSO`.
   * Si no existe ninguna ruta para esa asignación, o si la ruta ya estaba `FINALIZADA` o `INTERRUMPIDA`, el sistema debe confirmar el mensaje (ACK) sin error y escribir en el log con nivel `INFO` que no había ruta activa por cerrar.

5. **Cálculo parcial y transición de estado:**
   * Si la ruta está `EN_CURSO`, el sistema captura la hora actual como `hora_fin`.
   * Simula una posición intermedia proporcional al tiempo transcurrido desde el inicio.
   * Calcula la distancia parcial recorrida con la misma fórmula de Haversine.
   * Actualiza el estado de la ruta a `INTERRUMPIDA`.
   * **Bajo ninguna circunstancia se elimina el registro de la ruta; se conserva su historial completo para auditoría y trazabilidad del incidente.**

6. **Emisión de evento con estado INTERRUMPIDA:**
   * Tras guardar el cambio, el sistema debe publicar en `fleetops.events` el evento `telemetria.ruta.finalizada` con el sobre estándar y en `datos`:
     ```json
     {
       "asignacion_id": "asig-8472",
       "vehiculo_id": "veh-501",
       "distancia_recorrida_km": 7.80,
       "estado_ruta": "INTERRUMPIDA",
       "hora_inicio": "2026-10-05T08:00:00Z",
       "hora_fin": "2026-10-05T09:15:00Z"
     }
     ```
   * Efecto en otros servicios:
     * **Vehículos:** Escucha el evento y suma la distancia parcial a su `kilometraje_actual`.
     * **Asignaciones:** Lo recibe, pero al estar ya en `INTERRUMPIDA_POR_INCIDENTE`, lo ignora según las reglas de su catálogo de estados.

7. **Fallos transitorios y DLQ:**
   * Si la base de datos local no responde durante el procesamiento, el sistema debe reintentar **3 veces** con espera creciente.
   * Si sigue fallando, envía el mensaje a la DLQ `q.telemetria.dlq`.
   * El mensaje solo debe confirmarse (ACK) después de guardar el cambio de estado y el `evento_id` en la misma transacción.

8. **Frontera:**
   * El sistema no debe consultar a Incidentes ni a Asignaciones, ni interactuar con talleres o grúas.
   * Su única responsabilidad es cerrar la ruta localmente y publicar los kilómetros parciales.

---

## HU-05: Consultar Listado y Detalle Histórico de Rutas

| Parámetro | Detalle |
| :--- | :--- |
| **Identificador** | **HU-05** |
| **Rol / Actor** | Gerencia / Administrador de Flota |
| **Acción** | Requiero consultar el listado y detalle histórico de rutas con filtros por estado, asignación y fechas. |
| **Beneficio** | Para auditar los trayectos de los vehículos, monitorear distancias operativas y proveer datos al servicio de Reportes Operativos para el cálculo de KPIs gerenciales. |
| **Prioridad** | **Media** |
| **Dependencias** | Exposición de datos para auditoría administrativa y soporte síncrono al orquestador del Proceso 6 (KPIs gerenciales). |

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

2. **Respuesta paginada (200 OK):**
   * Estructura estándar obligatoria:
     ```json
     {
       "contenido": [
         {
           "id": "ruta-1001",
           "asignacion_id": "asig-8472",
           "vehiculo_id": "veh-501",
           "distancia_recorrida_km": 15.50,
           "hora_inicio": "2026-10-05T08:00:00Z",
           "hora_fin": "2026-10-05T12:00:00Z",
           "estado": "FINALIZADA"
         }
       ],
       "page": 0,
       "size": 20,
       "total": 1
     }
     ```
   * En rutas `EN_CURSO`, `distancia_recorrida_km` y `hora_fin` retornan `null`.

3. **Orden estable:**
   * Resultados ordenados de forma **descendente por `hora_inicio`** (las rutas más recientes primero).
   * Dos llamadas con la misma página deben devolver los mismos registros si no hubo cambios.

4. **Lista vacía:**
   * Si ninguna ruta cumple el filtro o `page` supera la última página, responde `200 OK` con `contenido: []` y `total: 0` (nunca `404`).

5. **Consulta por identificador (`GET /rutas/{id}`):**
   * Si el `id` existe, responde `200 OK` con el objeto completo de la ruta incluyendo las coordenadas de origen y destino:
     ```json
     {
       "id": "ruta-1001",
       "asignacion_id": "asig-8472",
       "vehiculo_id": "veh-501",
       "conductor_id": "cond-101",
       "distancia_recorrida_km": 15.50,
       "hora_inicio": "2026-10-05T08:00:00Z",
       "hora_fin": "2026-10-05T12:00:00Z",
       "coordenada_origen": { "latitud": 3.4516, "longitud": -76.5320 },
       "coordenada_destino": { "latitud": 3.5200, "longitud": -76.4800 },
       "estado": "FINALIZADA"
     }
     ```
   * Si no existe, responde `404 Not Found` con `codigo: "RUTA_NO_ENCONTRADA"`.

6. **Soporte al Proceso 6 (Reportes Operativos):**
   * Este endpoint es consultado síncronamente por el MS Reportes Operativos en su agregación paralela para calcular `distancia_total_recorrida_km` y `rutas_en_curso`.
   * Debe responder en **menos de 1.0 segundo** bajo carga normal, soportado por índices locales en base de datos sobre `(estado, hora_inicio)`.

7. **Fallo de persistencia (503):**
   * Si la base de datos no responde, responde `503 Service Unavailable` con `codigo: "SERVICIO_NO_DISPONIBLE"`.

---

## HU-06: Endpoint de Salud y Diagnóstico de Dependencias

| Parámetro | Detalle |
| :--- | :--- |
| **Identificador** | **HU-06** |
| **Rol / Actor** | Ingeniero de Infraestructura (DevOps / SRE) |
| **Acción** | Requiero consultar el estado de salud y dependencias del microservicio de telemetría. |
| **Beneficio** | Para verificar la disponibilidad del microservicio, diagnosticar fallas de red y permitir que el balanceador de carga de AWS y los contenedores gestionen el tráfico operativo. |
| **Prioridad** | **Baja** |
| **Dependencias** | Mandatorio según el Manual de Desarrollo v0.2 para probes de Kubernetes/Docker y balanceadores AWS. |

### Criterios de Aceptación

1. **Acceso público y sin token:**
   * El endpoint síncrono `GET /health` debe responder sin exigir token JWT de Cognito, cabeceras de autorización ni validación de roles en el API Gateway.

2. **Sondeo activo de Base de Datos:**
   * El sistema debe ejecutar una consulta de sondeo rápida (`SELECT 1`) contra su base de datos relacional local con un timeout de **1.0 segundo**.
   * Si la base de datos responde: `"database": "UP"`.
   * Si expira o falla: `"database": "DOWN"`.

3. **Sondeo activo de RabbitMQ:**
   * El sistema debe verificar la conexión activa del socket TCP contra el broker de RabbitMQ con un timeout de **1.0 segundo**.
   * Si el canal/conexión está abierto y saludable: `"broker": "UP"`.
   * Si está desconectado o bloqueado: `"broker": "DOWN"`.

4. **Éxito (200 OK):**
   * Si la base de datos y el broker responden favorablemente:
     ```json
     {
       "status": "UP",
       "database": "UP",
       "broker": "UP",
       "timestamp": "2026-10-22T16:27:00Z"
     }
     ```

5. **Degradación o fallo de dependencias (503 Service Unavailable):**
   * Si la base de datos o el broker fallan la prueba de conexión:
     ```json
     {
       "status": "DOWN",
       "database": "DOWN",
       "broker": "UP",
       "timestamp": "2026-10-22T16:27:00Z"
     }
     ```
   * Responde código HTTP `503` con encabezado o payload indicando `codigo: "SERVICIO_DEGRADADO"`.

6. **Rendimiento no intrusivo:**
   * La ejecución del healthcheck debe tomar **menos de 150 milisegundos** en condiciones normales.
   * No debe dejar conexiones colgadas en el pool de la base de datos ni saturar el canal de RabbitMQ.
