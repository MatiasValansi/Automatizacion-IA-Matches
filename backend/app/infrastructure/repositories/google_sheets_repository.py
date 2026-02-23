import requests
import os
from app.core.interfaces import MatchRepository
from app.core.entities import Match

class GoogleSheetsMatchRepository(MatchRepository):
    def __init__(self, webhook_url: str = None):
        # Priorizamos la URL pasada o la buscamos en el .env
        self.webhook_url = webhook_url or os.getenv("GOOGLE_SHEETS_WEBHOOK_URL")

    def save_matches(self, event_name: str, matches: list[Match]) -> bool:
        if not self.webhook_url:
            print("⚠️ Error: No se encontró la URL del Webhook de Google.")
            return False

        # El payload debe coincidir EXACTO con lo que espera tu Google Apps Script
        payload = {
            "sheet_name": event_name,
            "data": [
                {"persona_a": m.person_a.name, "persona_b": m.person_b.name} 
                for m in matches
            ]
        }

        try:
            # Enviamos el POST al script de Google
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error al conectar con Google Sheets: {e}")
            return False