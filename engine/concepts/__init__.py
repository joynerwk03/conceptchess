"""Concept registry.

Each concept is an object with:
  - name: str, a short identifier
  - display_name: str, human-readable
  - score(ctx) -> float          fast path, centipawns from White's perspective
  - details(ctx) -> list[(label, cp)]   itemized breakdown; MUST sum to score(ctx)

The faithfulness invariant (details sum == score, and sum of concept scores ==
the eval used by search) is enforced by tests/test_eval.py. Never break it:
the whole point of this engine is that the explanation IS the evaluation.
"""

from engine.concepts.material import Material
from engine.concepts.piece_placement import PiecePlacement
from engine.concepts.pawn_structure import PawnStructure
from engine.concepts.king_safety import KingSafety
from engine.concepts.mobility import Mobility
from engine.concepts.piece_activity import PieceActivity
from engine.concepts.king_attack import KingAttack
from engine.concepts.tempo import Tempo
from engine.concepts.threats import Threats
from engine.concepts.mate_drive import MateDrive

ALL_CONCEPTS = [
    Material(),
    PiecePlacement(),
    PawnStructure(),
    KingSafety(),
    KingAttack(),
    Mobility(),
    PieceActivity(),
    Tempo(),
    Threats(),
    MateDrive(),
]
