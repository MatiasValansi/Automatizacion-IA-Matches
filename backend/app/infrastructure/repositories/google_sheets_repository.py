from __future__ import annotations

import requests
import os
from app.core.interfaces import MatchRepository
from app.core.entities import DuplicateMerge, Match


class GoogleSheetsMatchRepository(MatchRepository):
    def __init__(self, webhook_url: str = None):
        # Priorizamos la URL pasada o la buscamos en el .env
        self.webhook_url = webhook_url or os.getenv("GOOGLE_SHEETS_WEBHOOK_URL")

    def save_matches(
        self,
        event_name: str,
        form_results: list,
        matches: list[Match],
        duplicate_merges: list[DuplicateMerge] | None = None,
    ) -> str | None:
        if not self.webhook_url:
            print("⚠️ Error: No se encontró la URL del Webhook de Google.")
            return None

        # Data cruda: una fila por cada voto individual de cada planilla
        raw_data = []
        for form in form_results:
            for interaction in form.interactions:
                raw_data.append({
                    "owner": form.owner.name,
                    "vote_for": interaction.receptor_name,
                    "interested": interaction.interested,
                })

        # Payload con tres secciones: data cruda + matches mutuos + duplicados
        payload = {
            "sheet_name": event_name,
            "raw_data": raw_data,
            "matches": [
                {"persona_a": m.person_a.name, "persona_b": m.person_b.name}
                for m in matches
            ],
            "duplicates": self._format_duplicates(duplicate_merges or []),
        }

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=15)
            print(f"[GoogleSheets] Webhook: {response.status_code} - {response.text[:200]}")
            if response.status_code == 200:
                data = response.json()
                return data.get("sheet", None)
            return None
        except Exception as e:
            print(f"❌ Error al conectar con Google Sheets: {e}")
            return None

    @staticmethod
    def _format_duplicates(merges: list[DuplicateMerge]) -> list[dict]:
        """Formatea las decisiones de deduplicación para el payload del webhook."""
        return [
            {
                "nombre_a": m.name_a,
                "nombre_b": m.name_b,
                "nombre_canonico": m.canonical_name,
                "similitud_porcentaje": m.similarity_score,
                "decision": m.decision,
            }
            for m in merges
        ]