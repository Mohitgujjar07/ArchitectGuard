import socket
import time
from typing import Any, Dict

from core.logger import get_logger
from core.probes.base import BaseProbe, ProbeResult

logger = get_logger("probe.socket")


class SocketPortProbe(BaseProbe):
    """Verifies that a target database or backend service TCP port is actively accepting connections."""

    def run(self, config: Dict[str, Any]) -> ProbeResult:
        host = config.get("host", "localhost")
        port = config.get("port")
        timeout_sec = config.get("timeout_sec", 3.0)
        max_connect_time_ms = config.get("max_connect_time_ms", 500.0)

        if not port:
            return ProbeResult(
                success=False,
                measured_value=None,
                threshold=None,
                message="Socket probe missing required 'port'",
            )

        start = time.perf_counter()
        try:
            with socket.create_connection((host, int(port)), timeout=timeout_sec):
                elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
                if elapsed_ms > max_connect_time_ms:
                    return ProbeResult(
                        success=False,
                        measured_value=elapsed_ms,
                        threshold=max_connect_time_ms,
                        message=f"TCP connection slow: {elapsed_ms}ms > {max_connect_time_ms}ms",
                        details={"host": host, "port": port},
                    )

                return ProbeResult(
                    success=True,
                    measured_value=elapsed_ms,
                    threshold=max_connect_time_ms,
                    message=f"TCP port {port} reachable in {elapsed_ms}ms",
                    details={"host": host, "port": port, "connect_time_ms": elapsed_ms},
                )
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
            return ProbeResult(
                success=False,
                measured_value=None,
                threshold=max_connect_time_ms,
                message=f"Port {port} unreachable on {host}: {e}",
                details={"host": host, "port": port, "elapsed_ms": elapsed_ms},
            )
