import re
from datetime import date
from typing import Dict, List, Optional
from pydantic import BaseModel

from core.logger import get_logger
from core.graph_engine import ADIEGraphEngine
from core.models import Assumption, NodeStatus

logger = get_logger("validator")


class ValidationAlert(BaseModel):
    assumption_id: str
    statement: str
    trigger_type: str  # "TEMPORAL_EXPIRY" | "SEMANTIC_CONTRADICTION" | "NUMERIC_DRIFT"
    similarity_score: float
    details: str
    recommended_confidence: float


class HybridAssumptionValidator:
    """Neuro-Symbolic Validator combining deterministic temporal/numeric rules with embeddings."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", similarity_threshold: float = 0.55):
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self._model = None
        self.negation_tokens = {
            "not", "no", "never", "increased", "exceeds", "deprecated",
            "banned", "stopped", "broken", "failed", "removed", "higher", "expensive"
        }

    @property
    def model(self):
        """Lazy-load the sentence-transformers model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading local embedding model: {self.model_name}...")
                self._model = SentenceTransformer(self.model_name)
                logger.info("Model loaded successfully.")
            except ImportError:
                logger.error("sentence-transformers is not installed. Install with: pip install 'assumptionpulse[ml]'")
                raise
            except Exception as e:
                logger.error(f"Failed to load embedding model '{self.model_name}': {e}")
                raise
        return self._model

    def check_temporal_validity(
        self, engine: ADIEGraphEngine, reference_date: Optional[date] = None
    ) -> List[ValidationAlert]:
        """Symbolic Rule 1: Checks if any assumption has passed its valid_until date."""
        today = reference_date or date.today()
        alerts: List[ValidationAlert] = []

        for assumption in engine.assumptions.values():
            if assumption.valid_until and today > assumption.valid_until and assumption.status != NodeStatus.INVALID:
                alert = ValidationAlert(
                    assumption_id=assumption.id,
                    statement=assumption.statement,
                    trigger_type="TEMPORAL_EXPIRY",
                    similarity_score=1.0,
                    details=f"Expired on {assumption.valid_until} (checked on {today}).",
                    recommended_confidence=0.0,
                )
                alerts.append(alert)
                logger.warning(f"[TEMPORAL_EXPIRY] Assumption {assumption.id} expired on {assumption.valid_until}")

        return alerts

    @staticmethod
    def _extract_numbers(text: str) -> List[float]:
        return [float(m) for m in re.findall(r"\d+(?:\.\d+)?", text)]

    def evaluate_incoming_fact(
        self,
        engine: ADIEGraphEngine,
        new_fact: str,
        auto_propagate: bool = True,
    ) -> List[ValidationAlert]:
        """Neural + Symbolic Check: Matches an incoming observation against stored assumptions."""
        assumptions = list(engine.assumptions.values())
        if not assumptions:
            return []

        try:
            from sentence_transformers import util
            statements = [a.statement for a in assumptions]
            fact_emb = self.model.encode(new_fact, convert_to_tensor=True)
            stmt_embs = self.model.encode(statements, convert_to_tensor=True)
            cosine_scores = util.cos_sim(fact_emb, stmt_embs)[0]
        except Exception as e:
            logger.error(f"Semantic comparison failed: {e}")
            return []

        fact_numbers = self._extract_numbers(new_fact)
        fact_words = set(re.findall(r"\w+", new_fact.lower()))
        has_conflict_cue = bool(fact_words & self.negation_tokens)

        alerts: List[ValidationAlert] = []

        for idx, assumption in enumerate(assumptions):
            sim = float(cosine_scores[idx])
            if sim < self.similarity_threshold:
                continue

            old_numbers = self._extract_numbers(assumption.statement)
            numeric_changed = bool(old_numbers and fact_numbers and old_numbers != fact_numbers)

            if numeric_changed:
                alert = ValidationAlert(
                    assumption_id=assumption.id,
                    statement=assumption.statement,
                    trigger_type="NUMERIC_DRIFT",
                    similarity_score=round(sim, 4),
                    details=f"Matched (sim={sim:.2f}). Value shifted from {old_numbers} to {fact_numbers}.",
                    recommended_confidence=0.1,
                )
                alerts.append(alert)
                logger.warning(f"[NUMERIC_DRIFT] {assumption.id}: {alert.details}")
                if auto_propagate:
                    engine.invalidate_assumption(assumption.id, new_confidence=0.1)

            elif has_conflict_cue:
                alert = ValidationAlert(
                    assumption_id=assumption.id,
                    statement=assumption.statement,
                    trigger_type="SEMANTIC_CONTRADICTION",
                    similarity_score=round(sim, 4),
                    details=f"Matched (sim={sim:.2f}) with contradiction signal in: '{new_fact}'.",
                    recommended_confidence=0.2,
                )
                alerts.append(alert)
                logger.warning(f"[SEMANTIC_CONTRADICTION] {assumption.id}: {alert.details}")
                if auto_propagate:
                    engine.invalidate_assumption(assumption.id, new_confidence=0.2)

        return alerts
