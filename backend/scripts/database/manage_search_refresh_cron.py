"""
Manage pg_cron job for refreshing company_search materialized view.

This script deletes any existing cron job and reschedules it fresh.

Usage:
  docker compose exec backend python -m scripts.database.manage_search_refresh_cron
"""

import asyncio
import asyncpg
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

JOB_NAME = "refresh_company_search"
CRON_SCHEDULE = "* * * * *"  # Every minute
REFRESH_COMMAND = "REFRESH MATERIALIZED VIEW CONCURRENTLY proveo.company_search"

# Arbitrary but stable lock ID (any int64 is fine)
ADVISORY_LOCK_ID = 742391845


async def reset_cron_job() -> None:
    """Delete existing cron job (if any) and create a fresh one safely."""
    conn = await asyncpg.connect(settings.alembic_database_url)

    try:
        logger.info("cron_reset_start", job_name=JOB_NAME)

        # Prevent concurrent executions of this script
        await conn.execute("SELECT pg_advisory_lock($1)", ADVISORY_LOCK_ID)

        # Ensure pg_cron exists
        ext_check = await conn.fetchrow(
            "SELECT 1 FROM pg_extension WHERE extname = 'pg_cron'"
        )
        if not ext_check:
            logger.error("pg_cron_not_installed")
            raise RuntimeError("pg_cron extension is not installed")

        # Log existing jobs
        existing_count = await conn.fetchval(
            "SELECT COUNT(*) FROM cron.job WHERE jobname = $1",
            JOB_NAME,
        )
        logger.info("existing_cron_jobs_found", count=existing_count)

        # Delete ALL jobs with this name (single, deterministic statement)
        await conn.execute(
            "SELECT cron.unschedule(jobid) FROM cron.job WHERE jobname = $1",
            JOB_NAME,
        )

        # Schedule fresh job
        result = await conn.fetchrow(
            "SELECT cron.schedule($1, $2, $3) AS jobid",
            JOB_NAME,
            CRON_SCHEDULE,
            REFRESH_COMMAND,
        )

        new_jobid = result["jobid"]
        logger.info("cron_job_created", jobid=new_jobid)

        # Verify exactly one job exists
        final_count = await conn.fetchval(
            "SELECT COUNT(*) FROM cron.job WHERE jobname = $1",
            JOB_NAME,
        )
        if final_count != 1:
            raise RuntimeError(
                f"Expected exactly 1 cron job named '{JOB_NAME}', found {final_count}"
            )

        # Verification details
        verification = await conn.fetchrow(
            """
            SELECT jobid, jobname, schedule, command
            FROM cron.job
            WHERE jobid = $1
            """,
            new_jobid,
        )

        logger.info(
            "cron_reset_complete",
            jobid=verification["jobid"],
            schedule=verification["schedule"],
        )

        print("\nCron job reset completed successfully!")
        print(f"  jobid:    {verification['jobid']}")
        print(f"  jobname:  {verification['jobname']}")
        print(f"  schedule: {verification['schedule']}")
        print(f"  command:  {verification['command']}")

    except Exception as e:
        logger.error("cron_reset_failed", error=str(e), exc_info=True)
        raise

    finally:
        # Always release the lock
        await conn.execute("SELECT pg_advisory_unlock($1)", ADVISORY_LOCK_ID)
        await conn.close()


if __name__ == "__main__":
    asyncio.run(reset_cron_job())
