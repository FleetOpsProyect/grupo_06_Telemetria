## 📋 Descripción
<!-- Describe brevemente qué hace este PR, la funcionalidad que añade o el problema que resuelve. -->
<!-- Incluye referencias a Historias de Usuario (HU), tareas o Criterios de Aceptación si aplica. -->


## 🛠️ Tipo de PR (PR Type)
- [ ] 🚀 **Feature** (Nueva funcionalidad)
- [ ] 🐛 **Fix** (Corrección de error)
- [ ] 🧪 **Test** (Pruebas añadidas o actualizadas)
- [ ] ♻️ **Refactor** (Reestructuración de código sin alterar comportamiento)
- [ ] 📝 **Docs** (Documentación / Swagger)
- [ ] 🔧 **Chore** (Configuración, CI, dependencias, tooling)


## 🔍 Cambios realizados
<!-- Detalla los archivos o módulos modificados según las capas o estructura del proyecto -->

### Capa de Dominio (Domain)
- `app/domain/models/` — <!-- Nuevas entidades, agregados o tipos de valor -->
- `app/domain/ports/` — <!-- Nuevos puertos de persistencia, eventos o servicios externos -->

### Capa de Aplicación (Application)
- `app/application/dtos/` — <!-- DTOs / Schemas Pydantic creados o modificados, validaciones -->
- `app/application/services/` — <!-- Servicios de aplicación, orquestación de casos de uso -->

### Capa de Infraestructura (Infrastructure)
- `app/infrastructure/db/` — <!-- Modelos ORM SQLAlchemy, migraciones de base de datos -->
- `app/infrastructure/repositories/` — <!-- Adaptadores de repositorio concretos -->
- `app/infrastructure/messaging/` — <!-- Publicadores y consumidores de RabbitMQ -->

### Capa de Presentación / API (Presentation)
- `app/presentation/api/` — <!-- Endpoints REST expuestos, routers de FastAPI -->
- `app/presentation/dependencies.py` — <!-- Inyección de dependencias (IoC) -->

### Configuración / Otros
- <!-- Cambios en settings (config.py), dependencias en pyproject.toml, Docker, CI, etc. -->


## 🧪 Calidad y Validaciones
<!-- Marca las validaciones ejecutadas antes de abrir el PR (deben pasar todas en CI) -->
- [ ] `ruff check .` (Linter sin errores)
- [ ] `ruff format --check .` (Formato de código verificado)
- [ ] `mypy app` (Type checking estricto pasando sin errores)
- [ ] `pytest --cov=app --cov-report=term-missing` (Tests pasando y cobertura ≥ 80%)


## 💡 Decisiones técnicas
<!-- Justifica decisiones de diseño, patrones adoptados, alternativas descartadas o manejo de casos borde -->
- 


## 🚀 Cómo probar
<!-- Proporciona pasos claros para que el revisor reproduzca y pruebe los cambios localmente -->

```bash
# 1. Ejemplo de comando o petición curl
curl -X GET http://localhost:8000/health
```

### Pruebas desde Swagger UI:
- [ ] Probado interactivamente en `http://localhost:8000/docs`

<!-- Adjunta aquí capturas de pantalla de Swagger, respuestas JSON o evidencias si aplica -->
