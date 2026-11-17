from unittest.mock import MagicMock, patch
import pytest

from core.models import Assumption, Decision, DependencyEdge, NodeStatus
from core.graph_engine import ADIEGraphEngine
from core.probes.http_probe import HttpProbe
from core.probes.socket_probe import SocketPortProbe
from core.probes.json_api_probe import JsonApiProbe
from core.probes.registry import run_all_probes


@patch("urllib.request.urlopen")
def test_http_probe_success(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    probe = HttpProbe()
    res = probe.run({"url": "https://api.example.com/health", "max_latency_ms": 2000.0})
    assert res.success is True
    assert res.measured_value is not None


@patch("urllib.request.urlopen")
def test_http_probe_status_failure(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.status = 503
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    probe = HttpProbe()
    res = probe.run({"url": "https://api.example.com/health", "expected_status": 200})
    assert res.success is False
    assert "status mismatch" in res.message


@patch("socket.create_connection")
def test_socket_probe_success(mock_conn):
    mock_conn.return_value.__enter__.return_value = MagicMock()
    probe = SocketPortProbe()
    res = probe.run({"host": "localhost", "port": 5432, "max_connect_time_ms": 1000.0})
    assert res.success is True


@patch("socket.create_connection", side_effect=ConnectionRefusedError("Connection refused"))
def test_socket_probe_failure(mock_conn):
    probe = SocketPortProbe()
    res = probe.run({"host": "localhost", "port": 9999})
    assert res.success is False
    assert "unreachable" in res.message


def test_json_api_numeric_evaluation():
    assert JsonApiProbe._evaluate(120, "<=", 200) is True
    assert JsonApiProbe._evaluate(250, "<=", 200) is False
    assert JsonApiProbe._evaluate(50, ">", 10) is True
    assert JsonApiProbe._evaluate("active", "==", "active") is True
    assert JsonApiProbe._evaluate("down", "!=", "active") is True


@patch("core.probes.http_probe.HttpProbe.run")
def test_run_all_probes_auto_trip(mock_http_run):
    from core.probes.base import ProbeResult
    # Mock probe failure
    mock_http_run.return_value = ProbeResult(
        success=False,
        measured_value=850.0,
        threshold=200.0,
        message="Latency exceeded 200ms",
    )

    engine = ADIEGraphEngine("Live Monitor")
    a = Assumption(
        id="A1",
        statement="Auth API responds under 200ms",
        probe_type="http",
        probe_config={"url": "https://auth.company.com/ping", "max_latency_ms": 200.0},
    )
    d = Decision(id="D1", title="Direct Sync Auth", description="desc", criticality=0.9)
    engine.add_assumption(a)
    engine.add_decision(d)
    engine.add_dependency(DependencyEdge(source_id="A1", target_id="D1", weight=0.9))

    # Before probe, valid
    assert a.status == NodeStatus.VALID
    assert d.status == NodeStatus.VALID

    # Run probes with auto_trip
    results = run_all_probes(engine, auto_trip=True)
    assert len(results) == 1
    assert results[0]["success"] is False

    # After probe failure, A1 must be broken and D1 must be AT_RISK!
    assert a.status == NodeStatus.INVALID
    assert a.confidence == 0.0
    assert d.status == NodeStatus.AT_RISK
    assert d.risk_score > 0.5
