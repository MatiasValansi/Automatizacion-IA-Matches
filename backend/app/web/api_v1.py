from fastapi import FastAPI

# Creamos la instancia de FastAPI que busca Uvicorn
app = FastAPI(
    title="AI Social Matcher API",
    description="Backend para la automatización de matches mediante IA",
    version="1.0.0"
)

@app.get("/")
def read_root():
    """Endpoint de salud para verificar que el contenedor funciona."""
    return {
        "status": "online",
        "project": "AI Social Matcher",
        "version": "1.0.0"
    }