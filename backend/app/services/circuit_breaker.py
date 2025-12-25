import time
import asyncio

class CircuitBreakerOpen(Exception):
    pass


class CircuitBreaker:
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

    async def allow_call(self):
        async with self._lock:
            if self._state == "OPEN":
                if time.time() - self._last_failure >= self.recovery_timeout:
                    self._state = "HALF_OPEN"
                else:
                    raise CircuitBreakerOpen("Image service circuit is open")

    async def record_success(self):
        async with self._lock:
            self._failures = 0
            self._state = "CLOSED"

    async def record_failure(self):
        async with self._lock:
            self._failures += 1
            self._last_failure = time.time()
            if self._failures >= self.failure_threshold:
                self._state = "OPEN"
