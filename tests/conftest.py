import sys
from pathlib import Path
import pytest

# Ensure root is in path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.models import Assumption, Decision, DependencyEdge, NodeStatus
from core.graph_engine import ADIEGraphEngine
from core.storage import ProjectStore


@pytest.fixture
def empty_engine():
    return ADIEGraphEngine(project_name="Test Project")


@pytest.fixture
def linear_dag_engine():
    """
    A1 -> D1 -> D2
    """
    engine = ADIEGraphEngine(project_name="Linear DAG")
    engine.add_assumption(Assumption(id="A1", statement="Database latency under 5ms", confidence=1.0))
    engine.add_decision(Decision(id="D1", title="Synchronous API writes", description="Rely on fast DB", criticality=0.9))
    engine.add_decision(Decision(id="D2", title="Instant UI update", description="Optimistic UI update", criticality=0.7))

    engine.add_dependency(DependencyEdge(source_id="A1", target_id="D1", weight=0.9))
    engine.add_dependency(DependencyEdge(source_id="D1", target_id="D2", weight=0.8))
    engine.propagate_impact()
    return engine


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_store.db"
    return ProjectStore(str(db_file))
