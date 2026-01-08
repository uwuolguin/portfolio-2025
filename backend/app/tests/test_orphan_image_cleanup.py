"""
Test for orphan image cleanup logic.
Run with: pytest app/tests/test_orphan_image_cleanup.py -v

Tests that the orphan image detection correctly identifies images
that exist in storage but are not referenced in the database.
"""
import pytest
import asyncpg
import ssl
import uuid
import base64
from io import BytesIO
from contextlib import asynccontextmanager

# Import settings
import sys
sys.path.insert(0, '/app')
from app.config import settings
from app.services.image_service_client import image_service_client


@asynccontextmanager
async def get_conn():
    """Get database connection with SSL"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    conn = await asyncpg.connect(
        dsn=settings.alembic_database_url,
        ssl=ssl_context,
        timeout=30,
    )
    try:
        yield conn
    finally:
        await conn.close()


def create_test_image() -> BytesIO:
    """
    Create a minimal valid 1x1 red JPEG image without PIL.
    This is a base64-encoded minimal JPEG.
    """
    # Minimal 1x1 red pixel JPEG (created with PIL, then base64 encoded)
    minimal_jpeg_b64 = (
        "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkS"
        "Ew8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJ"
        "CQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
        "MjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/"
        "xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwAB//2Q=="
    )
    jpeg_bytes = base64.b64decode(minimal_jpeg_b64)
    return BytesIO(jpeg_bytes)


@pytest.mark.asyncio
async def test_orphan_image_detection_and_cleanup():
    """
    Test orphan image detection logic:
    1. Upload a test image that won't be referenced in DB
    2. Verify it's detected as an orphan
    3. Delete it and verify cleanup works
    """
    # Generate unique ID for this test
    orphan_id = f"orphan_test_{uuid.uuid4().hex[:8]}"
    extension = ".jpg"
    filename = f"{orphan_id}{extension}"
    
    try:
        # 1. Create and upload a test image (this will be an orphan)
        test_image = create_test_image()
        
        upload_result = await image_service_client.upload_image_streaming(
            file_obj=test_image,
            company_id=orphan_id,
            content_type="image/jpeg",
            extension=extension,
            user_id="test_user",
        )
        
        assert upload_result["image_id"] == orphan_id
        print(f"✓ Uploaded test image: {filename}")
        
        # 2. Get all images from service
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{settings.image_service_url}/images")
            response.raise_for_status()
            data = response.json()
            service_images = {obj["name"] for obj in data.get("objects", [])}
        
        assert filename in service_images, f"Test image {filename} not found in service"
        print(f"✓ Image exists in storage service")
        
        # 3. Get all referenced images from database
        async with get_conn() as conn:
            rows = await conn.fetch("""
                SELECT image_url, image_extension
                FROM proveo.companies
                WHERE image_url IS NOT NULL AND image_extension IS NOT NULL
            """)
            db_images = {
                f"{row['image_url']}{row['image_extension']}"
                for row in rows
            }
        
        # 4. Verify our test image is NOT in the database (it's an orphan)
        assert filename not in db_images, "Test image should not be in database"
        print(f"✓ Image correctly not referenced in database (orphan)")
        
        # 5. Calculate orphans (same logic as cleanup script)
        orphan_images = service_images - db_images
        assert filename in orphan_images, "Test image should be detected as orphan"
        print(f"✓ Image correctly detected as orphan")
        
        # 6. Delete the orphan image
        deleted = await image_service_client.delete_image(filename)
        assert deleted, "Failed to delete orphan image"
        print(f"✓ Orphan image deleted successfully")
        
        # 7. Verify it's gone
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{settings.image_service_url}/images")
            response.raise_for_status()
            data = response.json()
            remaining_images = {obj["name"] for obj in data.get("objects", [])}
        
        assert filename not in remaining_images, "Orphan image should be deleted"
        print(f"✓ Verified image no longer exists in storage")
        
        print(f"\n✓ Orphan image cleanup test passed!")
        
    except Exception as e:
        # Cleanup on failure
        try:
            await image_service_client.delete_image(filename)
        except:
            pass
        raise