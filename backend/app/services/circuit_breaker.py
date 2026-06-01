"""Circuit breaker implementation for external service calls."""  # pylint: disable=missing-module-docstring

import time
import asyncio


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""


class CircuitBreaker:
    """Circuit breaker to prevent repeated calls to failing external services."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._failures = 0
        self._last_failure = 0.0
        self._state = "CLOSED"
        self._lock = asyncio.Lock()

    async def allow_call(self):  # pylint: disable=missing-function-docstring
        async with self._lock:
            if self._state == "OPEN":
                if time.time() - self._last_failure >= self.recovery_timeout:
                    self._state = "HALF_OPEN"
                    self._failures = 0
                else:
                    raise CircuitBreakerOpen("Image service circuit is open")
            elif self._state == "HALF_OPEN":
                raise CircuitBreakerOpen("Circuit recovering, probe in progress")

    async def record_success(self):  # pylint: disable=missing-function-docstring
        async with self._lock:
            self._failures = 0
            self._state = "CLOSED"

    async def record_failure(self):  # pylint: disable=missing-function-docstring
        async with self._lock:
            self._failures += 1
            self._last_failure = time.time()
            if self._failures >= self.failure_threshold or self._state == "HALF_OPEN":
                self._state = "OPEN"
