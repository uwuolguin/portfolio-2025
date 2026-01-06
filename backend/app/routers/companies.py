"""
Companies Router

API endpoints for company management including:
- Company CRUD operations
- Search functionality
- Admin management
"""

from fastapi import (
    APIRouter, Depends, HTTPException, status, 
    UploadFile, File, Query, Form
)
from typing import List, Optional
from uuid import UUID
import asyncpg
import uuid
import structlog

from app.database.connection import get_db
from app.database.transactions import DB
from app.auth.dependencies import (
    require_verified_email,
    require_admin,
    verify_csrf,
    get_current_user,
)
from app.schemas.companies import (
    CompanyResponse,
    CompanySearchResponse,
    CompanyDeleteResponse,
)
from app.services.translation_service import translate_field
from app.services.image_service_client import image_service_client
from app.utils.exceptions import (
    NotFoundError,
    ConflictError,
    ValidationErrorResponse,
    ServiceUnavailableError
)
from app.utils.validators import (
    validate_name,
    validate_email,
    validate_phone,
    validate_address,
    validate_description,
    validate_language,
    normalize_whitespace,
    ValidationError
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/companies", tags=["companies"])


async def resolve_commune_uuid(conn: asyncpg.Connection, commune_name: str) -> UUID:
    """Convert commune name to UUID"""
    normalized = normalize_whitespace(commune_name)
    result = await conn.fetchrow(
        "SELECT uuid FROM proveo.communes WHERE name = $1",
        normalized
    )
    if not result:
        raise ValidationErrorResponse(
            message=f"Commune '{normalized}' not found",
            field="commune_name"
        )
    return result['uuid']


async def resolve_product_uuid(conn: asyncpg.Connection, product_name: str, lang: str) -> UUID:
    """Convert product name (in current language) to UUID"""
    normalized = normalize_whitespace(product_name)
    if lang == 'es':
        result = await conn.fetchrow(
            "SELECT uuid FROM proveo.products WHERE name_es = $1",
            normalized
        )
    else:
        result = await conn.fetchrow(
            "SELECT uuid FROM proveo.products WHERE name_en = $1",
            normalized
        )
    
    if not result:
        raise ValidationErrorResponse(
            message=f"Product '{normalized}' not found",
            field="product_name"
        )
    return result['uuid']


@router.get(
    "/search",
    response_model=List[CompanySearchResponse],
    summary="Search companies",
)
async def search_companies(
    q: Optional[str] = Query(None, description="Search query"),
    commune: Optional[str] = Query(None, description="Filter by commune name"),
    product: Optional[str] = Query(None, description="Filter by product name"),
    lang: str = Query("es", pattern="^(es|en)$", description="Response language"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results to skip"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Search companies with optional filters.
    
    - Full-text search on company data
    - Filter by commune or product
    - Paginated results
    """
    try:
        # Normalize search parameters
        search_query = normalize_whitespace(q) if q else ""
        commune_filter = normalize_whitespace(commune) if commune else None
        product_filter = normalize_whitespace(product) if product else None
        
        return await DB.search_companies(
            conn=db,
            query=search_query,
            lang=lang,
            commune=commune_filter,
            product=product_filter,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error("search_companies_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )


@router.get(
    "/user/my-company",
    response_model=CompanyResponse,
    summary="Get my company",
)
async def get_my_company(
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get the current user's company.
    """
    user_uuid = UUID(current_user["sub"])

    try:
        company = await DB.get_company_by_user_uuid(db, user_uuid)
        if not company:
            raise NotFoundError(resource="company", identifier=f"user:{user_uuid}")

        response_dict = company.model_dump()
        response_dict["image_url"] = image_service_client.build_image_url(
            company.image_url,
            company.image_extension,
        )
        return CompanyResponse(**response_dict)

    except NotFoundError:
        raise
    except Exception as e:
        logger.error(
            "get_my_company_error",
            user_uuid=str(user_uuid),
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve company"
        )


@router.get(
    "/{company_uuid}",
    response_model=CompanyResponse,
    summary="Get company by UUID",
)
async def get_company(
    company_uuid: UUID,
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get a company by its UUID (public endpoint).
    """
    try:
        company = await DB.get_company_by_uuid(db, company_uuid)
        if not company:
            raise NotFoundError(resource="company", identifier=str(company_uuid))

        response_dict = company.model_dump()
        response_dict["image_url"] = image_service_client.build_image_url(
            company.image_url,
            company.image_extension,
        )
        return CompanyResponse(**response_dict)

    except NotFoundError:
        raise
    except Exception as e:
        logger.error(
            "get_company_error",
            company_uuid=str(company_uuid),
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve company"
        )


@router.post(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a company",
)
async def create_company(
    name: str = Form(..., description="Company name"),
    commune_name: str = Form(..., description="Commune name"),
    product_name: str = Form(..., description="Product name"),
    address: str = Form(..., description="Company address"),
    phone: str = Form(..., description="Phone number"),
    email: str = Form(..., description="Company email"),
    description_es: str = Form(..., description="Description in Spanish"),
    description_en: Optional[str] = Form(None, description="Description in English (auto-translated if empty)"),
    image: Optional[UploadFile] = File(None, description="Company logo"),
    lang: str = Form("es", description="Primary language"),
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    """
    Create a new company for the current user.
    
    Requires verified email.
    User can only have one company.
    """
    user_uuid = UUID(current_user["sub"])
    
    # Validate inputs
    try:
        validated_name = validate_name(name)
        validated_address = validate_address(address)
        validated_phone = validate_phone(phone)
        validated_email = validate_email(email)
        validated_desc_es = validate_description(description_es)
        validated_lang = validate_language(lang)
    except ValidationError as e:
        raise ValidationErrorResponse(message=e.message, field=e.field)
    
    # Auto-translate description if not provided
    if description_en:
        try:
            validated_desc_en = validate_description(description_en)
        except ValidationError as e:
            raise ValidationErrorResponse(message=e.message, field="description_en")
    else:
        try:
            validated_desc_en = await translate_field(validated_desc_es, "es", "en")
        except Exception as e:
            logger.warning(
                "translation_failed",
                error=str(e),
                field="description_en"
            )
            validated_desc_en = validated_desc_es  # Fallback to Spanish
    
    try:
        # Check if user already has a company
        existing = await DB.get_company_by_user_uuid(db, user_uuid)
        if existing:
            raise ConflictError(
                message="User already has a company",
                resource="company"
            )
        
        # Resolve commune and product UUIDs
        commune_uuid = await resolve_commune_uuid(db, commune_name)
        product_uuid = await resolve_product_uuid(db, product_name, validated_lang)
        
        # Handle image upload
        image_url = None
        image_extension = None
        if image and image.filename:
            try:
                upload_result = await image_service_client.upload_image(image)
                image_url = upload_result.get("image_id")
                image_extension = upload_result.get("extension")
            except Exception as img_error:
                logger.error(
                    "image_upload_failed",
                    error=str(img_error),
                    user_uuid=str(user_uuid)
                )
                raise ServiceUnavailableError(
                    service="image",
                    message="Failed to upload company image"
                )
        
        # Generate company UUID
        company_uuid = uuid.uuid4()
        
        # Create company (note: transactions.py requires company_uuid and email)
        company = await DB.create_company(
            conn=db,
            company_uuid=company_uuid,
            user_uuid=user_uuid,
            product_uuid=product_uuid,
            commune_uuid=commune_uuid,
            name=validated_name,
            description_es=validated_desc_es,
            description_en=validated_desc_en,
            address=validated_address,
            phone=validated_phone,
            email=validated_email,
            image_url=image_url,
            image_extension=image_extension,
        )
        
        logger.info(
            "company_created",
            company_uuid=str(company.uuid),
            user_uuid=str(user_uuid)
        )
        
        response_dict = company.model_dump()
        response_dict["image_url"] = image_service_client.build_image_url(
            company.image_url,
            company.image_extension,
        )
        return CompanyResponse(**response_dict)
        
    except (ConflictError, ValidationErrorResponse, ServiceUnavailableError):
        raise
    except Exception as e:
        logger.error(
            "create_company_error",
            user_uuid=str(user_uuid),
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create company"
        )


@router.patch(
    "/user/my-company",
    response_model=CompanyResponse,
    summary="Update my company",
)
async def update_my_company(
    name: Optional[str] = Form(None, description="Company name"),
    commune_name: Optional[str] = Form(None, description="Commune name"),
    product_name: Optional[str] = Form(None, description="Product name"),
    address: Optional[str] = Form(None, description="Company address"),
    phone: Optional[str] = Form(None, description="Phone number"),
    email: Optional[str] = Form(None, description="Company email"),
    description_es: Optional[str] = Form(None, description="Description in Spanish"),
    description_en: Optional[str] = Form(None, description="Description in English"),
    image: Optional[UploadFile] = File(None, description="Company logo"),
    lang: Optional[str] = Form(None, description="Primary language"),
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    """
    Update the current user's company.
    
    Only provided fields are updated.
    """
    user_uuid = UUID(current_user["sub"])
    
    try:
        # Get existing company
        company = await DB.get_company_by_user_uuid(db, user_uuid)
        if not company:
            raise NotFoundError(resource="company", identifier=f"user:{user_uuid}")
        
        # Build update dict with validated values
        update_data = {}
        
        if name is not None:
            try:
                update_data["name"] = validate_name(name)
            except ValidationError as e:
                raise ValidationErrorResponse(message=e.message, field="name")
        
        if address is not None:
            try:
                update_data["address"] = validate_address(address)
            except ValidationError as e:
                raise ValidationErrorResponse(message=e.message, field="address")
        
        if phone is not None:
            try:
                update_data["phone"] = validate_phone(phone)
            except ValidationError as e:
                raise ValidationErrorResponse(message=e.message, field="phone")
        
        if email is not None:
            try:
                update_data["email"] = validate_email(email)
            except ValidationError as e:
                raise ValidationErrorResponse(message=e.message, field="email")
        
        if description_es is not None:
            try:
                update_data["description_es"] = validate_description(description_es)
            except ValidationError as e:
                raise ValidationErrorResponse(message=e.message, field="description_es")
        
        if description_en is not None:
            try:
                update_data["description_en"] = validate_description(description_en)
            except ValidationError as e:
                raise ValidationErrorResponse(message=e.message, field="description_en")
        
        # Note: lang parameter removed from update_company_by_uuid signature
        
        # Resolve commune UUID if provided
        if commune_name is not None:
            update_data["commune_uuid"] = await resolve_commune_uuid(db, commune_name)
        
        # Resolve product UUID if provided
        if product_name is not None:
            # Use company's existing lang if not being updated
            current_lang = lang if lang else "es"  # Default to 'es' since lang is removed
            update_data["product_uuid"] = await resolve_product_uuid(
                db, product_name, current_lang
            )
        
        # Handle image upload if provided
        if image and image.filename:
            try:
                # Delete old image if exists
                if company.image_url:
                    await image_service_client.delete_image(
                        company.image_url,
                        company.image_extension
                    )
                
                upload_result = await image_service_client.upload_image(image)
                update_data["image_url"] = upload_result.get("image_id")
                update_data["image_extension"] = upload_result.get("extension")
            except Exception as img_error:
                logger.error(
                    "image_update_failed",
                    error=str(img_error),
                    company_uuid=str(company.uuid)
                )
                raise ServiceUnavailableError(
                    service="image",
                    message="Failed to update company image"
                )
        
        if not update_data:
            # No updates provided, return current company
            response_dict = company.model_dump()
            response_dict["image_url"] = image_service_client.build_image_url(
                company.image_url,
                company.image_extension,
            )
            return CompanyResponse(**response_dict)
        
        # Update company (use update_company_by_uuid from transactions.py)
        updated_company = await DB.update_company_by_uuid(
            conn=db,
            company_uuid=company.uuid,
            user_uuid=user_uuid,
            **update_data
        )
        
        logger.info(
            "company_updated",
            company_uuid=str(company.uuid),
            user_uuid=str(user_uuid),
            updated_fields=list(update_data.keys())
        )
        
        response_dict = updated_company.model_dump()
        response_dict["image_url"] = image_service_client.build_image_url(
            updated_company.image_url,
            updated_company.image_extension,
        )
        return CompanyResponse(**response_dict)
        
    except (NotFoundError, ValidationErrorResponse, ServiceUnavailableError):
        raise
    except Exception as e:
        logger.error(
            "update_company_error",
            user_uuid=str(user_uuid),
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update company"
        )


@router.delete(
    "/user/my-company",
    response_model=CompanyDeleteResponse,
    summary="Delete my company",
)
async def delete_my_company(
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    """
    Delete the current user's company.
    
    Also deletes associated image.
    """
    user_uuid = UUID(current_user["sub"])
    
    try:
        # Get company to delete
        company = await DB.get_company_by_user_uuid(db, user_uuid)
        if not company:
            raise NotFoundError(resource="company", identifier=f"user:{user_uuid}")
        
        # Delete company (use delete_company_by_uuid from transactions.py)
        result = await DB.delete_company_by_uuid(
            conn=db,
            company_uuid=company.uuid,
            user_uuid=user_uuid
        )
        
        logger.info(
            "company_deleted",
            company_uuid=str(company.uuid),
            user_uuid=str(user_uuid)
        )
        
        return CompanyDeleteResponse(
            message="Company successfully deleted",
            company_uuid=result.uuid
        )
        
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(
            "delete_company_error",
            user_uuid=str(user_uuid),
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete company"
        )


# Admin endpoints

@router.get(
    "/admin/all-companies/use-postman-or-similar-to-bypass-csrf",
    response_model=List[CompanyResponse],
    summary="List all companies (Admin)",
)
async def admin_list_companies(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_admin),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    List all companies (Admin only).
    """
    try:
        # Use get_all_companies from transactions.py
        companies = await DB.get_all_companies(
            conn=db, limit=limit, offset=offset
        )
        
        result = []
        for company in companies:
            response_dict = company.model_dump()
            response_dict["image_url"] = image_service_client.build_image_url(
                company.image_url,
                company.image_extension,
            )
            result.append(CompanyResponse(**response_dict))
        
        logger.info(
            "admin_list_companies",
            admin_email=current_user["email"],
            companies_count=len(result)
        )
        
        return result
        
    except Exception as e:
        logger.error("admin_list_companies_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve companies"
        )


@router.delete(
    "/admin/companies/{company_uuid}/use-postman-or-similar-to-bypass-csrf",
    response_model=CompanyDeleteResponse,
    summary="Delete company (Admin)",
)
async def admin_delete_company(
    company_uuid: UUID,
    current_user: dict = Depends(require_admin),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    """
    Delete any company by UUID (Admin only).
    
    Also deletes associated image.
    """
    try:
        # Get company to delete
        company = await DB.get_company_by_uuid(db, company_uuid)
        if not company:
            raise NotFoundError(resource="company", identifier=str(company_uuid))
        
        # Delete company using admin_delete_company_by_uuid
        result = await DB.admin_delete_company_by_uuid(conn=db, company_uuid=company_uuid)
        
        logger.info(
            "admin_deleted_company",
            company_uuid=str(company_uuid),
            company_name=company.name,
            admin_email=current_user["email"]
        )
        
        return CompanyDeleteResponse(
            message="Company successfully deleted by admin",
            company_uuid=result.uuid
        )
        
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(
            "admin_delete_company_error",
            company_uuid=str(company_uuid),
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete company"
        )