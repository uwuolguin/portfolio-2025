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


async def reset_cron_job() -> None:
    """Delete existing cron job (if any) and create a fresh one."""
    
    conn = await asyncpg.connect(settings.alembic_database_url)
    
    try:
        logger.info("cron_reset_start", job_name=JOB_NAME)
        
        # First, check if pg_cron extension exists
        ext_check = await conn.fetchrow(
            "SELECT 1 FROM pg_extension WHERE extname = 'pg_cron'"
        )
        if not ext_check:
            logger.error("pg_cron_not_installed")
            print("ERROR: pg_cron extension is not installed!")
            return
        
        # List current jobs to see what exists
        existing_jobs = await conn.fetch(
            "SELECT jobid, jobname, schedule, command FROM cron.job WHERE jobname = $1",
            JOB_NAME
        )
        
        if existing_jobs:
            print(f"Found {len(existing_jobs)} existing job(s) with name '{JOB_NAME}':")
            for job in existing_jobs:
                print(f"  - jobid: {job['jobid']}, schedule: {job['schedule']}")
        else:
            print(f"No existing job found with name '{JOB_NAME}'")
        
        # Delete ALL jobs with this name (using jobid for precision)
        for job in existing_jobs:
            jobid = job['jobid']
            print(f"Deleting job with jobid {jobid}...")
            await conn.execute(
                "SELECT cron.unschedule($1)",
                jobid
            )
            print(f"  Deleted jobid {jobid}")
        
        # Also try unschedule by name just in case
        try:
            await conn.execute(
                "SELECT cron.unschedule($1)",
                JOB_NAME
            )
            print(f"Also ran unschedule by name '{JOB_NAME}'")
        except Exception as e:
            # This might fail if no job with that name exists, which is fine
            print(f"Unschedule by name result: {e}")
        
        # Now schedule a fresh job
        print(f"\nScheduling new cron job '{JOB_NAME}'...")
        result = await conn.fetchrow(
            "SELECT cron.schedule($1, $2, $3) AS jobid",
            JOB_NAME,
            CRON_SCHEDULE,
            REFRESH_COMMAND
        )
        
        new_jobid = result['jobid']
        print(f"SUCCESS: Created new job with jobid {new_jobid}")
        
        # Verify the new job
        verification = await conn.fetchrow(
            "SELECT jobid, jobname, schedule, command FROM cron.job WHERE jobid = $1",
            new_jobid
        )
        
        if verification:
            print(f"\nVerification:")
            print(f"  jobid:    {verification['jobid']}")
            print(f"  jobname:  {verification['jobname']}")
            print(f"  schedule: {verification['schedule']}")
            print(f"  command:  {verification['command']}")
        
        logger.info("cron_reset_complete", new_jobid=new_jobid)
        print("\nCron job reset completed successfully!")
        
    except Exception as e:
        logger.error("cron_reset_failed", error=str(e), exc_info=True)
        print(f"ERROR: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(reset_cron_job())