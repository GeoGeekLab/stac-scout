from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from urllib3 import Retry


class BoundedRetry(Retry):
    """urllib3 Retry that caps server-provided Retry-After delays."""

    def __init__(
        self,
        *args: Any,
        max_retry_after_s: float = 10.0,
        **kwargs: Any,
    ) -> None:
        self.max_retry_after_s = max_retry_after_s
        super().__init__(*args, **kwargs)

    def new(self, **kw: Any) -> BoundedRetry:
        kw.setdefault("max_retry_after_s", self.max_retry_after_s)
        return super().new(**kw)

    def get_retry_after(self, response: Any) -> float | None:
        retry_after = super().get_retry_after(response)
        if retry_after is None:
            return None
        return min(float(retry_after), self.max_retry_after_s)


@dataclass(frozen=True, slots=True)
class ProviderNetworkPolicy:
    connect_timeout_s: float = 5.0
    read_timeout_s: float = 20.0
    max_retries: int = 2
    backoff_factor_s: float = 0.5
    backoff_jitter_s: float = 0.25
    max_retry_delay_s: float = 10.0
    retry_statuses: tuple[int, ...] = (408, 429, 500, 502, 503, 504)

    def __post_init__(self) -> None:
        for name, value in (
            ("connect_timeout_s", self.connect_timeout_s),
            ("read_timeout_s", self.read_timeout_s),
            ("backoff_factor_s", self.backoff_factor_s),
            ("backoff_jitter_s", self.backoff_jitter_s),
            ("max_retry_delay_s", self.max_retry_delay_s),
        ):
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")

        if self.connect_timeout_s <= 0:
            raise ValueError("connect_timeout_s must be positive")
        if self.read_timeout_s <= 0:
            raise ValueError("read_timeout_s must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")
        if self.backoff_factor_s < 0:
            raise ValueError("backoff_factor_s must not be negative")
        if self.backoff_jitter_s < 0:
            raise ValueError("backoff_jitter_s must not be negative")
        if self.max_retry_delay_s <= 0:
            raise ValueError("max_retry_delay_s must be positive")
        if not self.retry_statuses:
            raise ValueError("retry_statuses must not be empty")
        if any(status < 100 or status > 599 for status in self.retry_statuses):
            raise ValueError("retry_statuses must contain valid HTTP status codes")

    @property
    def timeout(self) -> tuple[float, float]:
        return (self.connect_timeout_s, self.read_timeout_s)

    def retry(self) -> Retry:
        return BoundedRetry(
            total=self.max_retries,
            connect=self.max_retries,
            read=self.max_retries,
            status=self.max_retries,
            backoff_factor=self.backoff_factor_s,
            backoff_jitter=self.backoff_jitter_s,
            backoff_max=self.max_retry_delay_s,
            status_forcelist=self.retry_statuses,
            allowed_methods=frozenset({"GET", "POST"}),
            respect_retry_after_header=True,
            raise_on_status=True,
            max_retry_after_s=self.max_retry_delay_s,
        )
