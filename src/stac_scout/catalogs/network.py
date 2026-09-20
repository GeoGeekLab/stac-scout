from __future__ import annotations

from dataclasses import dataclass

from urllib3 import Retry


@dataclass(frozen=True, slots=True)
class ProviderNetworkPolicy:
    connect_timeout_s: float = 5.0
    read_timeout_s: float = 20.0
    max_retries: int = 2
    backoff_factor_s: float = 0.5
    backoff_jitter_s: float = 0.25
    retry_statuses: tuple[int, ...] = (429, 502, 503, 504)

    def __post_init__(self) -> None:
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

    @property
    def timeout(self) -> tuple[float, float]:
        return (self.connect_timeout_s, self.read_timeout_s)

    def retry(self) -> Retry:
        return Retry(
            total=self.max_retries,
            connect=self.max_retries,
            read=self.max_retries,
            status=self.max_retries,
            backoff_factor=self.backoff_factor_s,
            backoff_jitter=self.backoff_jitter_s,
            status_forcelist=self.retry_statuses,
            allowed_methods=None,
            respect_retry_after_header=True,
            raise_on_status=True,
        )
