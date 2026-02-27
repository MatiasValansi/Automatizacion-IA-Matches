import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

load_dotenv()  # Carga las variables del archivo .env

# Importamos la lógica de negocio y los adaptadores
from app.use_cases.process_event import ProcessEventUseCase
from app.use_cases.match_engine import MatchEngine
from app.use_cases.name_normalizer import NameNormalizer
from app.use_cases.duplicate_detector import DuplicateDetector
from app.infrastructure.ai.gemini_provider import GeminiAIProvider
from app.infrastructure.repositories.google_sheets_repository import GoogleSheetsMatchRepository
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Automatizacion IA Matches",
    description="Backend para el procesamiento de planillas de eventos con IA",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Inicialización de Dependencias (Manual por ahora) ---
# En un futuro podrías usar un contenedor de DI como FastAPI Depends
normalizer = NameNormalizer(threshold=85)
engine = MatchEngine(normalizer=normalizer)
duplicate_detector = DuplicateDetector(normalizer=normalizer)
ai_provider = GeminiAIProvider()
# La URL del webhook debe estar en tu archivo .env
repository = GoogleSheetsMatchRepository(
    webhook_url=os.getenv("GOOGLE_SHEETS_WEBHOOK_URL", "")
)

# El "Director de Orquesta"
use_case = ProcessEventUseCase(
    ai_provider=ai_provider,
    match_engine=engine,
    repository=repository,
    duplicate_detector=duplicate_detector,
)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "project": "AI Social Matcher - Eventeando",
        "version": "1.1.0"
    }

@app.post(
    "/process-event",
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["event_name", "files"],
                        "properties": {
                            "event_name": {
                                "type": "string",
                                "description": "Nombre del evento (ej: '12/02/2026 26-34')"
                            },
                            "files": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "format": "binary"
                                },
                                "description": "Una o más imágenes de planillas"
                            }
                        }
                    }
                }
            },
            "required": True
        }
    }
)
async def handle_process_event(request: Request):
    """
    Endpoint principal para la UI de Eventeando.
    Recibe el nombre del evento (ej: '12/02/2026 26-34') y las fotos de las planillas.
    """
    form = await request.form()
    event_name = form.get("event_name")
    files = form.getlist("files")

    if not event_name:
        raise HTTPException(status_code=400, detail="El campo 'event_name' es requerido.")
    if not files:
        raise HTTPException(status_code=400, detail="Debe cargar al menos una imagen.")

    try:
        # Convertimos los archivos subidos a bytes
        images_bytes = []
        for file in files:
            content = await file.read()
            images_bytes.append(content)

        # Ejecutamos el flujo completo del evento
        result = use_case.execute(event_name, images_bytes)

        return {
            "event_name": event_name,
            "processed_images": result["images_processed"],
            "match_count": len(result["matches"]),
            "sheet_url": result["sheet_url"],
            "status": "success",
        }
    except Exception as e:
        # Aquí podrías loggear el error para debugging
        raise HTTPException(status_code=500, detail=f"Error procesando el evento: {str(e)}")