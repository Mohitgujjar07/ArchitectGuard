import json
import urllib.error
import urllib.request
from typing import Any, Dict

from core.logger import get_logger
from core.probes.base import BaseProbe, ProbeResult

logger = get_logger("probe.json_api")


class JsonApiProbe(BaseProbe):
    """Queries a JSON endpoint, extracts a field, and evaluates a numeric or equality assertion."""

    def run(self, config: Dict[str, Any]) -> ProbeResult:
        url = config.get("url")
        if not url:
            return ProbeResult(
                success=False,
                measured_value=None,
                threshold=None,
                message="JsonApi probe missing 'url'",
            )

        field_path = config.get("field_path")  # e.g., "data.memory_mb" or "active_connections"
        operator = config.get("operator", "<=")  # "<", "<=", ">", ">=", "==", "!="
        threshold = config.get("threshold")
        headers = config.get("headers", {})

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "AssumptionPulse-Probe/0.2.0", **headers},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))

                # Extract nested key if field_path provided
                val = data
                if field_path:
                    for key in field_path.split("."):
                        if isinstance(val, dict) and key in val:
                            val = val[key]
                        else:
                            return ProbeResult(
                                success=False,
                                measured_value=None,
                                threshold=threshold,
                                message=f"Field path '{field_path}' not found in response JSON",
                            )

                # Evaluate operator
                passed = self._evaluate(val, operator, threshold)
                if passed:
                    return ProbeResult(
                        success=True,
                        measured_value=val,
                        threshold=f"{operator} {threshold}",
                        message=f"JSON field '{field_path}' is {val} (condition {operator} {threshold} met)",
                        details={"url": url, "extracted": val},
                    )
                else:
                    return ProbeResult(
                        success=False,
                        measured_value=val,
                        threshold=f"{operator} {threshold}",
                        message=f"Assertion failed: {val} is not {operator} {threshold}",
                        details={"url": url, "extracted": val},
                    )

        except Exception as e:
            return ProbeResult(
                success=False,
                measured_value=None,
                threshold=threshold,
                message=f"Failed to query JSON API: {e}",
                details={"url": url},
            )

    @staticmethod
    def _evaluate(val: Any, operator: str, threshold: Any) -> bool:
        if threshold is None:
            return bool(val)

        try:
            # Try numeric comparison if possible
            n_val = float(val)
            n_thresh = float(threshold)
            if operator == "<":
                return n_val < n_thresh
            if operator == "<=":
                return n_val <= n_thresh
            if operator == ">":
                return n_val > n_thresh
            if operator == ">=":
                return n_val >= n_thresh
            if operator == "==":
                return n_val == n_thresh
            if operator == "!=":
                return n_val != n_thresh
        except (ValueError, TypeError):
            pass

        # String comparison fallback
        if operator == "==":
            return str(val) == str(threshold)
        if operator == "!=":
            return str(val) != str(threshold)

        return False
