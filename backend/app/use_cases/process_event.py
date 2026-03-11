from __future__ import annotations
import base64
import logging
from typing import TYPE_CHECKING
from app.core.entities import AuditRecord, FormResult, Interaction, Participant
from app.core.interfaces import AIProvider, AuditRepository, MatchRepository
from app.use_cases.match_engine import MatchEngine
from app.use_cases.duplicate_detector import DuplicateDetector
from app.use_cases.name_normalizer import NameNormalizer, ILEGIBLE_TAG
from app.services.image_optimizer import ImageOptimizer
from app.infrastructure.image_preprocessor import ImagePreprocessor
from app.services.result_cache import image_cache

# Evitamos colisiones de importación circular para el tipado
if TYPE_CHECKING:
    from app.core.entities import Match

logger = logging.getLogger(__name__)

class ProcessEventUseCase:
    """
    Orquestador del flujo de negocio. 
    Coordina la IA, la deduplicación, la auditoría,
    el motor de matches y la persistencia en Sheets.
    """

    def __init__(self, 
                 ai_provider: AIProvider, 
                 match_engine: MatchEngine, 
                 repository: MatchRepository,
                 audit_repo: AuditRepository,
                 duplicate_detector: DuplicateDetector,
                 name_normalizer: NameNormalizer | None = None):
        self.ai_provider = ai_provider
        self.match_engine = match_engine
        self.repository = repository
        self.audit_repo = audit_repo
        self.duplicate_detector = duplicate_detector
        self.name_normalizer = name_normalizer or NameNormalizer()

    def execute(self, event_name: str, images: list[bytes]) -> dict:
        """
        Flujo completo de procesamiento de un evento:

        FASE 1 – Extracción y Auditoría
          1. Verifica cache para cada imagen.
          2. Optimiza imágenes no cacheadas con ImageOptimizer.
          3. Extrae datos de las imágenes con Gemini.
          4. Cachea los resultados nuevos.
          5. Detecta nombres duplicados y unifica variantes.
          6. Persiste los resultados en la hoja 'Auditoría IA'.

        FASE 2 – Matches (post-auditoría)
          7. Lee los datos auditados (con posibles correcciones humanas).
          8. El motor de cruce calcula matches desde la auditoría.
          9. Persiste los matches en la hoja 'Matches'.

        Retorna un dict con toda la info relevante para el frontend.
        """
        all_results = []
        failed_images = []  # índices (1-based) de imágenes que fallaron
        pending_bytes: list[bytes] = []   # imágenes optimizadas a enviar por batch
        pending_indices: list[int] = []   # índice original de cada pending

        for idx, img_bytes in enumerate(images):
            img_b64 = base64.b64encode(img_bytes).decode()

            # 1. Verificar cache
            cached = image_cache.get(img_b64)
            if cached is not None:
                all_results.append(cached)
                continue

            # 2. Corregir perspectiva (deskew) + mejora contraste, luego optimizar
            deskewed_bytes = ImagePreprocessor.preprocess(img_bytes)
            deskewed_b64 = base64.b64encode(deskewed_bytes).decode()
            optimized_b64 = ImageOptimizer.optimize_base64(deskewed_b64)
            optimized_bytes = base64.b64decode(optimized_b64)
            pending_bytes.append(optimized_bytes)
            pending_indices.append(idx)

        # 3. Extraer datos con IA en batch (todas las no-cacheadas juntas)
        if pending_bytes:
            try:
                batch_results = self.ai_provider.extract_batch(pending_bytes)
                for i, result in enumerate(batch_results):
                    original_idx = pending_indices[i]
                    # 4. Guardar en cache
                    img_b64 = base64.b64encode(images[original_idx]).decode()
                    image_cache.set(img_b64, result)
                    all_results.append(result)
            except Exception as e:
                logger.error(f"[ProcessEvent] Batch falló: {e}")
                failed_images = [idx + 1 for idx in pending_indices]

        # Si no se pudo procesar ninguna imagen, lanzar error
        if not all_results:
            raise RuntimeError(
                f"No se pudo procesar ninguna imagen. "
                f"Fallaron: {len(failed_images)}/{len(images)}"
            )

        if failed_images:
            logger.warning(
                f"[ProcessEvent] {len(failed_images)} imagen(es) fallaron "
                f"(#{', #'.join(str(i) for i in failed_images)}). "
                f"Procesadas exitosamente: {len(all_results)}/{len(images)}"
            )

        # ── FASE 1: Limpieza de datos ──────────────────────────────
        cleaned_results = self._clean_form_results(all_results)

        # ── FASE 1a: Unificación de nombres ────────────────────────
        unified_results, duplicate_merges = self.duplicate_detector.detect_and_unify(
            cleaned_results
        )

        # ── FASE 1b: Normalizar nombres para presentación ────────
        normalized_results = self._normalize_form_results(unified_results)

        # ── FASE 1c: Persistir en Auditoría IA ─────────────────────
        audit_records = self._form_results_to_audit_records(normalized_results)
        unique_participants = self._collect_unique_participants(normalized_results)
        self.audit_repo.save_audit(event_name, audit_records, unique_participants)

        # ── FASE 2: Matches desde datos auditados ──────────────────
        # El motor lee de 'Auditoría IA', priorizando correcciones
        # humanas sobre la extracción de la IA.
        matches = self.match_engine.find_matches_from_audit(event_name)

        # ── FASE 3: Persistencia de matches y data cruda ───────────
        sheet_url = self.repository.save_matches(
            event_name, unified_results, matches, duplicate_merges
        )

        return {
            "matches": matches,
            "sheet_url": sheet_url,
            "images_processed": len(all_results),
            "images_failed": len(failed_images),
            "failed_indices": failed_images,
            "duplicates_detected": len(duplicate_merges),
        }

    # ── Limpieza de datos ──────────────────────────────────────────

    _INVALID_RECEPTOR_VALUES = {ILEGIBLE_TAG, "none", ""}
    _SUSPECT_OWNER_VALUES = {"participant", "ilegible"}

    def _clean_form_results(
        self, form_results: list[FormResult]
    ) -> list[FormResult]:
        """Elimina interacciones inválidas y alerta sobre emisores sospechosos.

        1. Descarta interacciones con receptor [NOMBRE ILEGIBLE], None o vacío.
        2. Descarta votos negativos sin receptor real (fantasma).
        3. Loguea advertencia si el owner necesita revisión manual.
        """
        cleaned: list[FormResult] = []
        for form in form_results:
            # Alerta de emisor sospechoso
            owner_lower = (form.owner.name or "").strip().lower()
            if owner_lower in self._SUSPECT_OWNER_VALUES:
                logger.warning(
                    "[ProcessEvent] Emisor sospechoso '%s' detectado. "
                    "La planilla requiere revisión manual de identidad.",
                    form.owner.name,
                )

            valid_interactions: list[Interaction] = []
            for inter in form.interactions:
                receptor = (inter.receptor_name or "").strip()

                # Filtrar receptores inválidos (ilegible, None, vacío)
                # Esto también elimina votos negativos fantasma (sin receptor real)
                if not receptor or receptor.lower() in self._INVALID_RECEPTOR_VALUES:
                    continue

                valid_interactions.append(inter)

            cleaned.append(FormResult(owner=form.owner, interactions=valid_interactions))
        return cleaned

    def _normalize_form_results(
        self, form_results: list[FormResult]
    ) -> list[FormResult]:
        """Normaliza todos los nombres para presentación (Title Case, trim).
        Preserva [NOMBRE ILEGIBLE] sin modificar."""
        normalized: list[FormResult] = []
        for form in form_results:
            owner_name = self.name_normalizer.normalize_display(form.owner.name)
            new_owner = Participant(name=owner_name, phone=form.owner.phone)
            new_interactions = [
                Interaction(
                    receptor_name=self.name_normalizer.normalize_display(
                        inter.receptor_name
                    ),
                    interested=inter.interested,
                    confidence_score=inter.confidence_score,
                )
                for inter in form.interactions
            ]
            normalized.append(FormResult(owner=new_owner, interactions=new_interactions))
        return normalized

    @staticmethod
    def _collect_unique_participants(
        form_results: list[FormResult],
    ) -> list[str]:
        """Extrae la lista de participantes únicos (owners + targets)."""
        names: set[str] = set()
        for form in form_results:
            names.add(form.owner.name)
            for interaction in form.interactions:
                names.add(interaction.receptor_name)
        return sorted(names)

    @staticmethod
    def _form_results_to_audit_records(
        form_results: list,
    ) -> list[AuditRecord]:
        """Convierte FormResults unificados en registros de auditoría."""
        records: list[AuditRecord] = []
        for form in form_results:
            for interaction in form.interactions:
                records.append(
                    AuditRecord(
                        extracted_name=form.owner.name,
                        voted_for=interaction.receptor_name,
                        interested=interaction.interested,
                        ai_confidence=interaction.confidence_score,
                    )
                )
        return records