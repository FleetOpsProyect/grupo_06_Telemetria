# FleetOps — Telemetría y Rutas (Grupo 06) — Arquetipo Base

Arquetipo base de microservicio FastAPI bajo **Clean Architecture** para el ecosistema **FleetOps** (Universidad del Valle, Desarrollo de Software III).

Este repositorio proporciona la arquitectura de software, infraestructura de contenedores (Docker), pipeline de integración continua (CI) y scaffolding de capas desacopladas, sirviendo como punto de partida para la implementación de las historias de usuario del proyecto.

---

## 🏛️ Estructura del Arquetipo (Clean Architecture)

El proyecto organiza el código separando estrictamente responsabilidades en capas concéntricas:

```text
grupo_06_Telemetria/
├── app/
│   ├── core/                  # Configuraciones, excepciones base, logging y resiliencia
│   │   ├── config.py          # Settings externalizados con Pydantic Settings
│   │   ├── exceptions.py      # Jerarquía de errores estandarizada
│   │   ├── logging.py         # Formato estructurado y correlación
│   │   ├── circuit_breaker.py # Máquina de estados de resiliencia
│   │   └── security.py        # Validación de autenticación JWT
│   ├── domain/                # Capa central de dominio empresarial
│   │   ├── models/            # Entidades y tipos de valor puros
│   │   └── ports/             # Interfaces abstractas (repositorios, publishers)
│   ├── application/           # Casos de uso y orquestación
│   │   ├── dtos/              # Schemas de entrada/salida y validaciones
│   │   └── services/          # Servicios de aplicación del arquetipo
│   ├── infrastructure/        # Adaptadores y drivers externos
│   │   ├── db/                # Sesión SQLAlchemy y modelos ORM
│   │   ├── messaging/         # Conexión y publicador para RabbitMQ
│   │   └── repositories/      # Implementaciones concretas de persistencia
│   ├── presentation/          # Controladores HTTP y middlewares
│   │   ├── api/v1/            # Enrutadores de endpoints REST
│   │   ├── dependencies.py    # Contenedor de Inversión de Control (IoC)
│   │   ├── exception_handlers.py # Estandarización de errores JSON
│   │   └── middleware.py      # Middleware de Correlation ID
│   └── main.py                # Fábrica de aplicación FastAPI
├── tests/                     # Suite de pruebas automatizadas
│   ├── unit/                  # Tests unitarios rápidos (AAA pattern)
│   └── integration/           # Tests end-to-end con SQLite y TestClient
├── .github/workflows/ci.yml   # Pipeline de CI (Ruff, Mypy, Pytest)
├── docker-compose.yml         # Entorno local (App + PostgreSQL + RabbitMQ)
├── Dockerfile                 # Construcción multi-stage de producción
└── pyproject.toml             # Dependencias y herramientas de calidad
```

---

## 🚀 Ejecución Rápida

### Requisitos Previos
* Python 3.12+
* Docker y Docker Compose

### 1. Entorno de Desarrollo Local
```bash
# Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# Instalar dependencias
pip install -e ".[dev]"
```

### 2. Ejecutar Pruebas y Cobertura
```bash
pytest --cov=app --cov-report=term-missing
```

### 3. Ejecutar Linters de Calidad
```bash
ruff check .
ruff format --check .
mypy app
```

### 4. Levantar con Docker Compose
```bash
docker compose up --build
```

El servicio estará disponible en `http://localhost:8000` con documentación interactiva Swagger en `http://localhost:8000/docs`.
