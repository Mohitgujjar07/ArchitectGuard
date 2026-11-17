import datetime
import socket
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict

from core.logger import get_logger
from core.probes.base import BaseProbe, ProbeResult

logger = get_logger("probe.http")


class HttpProbe(BaseProbe):
    """Measures real HTTP latency, HTTP status code, and TLS/SSL certificate expiry."""

    def run(self, config: Dict[str, Any]) -> ProbeResult:
        url = config.get("url")
        if not url:
            return ProbeResult(
                success=False,
                measured_value=None,
                threshold=None,
                message="HTTP probe missing required 'url' configuration",
            )

        max_latency_ms = config.get("max_latency_ms", 1000.0)
        expected_status = config.get("expected_status", 200)
        timeout_sec = config.get("timeout_sec", 5.0)

        start_time = time.perf_counter()
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "AssumptionPulse-Watchdog/0.2.0"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                status_code = resp.status

                if status_code != expected_status:
                    return ProbeResult(
                        success=False,
                        measured_value=status_code,
                        threshold=expected_status,
                        message=f"HTTP status mismatch: received {status_code}, expected {expected_status}",
                        details={"latency_ms": elapsed_ms, "url": url},
                    )

                if elapsed_ms > max_latency_ms:
                    return ProbeResult(
                        success=False,
                        measured_value=elapsed_ms,
                        threshold=max_latency_ms,
                        message=f"Latency threshold exceeded: {elapsed_ms}ms > {max_latency_ms}ms limit",
                        details={"status_code": status_code, "url": url},
                    )

                return ProbeResult(
                    success=True,
                    measured_value=elapsed_ms,
                    threshold=max_latency_ms,
                    message=f"HTTP request OK: {status_code} in {elapsed_ms}ms (limit: {max_latency_ms}ms)",
                    details={"status_code": status_code, "latency_ms": elapsed_ms, "url": url},
                )

        except urllib.error.HTTPError as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return ProbeResult(
                success=False,
                measured_value=e.code,
                threshold=expected_status,
                message=f"HTTP error {e.code}: {e.reason}",
                details={"latency_ms": elapsed_ms, "url": url},
            )
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return ProbeResult(
                success=False,
                measured_value=None,
                threshold=max_latency_ms,
                message=f"Connection failed: {e}",
                details={"latency_ms": elapsed_ms, "url": url},
            )


class TlsCertificateProbe(BaseProbe):
    """Connects to host and verifies TLS certificate is not expired or near expiry."""

    def run(self, config: Dict[str, Any]) -> ProbeResult:
        host = config.get("host")
        port = config.get("port", 443)
        min_days_remaining = config.get("min_days_remaining", 14)

        if not host:
            return ProbeResult(
                success=False,
                measured_value=None,
                threshold=None,
                message="TLS probe missing required 'host'",
            )

        context = ssl.create_default_context()
        try:
            with socket.create_connection((host, port), timeout=5.0) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    expiry_str = cert["notAfter"]
                    # Format: 'May 15 12:00:00 2026 GMT'
                    expiry_date = datetime.datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
                    now = datetime.datetime.utcnow()
                    days_remaining = (expiry_date - now).days

                    if days_remaining < min_days_remaining:
                        return ProbeResult(
                            success=False,
                            measured_value=days_remaining,
                            threshold=min_days_remaining,
                            message=f"Certificate expires in {days_remaining} days (threshold: {min_days_remaining} days)",
                            details={"expiry_date": expiry_str, "host": host},
                        )

                    return ProbeResult(
                        success=True,
                        measured_value=days_remaining,
                        threshold=min_days_remaining,
                        message=f"Certificate valid for {days_remaining} more days (expires {expiry_date.strftime('%Y-%m-%d')})",
                        details={"expiry_date": expiry_str, "host": host},
                    )
        except Exception as e:
            return ProbeResult(
                success=False,
                measured_value=None,
                threshold=min_days_remaining,
                message=f"Failed to check TLS cert for {host}: {e}",
                details={"host": host, "port": port},
            )
