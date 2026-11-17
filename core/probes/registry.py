from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger
from core.models import Assumption, NodeStatus
from core.graph_engine import ADIEGraphEngine
from core.probes.base import BaseProbe, ProbeResult
from core.probes.http_probe import HttpProbe, TlsCertificateProbe
from core.probes.socket_probe import SocketPortProbe
from core.probes.json_api_probe import JsonApiProbe

logger = get_logger("probe.registry")

PROBE_REGISTRY: Dict[str, BaseProbe] = {
    "http": HttpProbe(),
    "tls": TlsCertificateProbe(),
    "socket": SocketPortProbe(),
    "json_api": JsonApiProbe(),
}


def register_probe(name: str, probe: BaseProbe) -> None:
    PROBE_REGISTRY[name] = probe


def run_probe_for_assumption(assumption: Assumption) -> Optional[ProbeResult]:
    """Execute the configured probe for a single assumption if configured."""
    if not assumption.probe_type or not assumption.probe_config:
        return None

    probe = PROBE_REGISTRY.get(assumption.probe_type.lower())
    if not probe:
        logger.warning(f"Unknown probe type '{assumption.probe_type}' for assumption {assumption.id}")
        return None

    logger.info(f"Running live probe '{assumption.probe_type}' for assumption {assumption.id}...")
    return probe.run(assumption.probe_config)


def run_all_probes(engine: ADIEGraphEngine, auto_trip: bool = True) -> List[Dict[str, Any]]:
    """Scan all assumptions with attached probes, execute live tests, and optionally trip broken nodes."""
    results = []

    for a in engine.assumptions.values():
        if not a.probe_type:
            continue

        res = run_probe_for_assumption(a)
        if not res:
            continue

        result_entry = {
            "assumption_id": a.id,
            "statement": a.statement,
            "probe_type": a.probe_type,
            "success": res.success,
            "message": res.message,
            "measured_value": res.measured_value,
            "threshold": res.threshold,
        }
        results.append(result_entry)

        if not res.success and auto_trip:
            logger.warning(f"Live probe FAILED for {a.id}: {res.message}. Auto-tripping assumption!")
            engine.invalidate_assumption(a.id, new_confidence=0.0)

    if auto_trip and results:
        engine.propagate_impact()
        engine.auto_save()

    return results
