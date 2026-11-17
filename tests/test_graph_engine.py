import pytest

from core.models import Assumption, Decision, DependencyEdge, NodeStatus
from core.graph_engine import ADIEGraphEngine


def test_add_nodes_and_duplicate_prevention(empty_engine):
    a = Assumption(id="A1", statement="Premise 1 holds true")
    empty_engine.add_assumption(a)
    assert "A1" in empty_engine.assumptions

    # Adding decision with duplicate ID should raise ValueError
    d = Decision(id="A1", title="Collision", description="Desc")
    with pytest.raises(ValueError, match="already registered as an Assumption"):
        empty_engine.add_decision(d)


def test_cycle_detection(empty_engine):
    empty_engine.add_decision(Decision(id="D1", title="Decision 1", description="desc"))
    empty_engine.add_decision(Decision(id="D2", title="Decision 2", description="desc"))
    empty_engine.add_decision(Decision(id="D3", title="Decision 3", description="desc"))

    empty_engine.add_dependency(DependencyEdge(source_id="D1", target_id="D2"))
    empty_engine.add_dependency(DependencyEdge(source_id="D2", target_id="D3"))

    # Attempting to add D3 -> D1 creates a cycle
    with pytest.raises(ValueError, match="Cycle detected"):
        empty_engine.add_dependency(DependencyEdge(source_id="D3", target_id="D1"))

    # Graph edge must have been removed and still be a DAG
    assert not empty_engine.graph.has_edge("D3", "D1")


def test_target_cannot_be_assumption(empty_engine):
    empty_engine.add_assumption(Assumption(id="A1", statement="Premise 1 holds"))
    empty_engine.add_decision(Decision(id="D1", title="Decision 1", description="desc"))

    with pytest.raises(ValueError, match="must be a Decision, not an Assumption"):
        empty_engine.add_dependency(DependencyEdge(source_id="D1", target_id="A1"))


def test_multi_hop_risk_propagation(linear_dag_engine):
    # Initial state: everything is VALID, zero risk
    assert linear_dag_engine.decisions["D1"].risk_score == 0.0
    assert linear_dag_engine.decisions["D1"].status == NodeStatus.VALID
    assert linear_dag_engine.decisions["D2"].risk_score == 0.0

    # Break A1
    impacted = linear_dag_engine.invalidate_assumption("A1", new_confidence=0.0)

    # D1 and D2 should both experience risk transmission
    # D1: failure=1.0 * weight 0.9 = 0.9 threat, * criticality 0.9 = 0.81 risk
    assert linear_dag_engine.decisions["D1"].risk_score > 0.5
    assert linear_dag_engine.decisions["D1"].status == NodeStatus.AT_RISK

    # D2 is downstream of D1, so it also gets hit
    assert linear_dag_engine.decisions["D2"].risk_score > 0.35
    assert linear_dag_engine.decisions["D2"].status == NodeStatus.AT_RISK
    assert len(impacted) == 2


def test_causal_impact_paths(linear_dag_engine):
    paths = linear_dag_engine.get_impact_paths("A1", "D2")
    assert len(paths) == 1
    assert paths[0] == ["A1", "D1", "D2"]


def test_what_if_simulation_does_not_mutate_live_graph(linear_dag_engine):
    # Baseline
    initial_d1_risk = linear_dag_engine.decisions["D1"].risk_score

    cand_d = Decision(id="D1_REPLACEMENT", title="Async Message Queue", description="Decouple API", criticality=0.5)
    cand_dep = [DependencyEdge(source_id="A1", target_id="D1_REPLACEMENT", weight=0.2)]

    blast_radius, impacted = linear_dag_engine.simulate_what_if(
        broken_assumption_id="A1",
        candidate_decision=cand_d,
        candidate_dependencies=cand_dep,
        replaced_decision_id="D1",
    )

    # Verify live engine state was NOT modified
    assert "D1_REPLACEMENT" not in linear_dag_engine.decisions
    assert linear_dag_engine.decisions["D1"].status != NodeStatus.ARCHIVED
    assert linear_dag_engine.decisions["D1"].risk_score == initial_d1_risk
