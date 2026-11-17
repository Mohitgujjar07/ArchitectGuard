from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from core.logger import get_logger
from core.models import Assumption, Decision, DependencyEdge, NodeStatus, ProjectGraphData
from core.graph_engine import ADIEGraphEngine
from core.storage import ProjectStore

logger = get_logger("api")

app = FastAPI(
    title="ArchitectGuard API",
    description="REST API for Architectural Decision Watchdogs, Risk Propagation, and Live Probes.",
    version="0.2.0",
)

DEFAULT_DB = ".architectguard/store.db"


def get_engine() -> ADIEGraphEngine:
    db_path = DEFAULT_DB if Path(DEFAULT_DB).exists() else (
        ".assumptionpulse/store.db" if Path(".assumptionpulse/store.db").exists() else DEFAULT_DB
    )
    store = ProjectStore(db_path)
    projects = store.list_projects()
    if not projects:
        # Fall back to sample scenario if present
        sample = Path("data/sample_scenario.json")
        if sample.exists():
            engine = ADIEGraphEngine.from_json(str(sample))
            engine.attach_storage(store)
            store.save_project(engine)
            return engine
        engine = ADIEGraphEngine("Default Project")
        engine.attach_storage(store)
        store.save_project(engine)
        return engine

    active_name = projects[0]["name"]
    data = store.load_project_data(active_name)
    engine = ADIEGraphEngine.from_project_data(data)
    engine.attach_storage(store)
    return engine


class SimulateRequest(BaseModel):
    broken_assumption_id: str
    replace_decision_id: str
    alt_title: str
    support_assumption_id: str
    dep_weight: float = 0.75


class CheckRequest(BaseModel):
    fail_on_expired: bool = True
    fail_on_risk_above: float = 0.5


class FactEvaluationRequest(BaseModel):
    fact: str
    auto_propagate: bool = True


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/api/projects", tags=["Projects"])
def list_projects():
    store = ProjectStore(DEFAULT_DB)
    return {"projects": store.list_projects()}


@app.get("/api/status", tags=["Graph & Health"])
def get_architecture_status():
    engine = get_engine()
    engine.propagate_impact()

    total_blast = round(
        sum(d.risk_score for d in engine.decisions.values() if d.status != NodeStatus.ARCHIVED), 4
    )
    at_risk_count = sum(1 for d in engine.decisions.values() if d.status == NodeStatus.AT_RISK)
    invalid_count = sum(1 for a in engine.assumptions.values() if a.status == NodeStatus.INVALID)

    return {
        "project_name": engine.project_name,
        "total_blast_radius": total_blast,
        "at_risk_count": at_risk_count,
        "invalid_assumptions_count": invalid_count,
        "assumptions": list(engine.assumptions.values()),
        "decisions": list(engine.decisions.values()),
        "dependencies": [
            {
                "source": u,
                "target": v,
                "weight": d["weight"],
                "rationale": d.get("rationale", ""),
            }
            for u, v, d in engine.graph.edges(data=True)
        ],
    }


@app.post("/api/check", tags=["CI/CD"])
def run_ci_check(req: CheckRequest):
    engine = get_engine()
    engine.propagate_impact()

    today = date.today()
    expired = [
        a for a in engine.assumptions.values()
        if a.valid_until and today > a.valid_until and a.status != NodeStatus.INVALID
    ]
    high_risk = [d for d in engine.decisions.values() if d.risk_score >= req.fail_on_risk_above]

    failed = (bool(expired) and req.fail_on_expired) or bool(high_risk)

    return {
        "passed": not failed,
        "expired_assumptions": expired,
        "high_risk_decisions": high_risk,
    }


@app.post("/api/simulate", tags=["Counterfactual Simulation"])
def simulate_decision_replacement(req: SimulateRequest):
    engine = get_engine()
    cand = Decision(
        id=f"{req.replace_decision_id}_ALT",
        title=req.alt_title,
        description=f"Candidate alternative to {req.replace_decision_id}",
        criticality=0.85,
    )
    deps = [
        DependencyEdge(
            source_id=req.support_assumption_id,
            target_id=cand.id,
            weight=req.dep_weight,
        )
    ]

    blast_radius, remaining = engine.simulate_what_if(
        broken_assumption_id=req.broken_assumption_id,
        candidate_decision=cand,
        candidate_dependencies=deps,
        replaced_decision_id=req.replace_decision_id,
    )

    return {
        "simulated_blast_radius": blast_radius,
        "remaining_at_risk_decisions": remaining,
    }


@app.post("/api/assumptions", status_code=status.HTTP_201_CREATED, tags=["CRUD"])
def create_assumption(assumption: Assumption):
    engine = get_engine()
    try:
        engine.add_assumption(assumption)
        return {"message": f"Added assumption {assumption.id}", "assumption": assumption}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/decisions", status_code=status.HTTP_201_CREATED, tags=["CRUD"])
def create_decision(decision: Decision):
    engine = get_engine()
    try:
        engine.add_decision(decision)
        return {"message": f"Added decision {decision.id}", "decision": decision}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/dependencies", status_code=status.HTTP_201_CREATED, tags=["CRUD"])
def create_dependency(edge: DependencyEdge):
    engine = get_engine()
    try:
        engine.add_dependency(edge)
        engine.propagate_impact()
        engine.auto_save()
        return {"message": f"Linked {edge.source_id} -> {edge.target_id}", "edge": edge}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
