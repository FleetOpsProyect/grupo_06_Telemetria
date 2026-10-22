# FleetOps — Telemetría y Rutas (Grupo 06)

Microservicio encargado del ciclo de vida de los recorridos operativos de la flota de vehículos, simulación geoespacial de telemetría (Haversine), y sincronización de eventos de viaje para combustible, odómetros y auditoría gerencial en el ecosistema **FleetOps**.

---

## 📌 Contexto del Proyecto

Forma parte del **Proceso 5: Registro de Combustible y Telemetría (Rutas)**. Su objetivo principal es sistematizar el registro de recorridos vinculándolos obligatoriamente a una asignación activa para eliminar el uso de planillas físicas y permitir la detección oportuna de sobrecostos o consumos anómalos de combustible.

---

## 📚 Documentación Técnica Detallada

La documentación completa del proyecto ha sido estructurada en la carpeta [`/docs`](file:///b:/Projects/Universidad/DSIII/grupo_06_Telemetria/docs/index.md):

* 📖 [**01. Contexto de Negocio y Dominio**](file:///b:/Projects/Universidad/DSIII/grupo_06_Telemetria/docs/01_contexto_y_negocio.md): Actores, problemática, flujos del sistema y diagramas de interacción.
* 📋 [**02. Product Backlog Refinado (Historias de Usuario)**](file:///b:/Projects/Universidad/DSIII/grupo_06_Telemetria/docs/02_product_backlog_historias_usuario.md): Especificación detallada de **HU-01** a **HU-06** con criterios de aceptación completos.
* 🏛️ [**03. Documento de Arquitectura de Software (DAS)**](file:///b:/Projects/Universidad/DSIII/grupo_06_Telemetria/docs/03_documento_arquitectura_software_das.md): Metas, restricciones, matriz de atributos de calidad ISO 25010 (observables y no observables) y patrones aplicados (Transactional Outbox, Circuit Breaker, Strategy, Idempotent Consumer).
* 🔌 [**04. Contratos de API REST, Eventos y Modelo de Datos**](file:///b:/Projects/Universidad/DSIII/grupo_06_Telemetria/docs/04_contratos_api_y_eventos.md): Especificación OpenAPI de endpoints, payloads JSON, eventos en RabbitMQ y esquemas DDL SQL.

---

## 🚀 Capacidades y Reglas Principales

| Caso de Uso / HU | Método / Canal | Descripción |
| :--- | :--- | :--- |
| **HU-01: Iniciar Ruta** | `POST /rutas/iniciar` | Valida asignación en `PENDIENTE` con MS Asignaciones (Circuit Breaker 2s / 5 fallos), guarda ruta `EN_CURSO` en origen FleetCorp (`[3.4516, -76.5320]`) y publica `telemetria.ruta.iniciada`. |
| **HU-02: Validar Ruta Combustible**| Consumidor / Cola | Valida vigencia de ruta (`EN_CURSO`) para autorizar tanqueos en vía (< 200 ms P95, solo BD local, sin llamadas HTTP salientes). |
| **HU-03: Finalizar Ruta** | `POST /rutas` | Simulación de viaje con fórmula de **Haversine** (radio 5–25 km, mínimo 0.50 km si < 1 min), persiste `FINALIZADA`, guarda en `outbox_eventos` y publica `telemetria.ruta.finalizada`. |
| **HU-04: Ruta Interrumpida** | Cola `q.telemetria` | Reacciona a `asignaciones.asignacion.interrumpida`, calcula distancia parcial con Haversine, cambia a `INTERRUMPIDA` y publica odómetro parcial a Vehículos. |
| **HU-05: Consulta de Rutas** | `GET /rutas` | Consulta paginada (`page`, `size` 1-100) con filtros por estado, fechas, asignación y vehículo (< 1.0 s para soporte a Reportes Operativos). |
| **HU-06: Endpoint de Salud** | `GET /health` | Sondeo público sin JWT a BD relacional (`SELECT 1`) y RabbitMQ (< 150 ms, responde `200 UP` o `503 SERVICIO_DEGRADADO`). |

---

## 🛠️ Principios de Arquitectura

* **Patrón Transactional Outbox:** Garantiza que los eventos de fin de ruta no se pierdan si el broker RabbitMQ está caído.
* **Circuit Breaker:** Protege la comunicación saliente hacia el microservicio de Asignaciones.
* **Idempotencia y Tolerant Reader:** Tabla `eventos_procesados` para deduplicación estricta y lectura tolerante de mensajes en cola.
* **Patrón Strategy:** Algoritmo Haversine encapsulado tras interfaz para facilitar migración futura a GPS real sin modificar contratos.
