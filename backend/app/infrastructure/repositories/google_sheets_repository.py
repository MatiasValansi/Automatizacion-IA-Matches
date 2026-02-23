from backend.app.core.interfaces import MatchRepository


class GoogleSheetsMatchRepository(MatchRepository):
    def save_matches(self, event_name: str, matches: list[Match]) -> bool:
        payload = {
            "sheet_name": event_name, # Usamos el nombre que viene del frontend
            "matches": [
                {"p_a": m.person_a.name, "p_b": m.person_b.name} 
                for m in matches
            ]
        }
        # El Apps Script se encargará de crear la hoja si no existe
        response = requests.post(self.webhook_url, json=payload)
        return response.status_code == 200