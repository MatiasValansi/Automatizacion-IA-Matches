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

@dataclass
class FormResult:
    owner: Participant
    interactions: List[Interaction] = field(default_factory=list)

@dataclass
class Match:
    person_a: Participant
    person_b: Participant

@dataclass
class DuplicateMerge:
    """Representa la decisión de unificar dos nombres detectados como duplicados."""
    name_a: str
    name_b: str
    canonical_name: str
    similarity_score: int
    decision: str