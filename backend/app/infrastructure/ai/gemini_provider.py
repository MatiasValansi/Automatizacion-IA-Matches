import os
import base64
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from app.core.interfaces import AIProvider
from app.core.entities import FormResult, Interaction, Participant

class GeminiAIProvider(AIProvider):
    """
    Implementación concreta de AIProvider usando Google Gemini 1.5 Flash.
    """

    def __init__(self):
        # Configuramos el modelo. Temperature=0 para evitar "alucinaciones".
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0
        )

    def extract_from_image(self, image_bytes: bytes) -> FormResult:
        """
        Toma los bytes de una imagen, los envía a Gemini y devuelve un FormResult.
        """
        # 1. Convertimos los bytes a base64 (formato que requiere la API para imágenes)
        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        # 2. Preparamos el mensaje para la IA
        message = HumanMessage(
            content=[
                {"type": "text", "text": self._get_system_prompt()},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                },
            ]
        )

        # 3. Invocamos al modelo
        response = self.llm.invoke([message])
        
        # 4. Parseamos la respuesta a nuestras entidades de dominio
        return self._map_to_entity(response.content)

    def _get_system_prompt(self) -> str:
        return """
        Actúa como un experto en OCR y extracción de datos. 
        Analiza la planilla de Speed Dating adjunta.
        
        Extrae:
        1. El nombre de la persona dueña de la planilla.
        2. La lista de personas con las que habló y si marcó 'Sí' o 'No'.

        Devuelve ÚNICAMENTE un JSON con esta estructura exacta:
        {
            "owner_name": "Nombre del dueño",
            "votes": [
                {"target_name": "Nombre", "is_interested": true},
                {"target_name": "Nombre", "is_interested": false}
            ]
        }
        """

    def _map_to_entity(self, raw_content: str) -> FormResult:
        """Convierte el texto JSON de la IA en una entidad FormResult."""
        # Limpieza básica por si la IA devuelve markdown (```json ... ```)
        clean_json = raw_content.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        
        owner = Participant(name=data["owner_name"])
        interactions = [
            Interaction(receptor_name=v["target_name"], interested=v["is_interested"])
            for v in data["votes"]
        ]
        
        return FormResult(owner=owner, interactions=interactions)