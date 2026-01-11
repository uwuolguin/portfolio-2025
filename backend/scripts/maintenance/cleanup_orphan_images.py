"""
Cleanup Orphan Images Job

Identifies and deletes images stored in the image service
that are no longer referenced by any company in the database.

Usage:
    python -m app.jobs.cleanup_orphan_images

    Docker:
    docker-compose exec backend python -m app.jobs.cleanup_orphan_images
"""

import asyncio
import asyncpg
import structlog
from contextlib import asynccontextmanager
from typing import Set, List

from app.config import settings
from app.services.image_service_client import image_service_client

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def get_db_connection():
    conn = None
    try:
        conn = await asyncpg.connect(
            dsn=settings.alembic_database_url,
            timeout=30,
            command_timeout=60,
        )
        logger.info("database_connected")
        yield conn
    finally:
        if conn:
            await conn.close()
            logger.info("database_disconnected")


async def get_all_image_filenames_from_service() -> Set[str]:
    import httpx

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{settings.image_service_url}/images")
        response.raise_for_status()
        data = response.json()

        filenames = {obj["name"] for obj in data.get("objects", [])}

        logger.info(
            "images_fetched_from_service",
            count=len(filenames),
        )

        return filenames


async def get_all_referenced_filenames_from_db(
    conn: asyncpg.Connection,
) -> Set[str]:
    rows = await conn.fetch(
        """
        SELECT uuid, image_extension
        FROM proveo.companies
        WHERE uuid IS NOT NULL
          AND image_extension IS NOT NULL
        """
    )

    filenames = {
        f"{row['uuid']}{row['image_extension']}"
        for row in rows
    }

    logger.info(
        "images_fetched_from_database",
        count=len(filenames),
    )

    return filenames


async def delete_orphan_images(orphan_filenames: List[str]) -> int:
    if not orphan_filenames:
        logger.info("no_orphan_images_to_delete")
        return 0

    deleted_count = 0
    failed_count = 0

    for filename in orphan_filenames:
        try:
            success = await image_service_client.delete_image(filename)

            if success:
                logger.info("orphan_image_deleted", filename=filename)
                deleted_count += 1
            else:
                logger.warning("orphan_image_not_found", filename=filename)
                failed_count += 1

        except Exception as e:
            logger.error(
                "orphan_image_delete_failed",
                filename=filename,
                error=str(e),
                exc_info=True,
            )
            failed_count += 1

    logger.info(
        "orphan_cleanup_completed",
        deleted=deleted_count,
        failed=failed_count,
    )

    return deleted_count


async def cleanup_orphan_images():
    logger.info("orphan_cleanup_started")

    service_images = await get_all_image_filenames_from_service()

    async with get_db_connection() as conn:
        db_images = await get_all_referenced_filenames_from_db(conn)

    orphan_images = service_images - db_images

    logger.info(
        "orphan_analysis",
        service_count=len(service_images),
        database_count=len(db_images),
        orphan_count=len(orphan_images),
    )

    if not orphan_images:
        print("\n No orphan images found.")
        return

    orphan_list = sorted(orphan_images)

    print("\nDeleting orphan images:")
    for filename in orphan_list:
        print(f"  - {filename}")

    deleted = await delete_orphan_images(orphan_list)

    print(f"\n Cleanup completed: {deleted} images deleted\n")


async def main():
    await cleanup_orphan_images()


if __name__ == "__main__":
    asyncio.run(main())
