# 1. Usamos una imagen liviana de Python 3.11
FROM python:3.11-slim

# 2. Establecemos el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Instalamos dependencias del sistema necesarias para algunas librerías
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 4. Copiamos el archivo de requerimientos primero (para aprovechar el cache de Docker)
COPY requirements.txt .

# 5. Instalamos las librerías de Python
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiamos todo el código de la aplicación
COPY . .

# 7. Exponemos el puerto que usará FastAPI
EXPOSE 8000

# 8. Comando para arrancar la aplicación
CMD ["uvicorn", "app.web.api_v1:app", "--host", "0.0.0.0", "--port", "8000"]