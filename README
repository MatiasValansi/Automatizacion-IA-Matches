# Automatizacion IA Matches

**Automatizacion IA Matches** es una solución integral diseñada para automatizar la gestión de "matches" en eventos de networking o Speed Dating. El sistema elimina la carga manual de planillas físicas mediante el uso de **Inteligencia Artificial Multimodal** para el procesamiento de imágenes, extracción de datos y detección de reciprocidad mutua.

## Arquitectura y Principios de Diseño
El software ha sido construido siguiendo estándares de alta calidad para asegurar su mantenibilidad y escalabilidad:

* **Clean Architecture (Hexagonal):** Desacoplamiento total entre la lógica de negocio y la infraestructura (APIs externas, bases de datos).
* **SOLID:** Aplicación estricta de principios, con especial énfasis en la **Inversión de Dependencias** (el motor de matches no depende de la implementación del OCR).
* **TDD & BDD:** Desarrollo guiado por pruebas y comportamiento utilizando `pytest-bdd`. Los escenarios de negocio están documentados en lenguaje Gherkin.
* **Fuzzy Matching:** Implementación de lógica de comparación difusa (Distancia de Levenshtein) para normalizar nombres manuscritos con errores u omisión de tildes.

---

## Stack Tecnológico
* **Lenguaje:** Python 3.11+.
* **Framework Web:** FastAPI.
* **IA & OCR:** LangChain + Gemini 1.5 Flash.
* **Persistencia:** Google Sheets API (vía Google Apps Script).
* **Contenerización:** Docker & Docker Compose.

---

## Estructura del Proyecto
```text
backend/
├── app/
│   ├── core/           # Entidades puras e interfaces de dominio
│   ├── use_cases/      # Lógica de aplicación (MatchEngine, Normalizer)
│   ├── infrastructure/ # Adaptadores externos (IA, Repositorios)
│   └── web/            # Capa de entrada (FastAPI)
├── tests/
│   ├── features/       # Especificaciones Gherkin (.feature)
│   └── unit/           # Tests de comportamiento y unidad
└── Dockerfile          # Receta de construcción de la imagen

## Instalación y Ejecución

El proyecto está completamente **dockerizado** para garantizar la portabilidad y evitar conflictos de dependencias locales entre entornos de desarrollo.

**1. Construir y levantar el contenedor:**
Ejecutá el siguiente comando en la raíz del proyecto para compilar e iniciar el entorno:
```bash
docker-compose up --build

**2. Acceder a la documentación de la API:
Una vez que el contenedor esté en estado running, podés explorar y probar los endpoints desde la interfaz interactiva de Swagger/OpenAPI provista por FastAPI:

URL: http://localhost:8000/docs

## Ejecución de Pruebas
Para validar la integridad del sistema (específicamente la lógica de detección de matches y el motor de normalización de nombres), ejecutá la suite de tests directamente dentro del contenedor activo:

```bash
docker-compose exec backend python -m pytest tests/unit/test_matches.py -v