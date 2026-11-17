import pytest

from core.models import Assumption, Decision, DependencyEdge, NodeStatus
from core.graph_engine import ADIEGraphEngine
from core.storage import ProjectStore


def test_storage_save_and_load(temp_db):
    engine = ADIEGraphEngine(project_name="FinTech Backend")
    engine.add_assumption(Assumption(id="A1", statement="Payment gateway SLA is 99.99%"))
    engine.add_decision(Decision(id="D1", title="Direct API payments", description="No fallback"))
    engine.add_dependency(DependencyEdge(source_id="A1", target_id="D1", weight=0.9))

    temp_db.save_project(engine)
    assert temp_db.project_exists("FinTech Backend")

    # Load back
    data = temp_db.load_project_data("FinTech Backend")
    assert data.project_name == "FinTech Backend"
    assert len(data.assumptions) == 1
    assert data.assumptions[0].id == "A1"
    assert len(data.decisions) == 1
    assert len(data.dependencies) == 1

    restored_engine = ADIEGraphEngine.from_project_data(data)
    assert "A1" in restored_engine.assumptions
    assert "D1" in restored_engine.decisions


def test_storage_auto_save_hook(temp_db):
    engine = ADIEGraphEngine(project_name="AutoSave Project")
    engine.attach_storage(temp_db)

    # Adding node should trigger auto-save
    engine.add_assumption(Assumption(id="A1", statement="Memory stays under 1GB"))
    assert temp_db.project_exists("AutoSave Project")

    # Reload from DB and verify
    data = temp_db.load_project_data("AutoSave Project")
    assert len(data.assumptions) == 1


def test_storage_multi_project(temp_db):
    engine1 = ADIEGraphEngine("Project One")
    engine2 = ADIEGraphEngine("Project Two")

    temp_db.save_project(engine1)
    temp_db.save_project(engine2)

    projects = temp_db.list_projects()
    names = [p["name"] for p in projects]
    assert "Project One" in names
    assert "Project Two" in names


def test_storage_delete_project(temp_db):
    engine = ADIEGraphEngine("To Delete")
    temp_db.save_project(engine)
    assert temp_db.project_exists("To Delete")

    deleted = temp_db.delete_project("To Delete")
    assert deleted is True
    assert not temp_db.project_exists("To Delete")


def test_load_nonexistent_project_raises(temp_db):
    with pytest.raises(KeyError, match="not found in store"):
        temp_db.load_project_data("Does Not Exist")
