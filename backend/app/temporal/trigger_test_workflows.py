"""
Run this to trigger Temporal test workflows and watch the worker container logs.

    kubectl exec -n portfolio deployment/backend -- \
      python -m app.temporal.trigger_test_workflows

Watch logs in the worker container:
    kubectl logs -f -n portfolio deployment/temporal-worker

For sync exception testing run separately — it requires a direct process crash:
    kubectl exec -n portfolio deployment/temporal-worker -- \
      python app/temporal/test_sync_exception_standalone.py
"""
import asyncio
from temporalio.client import Client
from app.config import settings


async def main():
    client = await Client.connect(settings.temporal_host)

    await client.start_workflow(
        "TestSdkLogsWorkflow",
        id="test-sdk-logs-1",
        task_queue="auth-queue",
    )
    print("started TestSdkLogsWorkflow")

    await client.start_workflow(
        "TestAsyncExceptionWorkflow",
        id="test-async-exception-1",
        task_queue="auth-queue",
    )
    print("started TestAsyncExceptionWorkflow")

    await client.start_workflow(
        "TestCoreLogsWorkflow",
        id="test-core-logs-1",
        task_queue="auth-queue",
    )
    print("started TestCoreLogsWorkflow")


asyncio.run(main())