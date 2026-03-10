from dataclasses import dataclass, field
from typing import List

@dataclass(frozen=True)
class Participant:
    name: str
    phone: str = ""

@dataclass
class Interaction:
    receptor_name: str
    interested: bool
    confidence_score: float = 1.0

@dataclass
class FormResult:
    owner: Participant
    interactions: List[Interaction] = field(default_factory=list)

@dataclass
class Match:
    person_a: Participant
    person_b: Participant

@dataclass
class AuditRecord:
    """Una fila de la hoja 'Auditoría IA': un voto individual ya clasificado."""
    extracted_name: str       # Nombre_Extraído (dueño de la planilla)
    voted_for: str            # Votó_A (persona votada)
    interested: bool          # Interés (SI/NO) según la IA
    ai_confidence: float      # Confianza_IA (0.0 – 1.0)
    human_correction: str = ""  # Corrección_Humana ("SI"/"NO" o vacío)


@dataclass
class DuplicateMerge:
    """Representa la decisión de unificar dos nombres detectados como duplicados."""
    name_a: str
    name_b: str
    canonical_name: str
    similarity_score: int
    decision: str