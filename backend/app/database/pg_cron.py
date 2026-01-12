import structlog
from app.database.connection import pool_manager

logger = structlog.get_logger(__name__)

REFRESH_JOB_NAME = "refresh_company_search"
REFRESH_SCHEDULE = "* * * * *"
REFRESH_COMMAND = "REFRESH MATERIALIZED VIEW CONCURRENTLY proveo.company_search"


async def schedule_pg_cron_jobs():
    if not pool_manager.write_pool:
        logger.warning("pg_cron_schedule_skipped_no_pool")
        return

    try:
        async with pool_manager.write_pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_cron")

            await conn.execute(
                "SELECT cron.unschedule(jobname) FROM cron.job WHERE jobname = $1",
                REFRESH_JOB_NAME
            )

            await conn.execute(
                "SELECT cron.schedule($1, $2, $3)",
                REFRESH_JOB_NAME,
                REFRESH_SCHEDULE,
                REFRESH_COMMAND
            )

        logger.info("pg_cron_job_scheduled", job=REFRESH_JOB_NAME, schedule=REFRESH_SCHEDULE)
    except Exception as e:
        logger.error("pg_cron_schedule_failed", error=str(e))


async def unschedule_pg_cron_jobs():
    if not pool_manager.write_pool:
        return

    try:
        async with pool_manager.write_pool.acquire() as conn:
            await conn.execute(
                "SELECT cron.unschedule(jobname) FROM cron.job WHERE jobname = $1",
                REFRESH_JOB_NAME
            )
        logger.info("pg_cron_job_unscheduled", job=REFRESH_JOB_NAME)
    except Exception as e:
        logger.error("pg_cron_unschedule_failed", error=str(e))