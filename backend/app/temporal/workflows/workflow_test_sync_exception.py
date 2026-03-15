"""
Triggers: threading.excepthook (NOT sys.excepthook — Temporal catches everything
          in the main thread so sys.excepthook never fires from workflow/activity code.
          The closest equivalent is an unhandled exception in a spawned thread.)
How: activity spawns a thread that raises unhandled.
Expected log: printed to stderr by Python's threading.excepthook default,
              OR install a custom threading.excepthook the same way
              you installed sys.excepthook.
NOTE: to capture this in structlog JSON, add to worker.py:
      import threading
      threading.excepthook = lambda args: <your structlog handler>
"""
import threading
from datetime import timedelta
from temporalio import workflow, activity


@activity.defn
async def activity_thread_exception() -> str:
    def bad_thread():
        raise RuntimeError("test sync uncaught exception from thread")

    t = threading.Thread(target=bad_thread, daemon=True)
    t.start()
    t.join()  # join so activity waits for the thread to finish
    return "thread_exception_done"


@workflow.defn
class TestSyncExceptionWorkflow:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(
            activity_thread_exception,
            start_to_close_timeout=timedelta(seconds=10),
        )
