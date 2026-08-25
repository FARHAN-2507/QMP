"""Smoke-test rule interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from querymind.smoke.models import SmokeTestResult

if TYPE_CHECKING:
    from querymind.smoke.config import SmokeSettings
    from querymind.smoke.models import ApiRequest, HttpExchange


class SmokeTestRule(ABC):
    """Extensible smoke-test rule. Implement evaluate() only."""

    @property
    @abstractmethod
    def test_id(self) -> str:
        """Stable identifier, e.g. SMOKE-01."""

    @property
    @abstractmethod
    def test_name(self) -> str:
        """Human-readable name."""

    @property
    def category(self) -> str:
        return "generic"

    @abstractmethod
    def evaluate(
        self,
        request: ApiRequest,
        exchange: HttpExchange | None,
        settings: SmokeSettings,
    ) -> SmokeTestResult:
        """Run the rule against the request and optional HTTP exchange."""
