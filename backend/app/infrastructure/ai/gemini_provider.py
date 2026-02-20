import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from app.core.interfaces import AIProvider
from app.core.entities import FormResult, Interaction, Participant

class GeminiAIProvider(AIProvider):
    def __init__(self):
        # Configuramos el modelo 1.5 Flash (rápido y económico)
        # Usamos temperature=0 para que sea determinista (no invente cosas)
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0
        )

    def extract_form_data(self, image_bytes: bytes) -> list[FormResult]:
        """
        Envía la imagen a Gemini y parsea el resultado.
        """
        # 1. Preparamos el mensaje multimodal (Texto + Imagen)
        message = HumanMessage(
            content=[
                {"type": "text", "text": self._get_prompt()},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_bytes}"},
                },
            ]
        )

        # 2. Invocamos al modelo
        response = self.llm.invoke([message])
        
        # 3. Convertimos la respuesta de texto/JSON a nuestras entidades Core
        # (Aquí luego agregaremos un OutputParser para mayor robustez)
        return self._parse_response_to_entities(response.content)

    def _get_prompt(self) -> str:
        return """
        Actúa como un experto en OCR. Analiza la imagen de esta planilla de Speed Dating.
        Extrae el nombre del dueño de la planilla y la lista de personas con las que interactuó.
        Indica si hubo interés (Sí) o no (No).
        Retorna ÚNICAMENTE un JSON con este formato:
        [{"owner": "Nombre", "interactions": [{"target": "Nombre", "interested": true}]}]
        """