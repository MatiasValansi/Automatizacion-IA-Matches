from __future__ import annotations

import requests
from requests.exceptions import ReadTimeout, ConnectionError
import os
from app.core.interfaces import AuditRepository, MatchRepository
from app.core.entities import AuditRecord, DuplicateMerge, Match


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
            response = requests.post(
                self.webhook_url, json=payload, timeout=(10, 60)
            )
            print(f"[GoogleSheets] ✅ Webhook: {response.status_code} - {response.text[:200]}")
            if response.status_code == 200:
                data = response.json()
                return data.get("sheet", None)
            return None
        except ReadTimeout:
            # El servidor recibió los datos pero tardó en responder.
            # Google Apps Script suele procesar bien aunque haga timeout en la lectura.
            print(
                "[GoogleSheets] ⚠️ Timeout esperando respuesta de Google Sheets. "
                "Los datos probablemente se guardaron correctamente. "
                "Verificá la hoja de cálculo manualmente."
            )
            return None
        except ConnectionError as e:
            print(f"[GoogleSheets] ❌ Error de conexión con Google Sheets: {e}")
            return None
        except Exception as e:
            print(f"[GoogleSheets] ❌ Error inesperado al conectar con Google Sheets: {e}")
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


class GoogleSheetsAuditRepository(AuditRepository):
    """
    Adaptador concreto de AuditRepository para Google Sheets.
    Gestiona la hoja 'Auditoría IA' mediante webhooks al Apps Script.
    """

    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url or os.getenv("GOOGLE_SHEETS_WEBHOOK_URL")

    # ── Escritura ────────────────────────────────────────────────
    def save_audit(
        self,
        event_name: str,
        records: list[AuditRecord],
        participants: list[str] | None = None,
    ) -> None:
        if not self.webhook_url:
            print("⚠️ Error: No se encontró la URL del Webhook de Google.")
            return

        payload = {
            "sheet_name": event_name,
            "action": "save_audit",
            "audit_data": [
                {
                    "nombre_extraido": r.extracted_name,
                    "voto_a": r.voted_for,
                    "interes": "SI" if r.interested else "NO",
                    "confianza_ia": round(r.ai_confidence, 2),
                    "correccion_humana": r.human_correction,
                }
                for r in records
            ],
            "participants": participants or [],
        }

        try:
            response = requests.post(
                self.webhook_url, json=payload, timeout=(10, 60)
            )
            print(
                f"[AuditSheet] ✅ Webhook save_audit: "
                f"{response.status_code} - {response.text[:200]}"
            )
        except ReadTimeout:
            print(
                "[AuditSheet] ⚠️ Timeout en save_audit. "
                "Los datos probablemente se guardaron. Verificá la hoja."
            )
        except ConnectionError as e:
            print(f"[AuditSheet] ❌ Error de conexión en save_audit: {e}")
        except Exception as e:
            print(f"[AuditSheet] ❌ Error inesperado en save_audit: {e}")

    # ── Lectura ──────────────────────────────────────────────────
    def get_audited_results(self, event_name: str) -> list[AuditRecord]:
        if not self.webhook_url:
            print("⚠️ Error: No se encontró la URL del Webhook de Google.")
            return []

        params = {"action": "get_audit", "sheet_name": event_name}

        try:
            response = requests.get(
                self.webhook_url, params=params, timeout=(10, 60)
            )
            if response.status_code != 200:
                print(
                    f"[AuditSheet] ❌ get_audit HTTP {response.status_code}: "
                    f"{response.text[:200]}"
                )
                return []

            rows = response.json().get("audit_data", [])
            return [
                AuditRecord(
                    extracted_name=row["nombre_extraido"],
                    voted_for=row["voto_a"],
                    interested=str(row.get("interes", "NO")).upper() == "SI",
                    ai_confidence=float(row.get("confianza_ia", 0)),
                    human_correction=str(row.get("correccion_humana", "")),
                )
                for row in rows
            ]
        except ReadTimeout:
            print("[AuditSheet] ⚠️ Timeout en get_audit.")
            return []
        except ConnectionError as e:
            print(f"[AuditSheet] ❌ Error de conexión en get_audit: {e}")
            return []
        except Exception as e:
            print(f"[AuditSheet] ❌ Error inesperado en get_audit: {e}")
            return []