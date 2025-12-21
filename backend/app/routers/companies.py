from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request, Query, Form
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
    CompanyDeleteResponse
)
from app.services.translation_service import translate_field
from app.services.image_service_client import image_service_client

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/companies", tags=["companies"])

@router.get(
    "/search", 
    response_model=List[CompanySearchResponse],
    summary="Search companies"
)
async def search_companies(
    q: Optional[str] = Query(None, description="Search query"),
    commune: Optional[str] = Query(None, description="Filter by commune name"),
    product: Optional[str] = Query(None, description="Filter by product name"),
    lang: str = Query("es", regex="^(es|en)$", description="Response language"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results to skip"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Search companies with optional filters.
    
    - **q**: Search text (uses trigram similarity for 4+ characters)
    - **commune**: Filter by commune name (exact match, case-insensitive)
    - **product**: Filter by product name in either language
    - **lang**: Response language for descriptions/product names
    - **limit/offset**: Pagination
    """
    try:
        results = await DB.search_companies(
            conn=db,
            query=q or "",
            lang=lang,
            commune=commune,
            product=product,
            limit=limit,
            offset=offset,
        )
        return results
    except Exception as e:
        logger.error("search_companies_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )

@router.get(
    "/user/my-company", 
    response_model=CompanyResponse,
    summary="Get my company"
)
async def get_my_company(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get the authenticated user's company.
    Returns 404 if user hasn't published a company yet.
    """
    user_uuid = UUID(current_user["sub"])
    
    try:
        companies = await DB.get_companies_by_user_uuid(db, user_uuid)
        
        if not companies:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No company found for this user"
            )
        
        company = companies[0]  # Business rule: one company per user
        
        # Build full image URL
        response_dict = company.model_dump()
        response_dict["image_url"] = image_service_client.build_image_url(
            company.image_url, 
            company.image_extension, 
            str(request.base_url)
        )
        
        return CompanyResponse(**response_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_my_company_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve company"
        )


@router.post(
    "/", 
    response_model=CompanyResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create company"
)
async def create_company(
    request: Request,
    name: str = Form(..., min_length=1, max_length=100),
    product_uuid: UUID = Form(...),
    commune_uuid: UUID = Form(...),
    description_es: Optional[str] = Form(None, max_length=500),
    description_en: Optional[str] = Form(None, max_length=500),
    address: str = Form(..., max_length=200),
    phone: str = Form(..., max_length=20),
    email: str = Form(...),
    lang: str = Form(..., regex="^(es|en)$"),
    image: UploadFile = File(...),
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    """
    Create a new company (one per user).
    
    Requires:
    - Verified email
    - CSRF token
    - Image file (JPEG/PNG, max 10MB)
    - Either description_es or description_en (auto-translates if only one provided)
    """
    user_uuid = UUID(current_user["sub"])
    company_uuid = uuid.uuid4()

    try:
        if lang == "es":
            if not description_es:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="description_es required when lang=es"
                )
            description_es, description_en = await translate_field(
                "company_description", description_es, description_en
            )
        else:
            if not description_en:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="description_en required when lang=en"
                )
            description_es, description_en = await translate_field(
                "company_description", description_es, description_en
            )

        image_ext = image_service_client.get_extension_from_content_type(
            image.content_type
        )
        file_bytes = await image.read()
        
        upload_result = await image_service_client.upload_image(
            file_bytes=file_bytes,
            company_id=str(company_uuid),
            content_type=image.content_type,
            extension=image_ext,
            user_id=str(user_uuid),
        )

        image_id = upload_result["image_id"]
        image_ext = upload_result["extension"]

        company = await DB.create_company(
            conn=db,
            company_uuid=company_uuid,
            user_uuid=user_uuid,
            product_uuid=product_uuid,
            commune_uuid=commune_uuid,
            name=name,
            description_es=description_es,
            description_en=description_en,
            address=address,
            phone=phone,
            email=email,
            image_url=image_id,
            image_extension=image_ext,
        )

        # Fetch with relations for response
        company_with_relations = await DB.get_company_by_uuid(db, company_uuid)
        
        if not company_with_relations:
            raise RuntimeError("Failed to fetch created company")

        response_dict = company_with_relations.model_dump()
        response_dict["image_url"] = image_service_client.build_image_url(
            image_id, image_ext, str(request.base_url)
        )

        return CompanyResponse(**response_dict)

    except HTTPException:
        raise
    except ValueError as e:
        # Business rule violations (one company per user, invalid foreign keys)
        await image_service_client.delete_image(f"{company_uuid}{image_ext}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("create_company_failed", error=str(e), exc_info=True)
        await image_service_client.delete_image(f"{company_uuid}{image_ext}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create company"
        )


@router.put(
    "/{company_uuid}", 
    response_model=CompanyResponse,
    summary="Update company"
)
async def update_company(
    company_uuid: UUID,
    request: Request,
    name: Optional[str] = Form(None, min_length=1, max_length=100),
    description_es: Optional[str] = Form(None, max_length=500),
    description_en: Optional[str] = Form(None, max_length=500),
    address: Optional[str] = Form(None, max_length=200),
    phone: Optional[str] = Form(None, max_length=20),
    email: Optional[str] = Form(None),
    product_uuid: Optional[UUID] = Form(None),
    commune_uuid: Optional[UUID] = Form(None),
    lang: Optional[str] = Form(None, regex="^(es|en)$"),
    image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    """
    Update an existing company.
    Only the company owner can update their company.
    All fields are optional.
    """
    user_uuid = UUID(current_user["sub"])
    
    image_id = None
    image_ext = None

    try:
        # Handle image upload if provided
        if image:
            image_ext = image_service_client.get_extension_from_content_type(
                image.content_type
            )
            file_bytes = await image.read()

            upload_result = await image_service_client.upload_image(
                file_bytes=file_bytes,
                company_id=str(company_uuid),
                content_type=image.content_type,
                extension=image_ext,
                user_id=str(user_uuid),
            )

            image_id = upload_result["image_id"]
            image_ext = upload_result["extension"]

        # Update company
        company = await DB.update_company_by_uuid(
            conn=db,
            company_uuid=company_uuid,
            user_uuid=user_uuid,
            name=name,
            description_es=description_es,
            description_en=description_en,
            address=address,
            phone=phone,
            email=email,
            image_url=image_id,
            image_extension=image_ext,
            product_uuid=product_uuid,
            commune_uuid=commune_uuid,
        )

        # Fetch with relations
        company_with_relations = await DB.get_company_by_uuid(db, company_uuid)
        
        if not company_with_relations:
            raise RuntimeError("Failed to fetch updated company")

        response_dict = company_with_relations.model_dump()
        response_dict["image_url"] = image_service_client.build_image_url(
            company_with_relations.image_url,
            company_with_relations.image_extension,
            str(request.base_url)
        )

        return CompanyResponse(**response_dict)

    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("update_company_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update company"
        )


@router.delete(
    "/{company_uuid}",
    response_model=CompanyDeleteResponse,
    summary="Delete company"
)
async def delete_company(
    company_uuid: UUID,
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    """
    Delete the authenticated user's company.
    This is a soft delete - data is moved to companies_deleted table.
    Associated image is deleted from storage.
    """
    user_uuid = UUID(current_user["sub"])

    try:
        result = await DB.delete_company_by_uuid(db, company_uuid, user_uuid)
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("delete_company_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete company"
        )


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@router.get(
    "/admin/all-companies/use-postman-or-similar-to-bypass-csrf",
    response_model=List[CompanyResponse],
    summary="List all companies (Admin)"
)
async def admin_list_companies(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_admin),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Admin endpoint to list all companies with pagination.
    """
    try:
        companies = await DB.get_all_companies(db, limit, offset)
        base_url = str(request.base_url)

        result = []
        for company in companies:
            response_dict = company.model_dump()
            response_dict["image_url"] = image_service_client.build_image_url(
                company.image_url, 
                company.image_extension, 
                base_url
            )
            result.append(CompanyResponse(**response_dict))

        return result

    except Exception as e:
        logger.error("admin_list_companies_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list companies"
        )


@router.delete(
    "/admin/{company_uuid}/use-postman-or-similar-to-bypass-csrf",
    response_model=CompanyDeleteResponse,
    summary="Delete company (Admin)"
)
async def admin_delete_company(
    company_uuid: UUID,
    current_user: dict = Depends(require_admin),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    """
    Admin endpoint to delete any company.
    Bypasses ownership check.
    """
    try:
        result = await DB.admin_delete_company_by_uuid(db, company_uuid)
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "admin_delete_company_failed", 
            error=str(e), 
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete company"
        )