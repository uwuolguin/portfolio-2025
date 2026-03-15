"""
test_sync_exception_standalone.py aka not importing asyncio when executing asyncio.set_event_looop

Run directly on the worker container — NOT via Temporal.
Simulates what sys.excepthook catches in production: a Python crash
at startup, a missing import, a bad config value, a typo in module code.

    kubectl exec -n portfolio deployment/temporal-worker -- \
      python app/temporal/test_sync_exception_standalone.py

Expected output:
    {"level": "critical", "event": "sync_uncaught_exception", "exc_info": "..."}
"""
from app.middleware.logging import setup_logging, install_sync_exception_handler

setup_logging()
install_sync_exception_handler()

# Simulates a startup crash — misspelled name, bad import, broken config
raise RuntimeError("test sync uncaught exception — simulating worker startup crash")