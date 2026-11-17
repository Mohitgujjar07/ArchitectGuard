from datetime import date
import pytest
from pydantic import ValidationError

from core.models import Assumption, Decision, DependencyEdge, NodeStatus, ProjectGraphData


def test_assumption_creation_and_defaults():
    a = Assumption(id="A1", statement="Postgres connections scale to 500")
    assert a.id == "A1"
    assert a.confidence == 1.0
    assert a.status == NodeStatus.VALID
    assert a.category == "Technical"
    assert a.created_at == date.today()
    assert a.valid_until is None
    assert a.tags == []


def test_assumption_confidence_bounds():
    # Valid bounds
    Assumption(id="A1", statement="Valid boundary 0.0", confidence=0.0)
    Assumption(id="A2", statement="Valid boundary 1.0", confidence=1.0)

    # Invalid bounds
    with pytest.raises(ValidationError):
        Assumption(id="A3", statement="Out of bounds", confidence=1.05)

    with pytest.raises(ValidationError):
        Assumption(id="A4", statement="Out of bounds negative", confidence=-0.1)


def test_assumption_statement_min_length():
    with pytest.raises(ValidationError):
        Assumption(id="A1", statement="Tiny")


def test_decision_creation_and_bounds():
    d = Decision(id="D1", title="Use Kafka", description="Event streaming architecture")
    assert d.criticality == 0.8
    assert d.risk_score == 0.0
    assert d.status == NodeStatus.VALID

    # Criticality bounds (0.1 to 1.0)
    with pytest.raises(ValidationError):
        Decision(id="D2", title="Fail", description="Desc", criticality=0.05)

    with pytest.raises(ValidationError):
        Decision(id="D3", title="Fail", description="Desc", criticality=1.1)


def test_dependency_edge_validation():
    edge = DependencyEdge(source_id="A1", target_id="D1", weight=0.85, rationale="Primary DB")
    assert edge.weight == 0.85
    assert edge.rationale == "Primary DB"

    with pytest.raises(ValidationError):
        DependencyEdge(source_id="A1", target_id="D1", weight=0.05)

    with pytest.raises(ValidationError):
        DependencyEdge(source_id="A1", target_id="D1", weight=1.2)


def test_project_graph_data_serialization():
    a = Assumption(id="A1", statement="AWS costs remain stable")
    d = Decision(id="D1", title="Multi-region AWS", description="Deploy to 3 regions")
    e = DependencyEdge(source_id="A1", target_id="D1", weight=0.9)

    data = ProjectGraphData(
        project_name="Cloud Migration",
        assumptions=[a],
        decisions=[d],
        dependencies=[e],
    )
    json_str = data.model_dump_json()
    assert "Cloud Migration" in json_str

    restored = ProjectGraphData.model_validate_json(json_str)
    assert restored.project_name == "Cloud Migration"
    assert len(restored.assumptions) == 1
    assert restored.assumptions[0].id == "A1"
    assert len(restored.decisions) == 1
    assert len(restored.dependencies) == 1
