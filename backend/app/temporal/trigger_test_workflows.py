"""
Run this to trigger all four test workflows and watch the worker container logs.

    python trigger_test_workflows.py

Watch logs in the worker container:
    kubectl logs -f -n portfolio deployment/temporal-worker
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
        "TestSyncExceptionWorkflow",
        id="test-sync-exception-1",
        task_queue="auth-queue",
    )
    print("started TestSyncExceptionWorkflow")

    await client.start_workflow(
        "TestCoreLogsWorkflow",
        id="test-core-logs-1",
        task_queue="auth-queue",
    )
    print("started TestCoreLogsWorkflow")


asyncio.run(main())
