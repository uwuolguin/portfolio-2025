```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from uuid import UUID
import asyncpg
import structlog

from app.database.connection import get_db_read, get_db_write
from app.database.transactions import DB
from app.schemas.products import ProductCreate, ProductUpdate, ProductResponse
from app.auth.dependencies import require_admin, verify_csrf
from app.redis.decorators import cache_response
from app.redis.cache_manager import cache_manager
from app.services.translation_service import translate_field

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/products",
    tags=["products"]
)


@router.get("/", response_model=List[ProductResponse])
@cache_response(key_prefix="products:all", ttl=259200)
async def list_products(
    db: asyncpg.Connection = Depends(get_db_read)
):
    products = await DB.get_all_products(conn=db)
    return products


@router.post(
    "/use-postman-or-similar-to-bypass-csrf",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product (Admin Only)"
)
async def create_product(
    product_data: ProductCreate,
    current_user: dict = Depends(require_admin),
    db: asyncpg.Connection = Depends(get_db_write),
    _: None = Depends(verify_csrf)
):
    try:
        # Translate to get both languages (handles all cases: es only, en only, or both)
        validated_name_es, validated_name_en = await translate_field(
            field_name="name",
            text_es=product_data.name_es,
            text_en=product_data.name_en
        )
        
        product = await DB.create_product(
            conn=db,
            name_es=validated_name_es,
            name_en=validated_name_en
        )

        await cache_manager.invalidate_products()

        return product

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error("create_product_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create product"
        )


@router.put(
    "/{product_uuid}/use-postman-or-similar-to-bypass-csrf",
    response_model=ProductResponse,
    summary="Update a product (Admin Only)"
)
async def update_product(
    product_uuid: UUID,
    product_data: ProductUpdate,
    current_user: dict = Depends(require_admin),
    db: asyncpg.Connection = Depends(get_db_write),
    _: None = Depends(verify_csrf)
):
    try:
        # Translate to get both languages (handles all cases: es only, en only, or both)
        validated_name_es, validated_name_en = await translate_field(
            field_name="name",
            text_es=product_data.name_es,
            text_en=product_data.name_en
        )
        
        product = await DB.update_product_by_uuid(
            conn=db,
            product_uuid=product_uuid,
            name_es=validated_name_es,
            name_en=validated_name_en
        )

        await cache_manager.invalidate_products()

        return product

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("update_product_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update product"
        )


@router.delete(
    "/{product_uuid}/use-postman-or-similar-to-bypass-csrf",
    status_code=status.HTTP_200_OK,
    summary="Delete a product (Admin Only)"
)
async def delete_product(
    product_uuid: UUID,
    current_user: dict = Depends(require_admin),
    db: asyncpg.Connection = Depends(get_db_write),
    _: None = Depends(verify_csrf)
):
    try:
        product = await DB.delete_product_by_uuid(conn=db, product_uuid=product_uuid)

        await cache_manager.invalidate_products()

        logger.info(
            "product_deleted_successfully",
            product_uuid=str(product_uuid),
            product_name=product.name_en,
            admin_email=current_user["email"]
        )

        return {
            "message": "Product successfully deleted",
            "uuid": product.uuid,
            "name_es": product.name_es,
            "name_en": product.name_en
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("product_delete_unexpected_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete product"
        )
```