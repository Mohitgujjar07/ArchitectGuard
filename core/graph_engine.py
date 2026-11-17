import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import networkx as nx

from core.logger import get_logger
from core.models import (
    Assumption,
    Decision,
    DependencyEdge,
    NodeStatus,
    ProjectGraphData,
)

logger = get_logger("graph_engine")


class ADIEGraphEngine:
    """Assumption-to-Decision Impact Engine (ADIE) using NetworkX DAGs."""

    def __init__(self, project_name: str = "Untitled Project"):
        self.project_name = project_name
        self.graph = nx.DiGraph()
        self.assumptions: Dict[str, Assumption] = {}
        self.decisions: Dict[str, Decision] = {}
        self.storage: Optional[Any] = None

    def attach_storage(self, store: Any) -> None:
        """Attach a ProjectStore instance for auto-saving mutations."""
        self.storage = store

    def auto_save(self) -> None:
        """Persist state to attached storage if present."""
        if self.storage:
            try:
                self.storage.save_project(self)
                logger.debug(f"Auto-saved project '{self.project_name}'")
            except Exception as e:
                logger.warning(f"Failed to auto-save project '{self.project_name}': {e}")

    def add_assumption(self, assumption: Assumption) -> None:
        """Add an assumption node to the graph."""
        if assumption.id in self.decisions:
            raise ValueError(f"ID '{assumption.id}' is already registered as a Decision.")
        self.assumptions[assumption.id] = assumption
        self.graph.add_node(assumption.id, node_type="ASSUMPTION", data=assumption)
        logger.info(f"Added assumption {assumption.id}: '{assumption.statement[:50]}'")
        self.auto_save()

    def add_decision(self, decision: Decision) -> None:
        """Add a decision node to the graph."""
        if decision.id in self.assumptions:
            raise ValueError(f"ID '{decision.id}' is already registered as an Assumption.")
        self.decisions[decision.id] = decision
        self.graph.add_node(decision.id, node_type="DECISION", data=decision)
        logger.info(f"Added decision {decision.id}: '{decision.title}'")
        self.auto_save()

    def add_dependency(self, edge: DependencyEdge) -> None:
        """Add a directed edge representing an architectural dependency."""
        if edge.source_id not in self.graph or edge.target_id not in self.graph:
            missing = [nid for nid in (edge.source_id, edge.target_id) if nid not in self.graph]
            raise ValueError(f"Cannot link dependency: node(s) {missing} do not exist in graph.")
        if edge.target_id in self.assumptions:
            raise ValueError(f"Target node '{edge.target_id}' must be a Decision, not an Assumption.")

        self.graph.add_edge(
            edge.source_id,
            edge.target_id,
            weight=edge.weight,
            rationale=edge.rationale,
        )
        if not nx.is_directed_acyclic_graph(self.graph):
            self.graph.remove_edge(edge.source_id, edge.target_id)
            raise ValueError(
                f"Cycle detected! Adding {edge.source_id} -> {edge.target_id} creates a circular dependency."
            )
        logger.info(f"Added dependency: {edge.source_id} -> {edge.target_id} (weight={edge.weight})")
        self.auto_save()

    def invalidate_assumption(self, assumption_id: str, new_confidence: float = 0.0) -> List[Decision]:
        """Update an assumption's confidence/status and propagate risk downstream."""
        if assumption_id not in self.assumptions:
            raise KeyError(f"Assumption '{assumption_id}' not found.")

        assumption = self.assumptions[assumption_id]
        old_conf = assumption.confidence
        assumption.confidence = max(0.0, min(1.0, new_confidence))
        assumption.status = NodeStatus.INVALID if assumption.confidence < 0.5 else NodeStatus.VALID

        logger.info(
            f"Assumption {assumption_id} confidence changed: {old_conf:.2f} -> {assumption.confidence:.2f} ({assumption.status.value})"
        )
        self.propagate_impact()
        self.auto_save()
        return self.get_impacted_decisions(assumption_id)

    def propagate_impact(self) -> None:
        """Topologically traverse the DAG to compute downstream decision risk scores."""
        node_validity: Dict[str, float] = {}

        for a_id, assumption in self.assumptions.items():
            node_validity[a_id] = 0.0 if assumption.status == NodeStatus.INVALID else assumption.confidence

        for node_id in nx.topological_sort(self.graph):
            if node_id not in self.decisions:
                continue

            decision = self.decisions[node_id]
            if decision.status == NodeStatus.ARCHIVED:
                node_validity[node_id] = 1.0
                continue

            parents = list(self.graph.predecessors(node_id))
            if not parents:
                decision.risk_score = 0.0
                decision.status = NodeStatus.VALID
                node_validity[node_id] = 1.0
                continue

            # Probabilistic failure aggregation across all parent dependencies
            survival_prob = 1.0
            for parent_id in parents:
                weight = self.graph.edges[parent_id, node_id]["weight"]
                parent_failure = 1.0 - node_validity.get(parent_id, 1.0)
                transmitted_risk = parent_failure * weight
                survival_prob *= (1.0 - transmitted_risk)

            raw_threat = 1.0 - survival_prob
            decision.risk_score = round(raw_threat * decision.criticality, 4)

            if decision.risk_score >= 0.35:
                decision.status = NodeStatus.AT_RISK
            else:
                decision.status = NodeStatus.VALID

            node_validity[node_id] = 1.0 - decision.risk_score

        logger.debug("Risk propagation sweep completed.")

    def get_impacted_decisions(self, source_id: str) -> List[Decision]:
        """Return all downstream decisions reachable from source_id, sorted by risk_score."""
        if source_id not in self.graph:
            return []
        descendants = nx.descendants(self.graph, source_id)
        impacted = [
            self.decisions[d_id]
            for d_id in descendants
            if d_id in self.decisions and self.decisions[d_id].status == NodeStatus.AT_RISK
        ]
        return sorted(impacted, key=lambda d: d.risk_score, reverse=True)

    def get_impact_paths(self, source_id: str, target_id: str) -> List[List[str]]:
        """Return all causal chains explaining why source_id impacts target_id."""
        if source_id not in self.graph or target_id not in self.graph:
            return []
        return list(nx.all_simple_paths(self.graph, source=source_id, target=target_id))

    def simulate_what_if(
        self,
        broken_assumption_id: str,
        candidate_decision: Decision,
        candidate_dependencies: List[DependencyEdge],
        replaced_decision_id: str,
    ) -> Tuple[float, List[Decision]]:
        """Simulate replacing a broken decision with an alternative without mutating live state."""
        sim_engine = copy.deepcopy(self)
        sim_engine.storage = None  # Do not auto-save simulation branch

        if replaced_decision_id in sim_engine.decisions:
            sim_engine.decisions[replaced_decision_id].status = NodeStatus.ARCHIVED

        sim_engine.add_decision(candidate_decision)
        for dep in candidate_dependencies:
            sim_engine.add_dependency(dep)

        impacted = sim_engine.invalidate_assumption(broken_assumption_id, new_confidence=0.0)
        total_blast_radius = round(
            sum(d.risk_score for d in sim_engine.decisions.values() if d.status != NodeStatus.ARCHIVED), 4
        )
        return total_blast_radius, impacted

    def to_json(self, filepath: str) -> None:
        """Export graph to JSON file."""
        edges = [
            DependencyEdge(
                source_id=u,
                target_id=v,
                weight=data["weight"],
                rationale=data.get("rationale", ""),
            )
            for u, v, data in self.graph.edges(data=True)
        ]
        payload = ProjectGraphData(
            project_name=self.project_name,
            assumptions=list(self.assumptions.values()),
            decisions=list(self.decisions.values()),
            dependencies=edges,
        )
        Path(filepath).write_text(payload.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"Exported project graph to {filepath}")

    @classmethod
    def from_json(cls, filepath: str) -> "ADIEGraphEngine":
        """Instantiate engine from a JSON file."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Project file not found: {filepath}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            data = ProjectGraphData(**raw)
        except Exception as e:
            raise ValueError(f"Failed to parse project file '{filepath}': {e}")

        return cls.from_project_data(data)

    @classmethod
    def from_project_data(cls, data: ProjectGraphData) -> "ADIEGraphEngine":
        """Build engine from a ProjectGraphData model."""
        engine = cls(project_name=data.project_name)
        for a in data.assumptions:
            engine.add_assumption(a)
        for d in data.decisions:
            engine.add_decision(d)
        for dep in data.dependencies:
            engine.add_dependency(dep)
        engine.propagate_impact()
        return engine
