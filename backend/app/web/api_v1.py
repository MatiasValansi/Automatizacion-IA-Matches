import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from typing import List

# Importamos la lógica de negocio y los adaptadores
from app.use_cases.process_event import ProcessEventUseCase
from app.use_cases.match_engine import MatchEngine
from app.use_cases.name_normalizer import NameNormalizer
from app.infrastructure.ai.gemini_provider import GeminiAIProvider
from app.infrastructure.repositories.google_sheets_repository import GoogleSheetsMatchRepository

app = FastAPI(
    title="Automatizacion IA Matches",
    description="Backend para el procesamiento de planillas de eventos con IA",
    version="1.1.0"
)

# --- Inicialización de Dependencias (Manual por ahora) ---
# En un futuro podrías usar un contenedor de DI como FastAPI Depends
normalizer = NameNormalizer(threshold=85)
engine = MatchEngine(normalizer=normalizer)
ai_provider = GeminiAIProvider()
# La URL del webhook debe estar en tu archivo .env
repository = GoogleSheetsMatchRepository(
    webhook_url=os.getenv("GOOGLE_SHEETS_WEBHOOK_URL", "")
)

# El "Director de Orquesta"
use_case = ProcessEventUseCase(
    ai_provider=ai_provider,
    match_engine=engine,
    repository=repository
)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "project": "AI Social Matcher - Eventeando",
        "version": "1.1.0"
    }

@app.post("/process-event")
async def handle_process_event(
    event_name: str = Form(...), 
    files: List[UploadFile] = File(...)
):
    """
    Endpoint principal para la UI de Eventeando.
    Recibe el nombre del evento (ej: '12/02/2026 26-34') y las fotos de las planillas.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Debe cargar al menos una imagen.")

    try:
        # Convertimos los archivos subidos a bytes
        images_bytes = []
        for file in files:
            content = await file.read()
            images_bytes.append(content)

        # Ejecutamos el flujo completo del evento
        matches = use_case.execute(event_name, images_bytes)

        return {
            "event": event_name,
            "processed_images": len(files),
            "matches_found": len(matches),
            "status": "Exportado exitosamente a Google Sheets"
        }
    except Exception as e:
        # Aquí podrías loggear el error para debugging
        raise HTTPException(status_code=500, detail=f"Error procesando el evento: {str(e)}")