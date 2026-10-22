# Documentación Técnica — Microservicio Telemetría y Rutas

Bienvenido al repositorio de documentación del microservicio **Telemetría y Rutas** (`grupo_06_Telemetria`), perteneciente a la plataforma **FleetOps** para la gestión logística de flotas de transporte.

---

## Índice de Documentos

1. [**01. Contexto de Negocio y Dominio**](file:///b:/Projects/Universidad/DSIII/grupo_06_Telemetria/docs/01_contexto_y_negocio.md)
   * Visión general del microservicio en el **Proceso 5: Registro de Combustible y Telemetría (Rutas)**.
   * Problemática de las planillas físicas de combustible y auditoría extemporánea.
   * Actores del sistema (Conductor, Combustible, Asignaciones, Vehículos, Reportes, SRE).
   * Diagrama integral de interacciones y flujos síncronos y asíncronos.
   * Flujo de inicio de ruta, verificación de vigencia de ruta en tanqueo, finalización con simulación geoespacial Haversine, interrupción imprevista por incidente y auditoría gerencial.

2. [**02. Product Backlog Refinado (Historias de Usuario)**](file:///b:/Projects/Universidad/DSIII/grupo_06_Telemetria/docs/02_product_backlog_historias_usuario.md)
   * **HU-01:** Iniciar ruta asociada a asignación activa (`POST /rutas/iniciar`, validación síncrona, Circuit Breaker, unicidad 409, evento `telemetria.ruta.iniciada`).
   * **HU-02:** Consultar ruta en curso para combustible (Verificación interna, sin llamadas externas, respuesta en < 200 ms P95, DLQ).
   * **HU-03:** Finalizar ruta activa y calcular distancia simulada (`POST /rutas`, fórmula de Haversine, Transactional Outbox, evento `telemetria.ruta.finalizada`).
   * **HU-04:** Procesar interrupción imprevista de asignación por incidente (`AsignacionInterrumpidaEvent`, cálculo de distancia parcial, inmutabilidad de ruta, evento con estado `INTERRUMPIDA`).
   * **HU-05:** Consultar listado y detalle histórico de rutas (`GET /rutas`, `GET /rutas/{id}`, paginación, filtros, respuesta en < 1.0 s para soporte al Proceso 6 de Reportes Operativos).
   * **HU-06:** Endpoint de salud y diagnóstico de dependencias (`GET /health`, sondeo no intrusivo a BD relacional y socket RabbitMQ en < 150 ms, público).

3. [**03. Documento de Arquitectura de Software (DAS)**](file:///b:/Projects/Universidad/DSIII/grupo_06_Telemetria/docs/03_documento_arquitectura_software_das.md)
   * Metas y restricciones arquitectónicas.
   * Matriz exhaustiva de **Atributos de Calidad Observables** bajo la norma **ISO/IEC 25010** (Adecuación funcional, Compatibilidad, Capacidad de interacción, Fiabilidad, Seguridad, Mantenibilidad, Flexibilidad, Protección).
   * Matriz de **Atributos de Calidad No Observables** (Eficiencia de desempeño, Recuperabilidad, Resistencia, Modularidad, Reemplazabilidad).
   * Patrones tácticos y arquitectónicos aplicados: **Transactional Outbox**, **Circuit Breaker**, **Strategy Pattern** (Haversine vs GPS real), **Idempotent Consumer**, **Tolerant Reader**, **Database-per-Service** y **Clean Architecture**.

4. [**04. Contratos de API REST, Eventos y Modelo de Datos**](file:///b:/Projects/Universidad/DSIII/grupo_06_Telemetria/docs/04_contratos_api_y_eventos.md)
   * Catálogo unificado de códigos de error HTTP y payloads de respuesta JSON.
   * Especificación detallada de endpoints REST (`POST /rutas/iniciar`, `POST /rutas`, `GET /rutas`, `GET /rutas/{id}`, `GET /health`).
   * Contratos de eventos para el bus RabbitMQ (Exchange `fleetops.events`, sobre estándar, routing keys, eventos emitidos y consumidos).
   * Modelo entidad-relación (ER) y DDL SQL para las tablas `rutas`, `outbox_eventos` y `eventos_procesados`.

5. [**05. Guía Dojo API REST Python (Univalle - Desarrollo de Software III)**](file:///b:/Projects/Universidad/DSIII/grupo_06_Telemetria/docs/05_guia_dojo_api_rest_python.md)
   * Guía oficial del curso dictado por el PhD. Manuel Alejandro Pastrana Pardo.
   * Estándares y versiones de dependencias (Python 3.12, FastAPI 0.115, SQLAlchemy 2.0, Pydantic v2, Ruff, Mypy, Pytest).
   * Estrategia de pruebas unitarias (SQLite en memoria con StaticPool) y de integración (Testcontainers).
   * Especificaciones de empaquetado Docker multi-etapa, Docker Compose, SonarCloud y Pipelines de CI/CD para GitHub Actions y AWS EC2.
