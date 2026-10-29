# FleetOps — Telemetría y Rutas (Grupo 06) — Arquetipo Base

Proyecto académico de **Desarrollo de Software III** (código 750027C), Universidad del Valle, semestre 2026-1.

Arquetipo base de microservicio FastAPI bajo **Clean Architecture** para el ecosistema **FleetOps** (Universidad del Valle, Desarrollo de Software III).

Este repositorio proporciona la arquitectura de software, infraestructura de contenedores (Docker), pipeline de integración continua (CI) y scaffolding de capas desacopladas, sirviendo como punto de partida para la implementación de las historias de usuario del proyecto.


[![CI](https://github.com/FleetOpsProyect/grupo_06_Telemetria/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/FleetOpsProyect/grupo_06_Telemetria/actions/workflows/ci.yml)
[![CD](https://github.com/FleetOpsProyect/grupo_06_Telemetria/actions/workflows/cd.yml/badge.svg?branch=main)](https://github.com/FleetOpsProyect/grupo_06_Telemetria/actions/workflows/cd.yml)
[![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project=OWNER_REPO&metric=alert_status)](https://sonarcloud.io/dashboard?id=OWNER_REPO)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project= FleetOpsProyect_grupo_06_Telemetria&metric=coverage)](https://sonarcloud.io/dashboard?id= FleetOpsProyect_grupo_06_Telemetria)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)


---
## Alcance del microservicio

El servicio gestiona el ciclo de vida de una ruta: inicio, finalización con cálculo de distancia, interrupción por asignación cancelada y consulta. Consume el microservicio de **Asignaciones** (síncrono, REST) y publica eventos al bus para **Combustible**, **Notificaciones** y **Reportes Operativos**.
---
### Historias de usuario

| HU | Descripción | Endpoint / Consumidor | Tipo |
|---|---|---|---|
| HU-01 | Iniciar ruta asociada a una asignación | `POST /route/start` | Síncrono REST |
| HU-02 | Validación de ruta para consumo de combustible | Consumidor `q.telemetria` | Asíncrono |
| HU-03 | Finalizar ruta y calcular distancia (Haversine) | `POST /route` | Síncrono REST |
| HU-04 | Interrumpir ruta por asignación cancelada | Consumidor `q.telemetria` | Asíncrono |
| HU-05 | Consultar rutas (listado paginado y por ID) | `GET /route`, `GET /route/{id}` | Síncrono REST |
| HU-06 | Health check para probes y balanceador | `GET /health` | Público |

---
### Endpoints

| Método | Ruta | Auth | Rol | Timeout |
|---|---|---|---|---|
| POST | `/route/start` | JWT Cognito | Conductor (Operador) | 2 s hacia Asignaciones |
| POST | `/route` | JWT Cognito | Conductor (Operador) | — |
| GET | `/route` | JWT Cognito | Gerencia / Administrador de flota | 1.0 s |
| GET | `/route/{id}` | JWT Cognito | Gerencia / Administrador de flota | 1.0 s |
| GET | `/health` | Público (sin token) | Ninguno | 150 ms |
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
 


---
## Modelo de datos

|Tabla            | Propósito                                                    |
|-----------------|--------------------------------------------------------------|
|routes           |Entidad central; estado IN_PROGRESS, COMPLETED o INTERRUPTED  |
|outbox_events    |Patrón outbox para publicación confiable                      |
|events           |Bitácora de eventos entrantes y salientes                     |
|processed_events |Idempotencia de eventos de entrada                            |
|logs             |Bitácora estructurada con nivel, operación y código           |

---

## Mensajería 

|Elemento                | Tipo    | Nombre                     |
|------------------------|---------|----------------------------|
|Exchange                |Topic    |fleetops.events             |
|Routing key (salida)    |Publica  |telemetria.ruta.iniciada    |
|Routing key (salida)    |Publica  |telemetria.ruta.finalizada  |
|Cola (entrada)          |Consume  |q.telemetria                |
|Cola de descarte        |Consume  |q.telemetria.dlq            |


---
## Stack tecnológico

Lenguaje ---> Python 3.12
Framework API ---> FastAPI
Validación --->	Pydantic v2
ORM	SQLAlchemy ---> 2.x
Base de datos ---> PostgreSQL 16
Mensajería	---> RabbitMQ 3.13 (aio-pika)
Autenticación ---> AWS Cognito (JWT)
Tests --->	Pytest + pytest-cov + httpx
Calidad ---> Ruff, Mypy, SonarCloud
Contenedores ---> Docker multi-stage + Docker Compose
Despliegue --->	AWS EC2
Monitoreo ---> Prometheus + Grafana
cobertura ---> pytest
---
## inicio rapido

- Requisitos previos

Python 3.12+
Docker Desktop 4.20+ (o Docker Engine con el plugin Compose)
Git 2.40+

- clonar repositorio
git clone https://github.com/FleetOpsProyect/grupo_06_Telemetria.git

- Entorno virtual e instalacion

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

- Variables de entorno

Se encuentra en .env.example

---
## Levantar  el stack local

docker compose up --build

|Servicio        |Puerto        | Verificación                      |
|----------------|--------------|-----------------------------------|
|telemetria_api  |8000          |GET /health                        |
|postgres        |5432          |pg_isready                         |
|rabbitmq        |5672 / 15672  |Consola en http://localhost:15672  |
|prometheus      |9090          |http://localhost:9090              |
|grafana         |3000          |http://localhost:3000              |

Documentación interactiva: http://localhost:8000/docs

- verificar endpoints

curl http://localhost:8000/health

curl -X POST http://localhost:8000/route/start \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"assignment_id":"ASG-001","vehicle_id":"VEH-014","driver_id":"DRV-007"}'

---


## Pruebas y calidad 

- Suite completa con cobertura
pytest --cov=app --cov-report=term-missing

- Solo unitarias
pytest tests/unit -v

- Solo integración
pytest tests/integration -v

- Linters
ruff check .
ruff format --check .
mypy app


## Cobertura de tests

|Rama / evento      | Pipeline    | Qué valida                     |
|-------------------|-------------|--------------------------------|
|Tests unitarios    |Pytest       |Job Tests en CI                 |
|Cobertura          |pytest-cov   |Job Tests y panel de SonarCloud |
|Análisis estático  |Ruff + Mypy  |Job Lint en CI                  |
|Calidad global     |SonarCloud   |Quality Gate del PR             |


## CI/CD

|Rama / evento           | Pipeline       | Qué valida                                              |
|------------------------|----------------|---------------------------------------------------------|
|PR → develop            |CI              |Ruff, Mypy, Pytest con cobertura, build de imagen Docker |
|Merge → main            |CI + SonarCloud |Quality Gate obligatorio                                 |
|Quality Gate aprobado   |CD              |Despliegue automático del contenedor en AWS EC2          |

1.  Trabajar en una rama feature/....
2. Abrir PR hacia develop; corre CI y se exige al menos una aprobación.
3. Tras la revisión, merge a develop.
4. Abrir PR develop → main; corre CI y el análisis de SonarCloud.
5. Si el Quality Gate pasa, el CD despliega en EC2.

- Secrets requeridos en GitHub Actions

Secret	           | Uso
-------------------|-----------------------------------------
SONAR_TOKEN	       |Autenticación con SonarCloud
SONAR_PROJECT_KEY  |Clave del proyecto en SonarCloud
SONAR_ORGANIZATION |Organización de SonarCloud
DOCKERHUB_USERNAME |Usuario de Docker Hub
DOCKERHUB_TOKEN	   |Access token de Docker Hub (no la contraseña)
EC2_HOST	       |IP o hostname de la instancia
EC2_USER	       |Usuario SSH (ubuntu en EC2)
EC2_SSH_KEY	       |Clave privada .pem
EC2_DEPLOY_PATH	   |Ruta con docker-compose.prod.yml y .env

---
## Monitoreo

|componente    | Endpoint             | Propósito                                               |
|--------------|----------------------|---------------------------------------------------------|
|Prometheus    |GET /metrics          |Recolección de métricas del servicio                     |
|Grafana       |http://localhost:3000 |Dashboards de latencia, errores y consumo de recursos    |
|Health check  |GET /health           |Probes de Docker y balanceador AWS                       |

---
## Estado del proyecto

Área                                 | Estado | Notas
  
Arquetipo base y Clean Architecture      ✅    Capas desacopladas y contenedor de IoC
HU-01 Iniciar ruta                       ✅    Circuit Breaker hacia Asignaciones
HU-03 Finalizar ruta                     ✅    Cálculo Haversine y outbox
HU-04 Interrumpir ruta                   ✅    Consumidor q.telemetria
HU-05 Consultar rutas                    ✅    Paginación y filtros
HU-06 Health check                       ✅    Probes y balanceador
HU-02 Validación para combustible        ✅    Pendiente de integración
CI con SonarCloud                        ✅    Quality Gate en cada PR
CD a AWS EC2                             ✅    Despliegue automático
Monitoreo Prometheus + Grafana           ✅    Dashboard operativo


---

Sprint |      Estado     | Descripción

S1        ✅ Completado   Arquetipo base, Docker, CI, despliegue inicial, HU-01, HU-06, HU-03, HU-05
S2        🔜 Pendiente    HU-02, HU-04, mantenibilidad y monitoreo avanzado

---

## Equipo

Sara Julissa Hernandez — 202610102-3743
Ana Sofía Cantillo Bolaños - 202610112-3743
Juan David Rincón - 202342032-3743
Samuel Arenas Valencia - 202341928-3743
Miguel Ángel Castillo - 202341975-3743
Juan Esteban Pereira - 202569259-3743

Curso: Desarrollo de Software III — 750027C Docente: Manuel Alejandro Pastrana Pardo, PhD. Semestre: 2026-1
## Licencia

Released under the MIT License. See LICENSE for details.