"""Evaluation: sum of concept scores.

evaluate()          fast path used by search (centipawns, White's perspective)
evaluate_detailed() same number, broken into concepts and items (faithful:
                    total == evaluate(), each concept's items sum to its score)
"""

from dataclasses import dataclass, field

from engine.concepts import ALL_CONCEPTS, ALL_MODIFIERS
from engine.context import EvalContext

CONCEPTS = ALL_CONCEPTS
MODIFIERS = ALL_MODIFIERS


def evaluate(board):
    """Centipawns from White's perspective.

    Two stages: the additive concept sum, then any multiplicative modifiers
    (e.g. opposite-bishop drawishness) applied in registry order. The C core
    mirrors this exactly (see core/ceval.c)."""
    ctx = EvalContext(board)
    total = sum(c.score(ctx) for c in CONCEPTS)
    for m in MODIFIERS:
        total *= m.factor(ctx)
    return total


def clear_caches():
    """Invalidate concept-level caches. MUST be called after mutating
    engine.weights.W at runtime (the pawn/king caches bake weights in)."""
    for c in CONCEPTS:
        if hasattr(c, "_cache"):
            c._cache.clear()


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
    # multiplicative modifiers: attribute each its marginal delta so the
    # displayed items still sum to the final total (faithfulness preserved).
    for m in MODIFIERS:
        f = m.factor(ctx)
        delta = (f - 1.0) * total
        items = [(m.item_label(ctx), delta)] if delta else []
        concepts.append(ConceptBreakdown(m.name, m.display_name, delta, items))
        total *= f
    return EvalBreakdown(total, concepts)
