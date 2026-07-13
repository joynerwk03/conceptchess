"""Evaluation: sum of concept scores.

evaluate()          fast path used by search (centipawns, White's perspective)
evaluate_detailed() same number, broken into concepts and items (faithful:
                    total == evaluate(), each concept's items sum to its score)
"""

from dataclasses import dataclass, field

from engine.concepts import ALL_CONCEPTS
from engine.context import EvalContext

CONCEPTS = ALL_CONCEPTS


def evaluate(board):
    """Centipawns from White's perspective."""
    ctx = EvalContext(board)
    return sum(c.score(ctx) for c in CONCEPTS)


@dataclass
class ConceptBreakdown:
    name: str
    display_name: str
    score: float
    items: list = field(default_factory=list)  # [(label, cp)]


@dataclass
class EvalBreakdown:
    total: float
    concepts: list  # [ConceptBreakdown]

    def as_dict(self):
        return {
            "total": round(self.total, 1),
            "concepts": [
                {
                    "name": c.name,
                    "display_name": c.display_name,
                    "score": round(c.score, 1),
                    "items": [(label, round(v, 1)) for label, v in c.items],
                }
                for c in self.concepts
            ],
        }


def evaluate_detailed(board):
    ctx = EvalContext(board)
    concepts = []
    total = 0.0
    for c in CONCEPTS:
        items = c.details(ctx)
        score = c.score(ctx)
        concepts.append(ConceptBreakdown(c.name, c.display_name, score, items))
        total += score
    return EvalBreakdown(total, concepts)
