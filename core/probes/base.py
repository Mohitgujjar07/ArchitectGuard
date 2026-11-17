from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel


class ProbeResult(BaseModel):
    success: bool
    measured_value: Any
    threshold: Any
    message: str
    details: Dict[str, Any] = {}


class BaseProbe(ABC):
    """Abstract base class for all live operational probes."""

    @abstractmethod
    def run(self, config: Dict[str, Any]) -> ProbeResult:
        """Execute the live probe and return a structured ProbeResult."""
        pass
