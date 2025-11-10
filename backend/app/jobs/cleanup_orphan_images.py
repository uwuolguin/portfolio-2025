"""
Cleanup orphan images - removes image files that don't have corresponding user records
Run this as a scheduled job (e.g., daily via cron)

Usage:
  python -m app.jobs.cleanup_orphan_images
  docker compose exec backend python -m app.jobs.cleanup_orphan_images
"""
import asyncio
import asyncpg
import uuid
from pathlib import Path
from app.config import settings
from app.utils.file_handler import FileHandler
import structlog

logger = structlog.get_logger(__name__)


async def get_all_active_user_uuids() -> set[str]:
    conn = await asyncpg.connect(settings.alembic_database_url)
    try:
        active_users = await conn.fetch("SELECT uuid FROM proveo.users")
        return {str(row['uuid']) for row in active_users}
    finally:
        await conn.close()


async def cleanup_orphan_images(dry_run: bool = True):
    logger.info("starting_orphan_image_cleanup", dry_run=dry_run)
    active_user_uuids = await get_all_active_user_uuids()
    logger.info("active_users_found", count=len(active_user_uuids))

    upload_dir = FileHandler.UPLOAD_DIR
    if not upload_dir.exists():
        logger.error("upload_directory_not_found", path=str(upload_dir))
        return

    filesystem_files = list(upload_dir.glob("*"))
    logger.info("filesystem_files_found", count=len(filesystem_files))

    orphans = []
    for file_path in filesystem_files:
        if not file_path.is_file():
            continue
        file_uuid = file_path.stem
        try:
            uuid.UUID(file_uuid)
        except ValueError:
            logger.debug("skipping_non_uuid_file", filename=file_path.name)
            continue
        if file_uuid not in active_user_uuids:
            orphans.append(file_path)

    logger.info("orphan_images_detected", count=len(orphans))
    if not orphans:
        logger.info("no_orphan_images_found")
        return

    total_size_kb = 0
    for orphan in orphans:
        size_kb = orphan.stat().st_size / 1024
        total_size_kb += size_kb
        logger.info(
            "orphan_image",
            filename=orphan.name,
            user_uuid=orphan.stem,
            size_kb=f"{size_kb:.2f}",
            path=str(orphan)
        )

    logger.info(
        "orphan_summary",
        total_orphans=len(orphans),
        total_size_kb=f"{total_size_kb:.2f}",
        total_size_mb=f"{total_size_kb / 1024:.2f}"
    )

    if not dry_run:
        deleted_count = 0
        failed_count = 0
        for orphan in orphans:
            try:
                orphan.unlink()
                deleted_count += 1
                logger.info("orphan_deleted", filename=orphan.name, user_uuid=orphan.stem)
            except Exception as e:
                failed_count += 1
                logger.error(
                    "orphan_deletion_failed",
                    filename=orphan.name,
                    user_uuid=orphan.stem,
                    error=str(e)
                )
        logger.info(
            "cleanup_complete",
            total_orphans=len(orphans),
            deleted=deleted_count,
            failed=failed_count,
            disk_space_freed_mb=f"{total_size_kb / 1024:.2f}"
        )
    else:
        logger.info(
            "dry_run_complete",
            message="Run with --execute to actually delete files",
            potential_disk_space_freed_mb=f"{total_size_kb / 1024:.2f}"
        )


if __name__ == "__main__":
    import sys
    execute = "--execute" in sys.argv

    if execute:
        print(" Running in EXECUTE mode - files will be deleted")
    else:
        print(" Running in DRY RUN mode - no files will be deleted")
        print("   Use --execute flag to actually delete orphan images")

    print()
    asyncio.run(cleanup_orphan_images(dry_run=not execute))
