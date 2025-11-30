"""
Companies Router - Complete Implementation
Handles all company CRUD operations with image management
CORRECTED: Uses company_uuid for image storage
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request, Query, Form
from typing import List, Optional
from uuid import UUID
import asyncpg
import uuid

from app.config import settings
from app.database.connection import get_db
from app.database.transactions import DB
from app.auth.dependencies import require_verified_email, require_admin, verify_csrf, get_current_user
from app.schemas.companies import CompanyResponse, CompanySearchResponse
from backend.app.services.translation_service import translate_field
from app.services.file_handler import FileHandler
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/companies", tags=["companies"])


# ============================================================================
# PUBLIC ENDPOINTS
# ============================================================================

@router.get("/search", response_model=List[CompanySearchResponse])
async def search_companies(
    q: Optional[str] = Query(None, description="Search query"),
    commune: Optional[str] = Query(None, description="Filter by commune name"),
    product: Optional[str] = Query(None, description="Filter by product name"),
    lang: str = Query("es", description="Language (es/en)"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Public search endpoint
    - Supports keyword search
    - Filter by commune and product
    - Pagination support
    - Returns localized results based on lang parameter
    """
    try:
        results = await DB.search_companies(
            conn=db,
            query=q or "",
            lang=lang,
            commune=commune,
            product=product,
            limit=limit,
            offset=offset
        )
        
        logger.info(
            "company_search_completed",
            query=q,
            commune=commune,
            product=product,
            results_count=len(results),
            lang=lang
        )
        
        return [CompanySearchResponse(**result) for result in results]
        
    except Exception as e:
        logger.error("search_companies_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )


# ============================================================================
# AUTHENTICATED USER ENDPOINTS
# ============================================================================

@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    request: Request,
    name: str = Form(..., min_length=1, max_length=100),
    product_uuid: UUID = Form(...),
    commune_uuid: UUID = Form(...),
    description_es: Optional[str] = Form(None, max_length=500),
    description_en: Optional[str] = Form(None, max_length=500),
    address: str = Form(..., min_length=1, max_length=200),
    phone: str = Form(..., min_length=1, max_length=20),
    email: str = Form(..., min_length=1, max_length=100),
    lang: str = Form(..., regex="^(es|en)$"),
    image: UploadFile = File(...),
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf)
):
    """
    Create a new company
    
    Requirements:
    - User must be authenticated and email verified
    - Each user can only have ONE company
    - Image required (JPEG/PNG, max 10MB)
    - NSFW content detection enabled
    
    Flow:
    1. Translate description if only one language provided
    2. Generate company UUID
    3. Upload image using company UUID as filename
    4. Create DB record with that UUID
    5. On DB failure: cleanup uploaded image
    """
    try:
        user_uuid = UUID(current_user["sub"])
        
        # Step 1: Translate description if needed
        if lang == "es":
            if not description_es:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="description_es required when lang=es"
                )
            description_es, description_en = await translate_field(
                "company_description", 
                description_es, 
                None
            )
        else:  # lang == "en"
            if not description_en:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="description_en required when lang=en"
                )
            description_es, description_en = await translate_field(
                "company_description", 
                None, 
                description_en
            )
        
        logger.info(
            "creating_company",
            user_uuid=str(user_uuid),
            name=name,
            lang=lang
        )
        
        # Step 2: Generate company UUID BEFORE uploading image
        company_uuid_str = str(uuid.uuid4())
        
        # Step 3: Upload image using company_id (validates, checks NSFW, uploads)
        image_id, image_ext = await FileHandler.save_image(
            file=image, 
            company_id=company_uuid_str
        )
        
        try:
           
            company = await DB.create_company(
                conn=db,
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
                company_uuid=company_uuid_str
            )
            
            # Build response with full image URL
            response_data = dict(company)
            response_data["image_url"] = FileHandler.get_image_url(
                image_id,  # company_uuid
                str(request.base_url).rstrip('/')
            )
            
            logger.info(
                "company_created_successfully",
                company_uuid=str(company["uuid"]),
                user_uuid=str(user_uuid),
                image_id=image_id
            )
            
            return CompanyResponse(**response_data)
            
        except ValueError as ve:
            # Business rule violation (e.g., user already has company)
            await FileHandler.delete_image(company_uuid_str)
            logger.warning(
                "company_creation_failed_business_rule",
                user_uuid=str(user_uuid),
                error=str(ve)
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(ve)
            )
            
        except Exception as db_error:
            # Database error - cleanup uploaded image
            await FileHandler.delete_image(company_uuid_str)
            logger.error(
                "company_creation_failed_db_error",
                user_uuid=str(user_uuid),
                error=str(db_error),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error during company creation"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_company_unexpected_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create company"
        )


@router.put("/{company_uuid}", response_model=CompanyResponse)
async def update_company(
    company_uuid: UUID,
    request: Request,
    name: Optional[str] = Form(None, min_length=1, max_length=100),
    product_uuid: Optional[UUID] = Form(None),
    commune_uuid: Optional[UUID] = Form(None),
    description_es: Optional[str] = Form(None, max_length=500),
    description_en: Optional[str] = Form(None, max_length=500),
    address: Optional[str] = Form(None, min_length=1, max_length=200),
    phone: Optional[str] = Form(None, min_length=1, max_length=20),
    email: Optional[str] = Form(None, min_length=1, max_length=100),
    lang: Optional[str] = Form(None, regex="^(es|en)$"),
    image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf)
):
    """
    Update existing company
    
    Requirements:
    - User must own the company
    - All fields optional (partial update)
    - Image update is optional
    
    Flow:
    1. Translate if description provided
    2. Upload new image if provided (uses company_uuid, automatically overwrites old)
    3. Update database
    """
    try:
        user_uuid = UUID(current_user["sub"])
        
        # Step 1: Translate description if provided
        final_description_es, final_description_en = description_es, description_en
        
        if (description_es or description_en) and lang:
            if lang == "es" and description_es:
                final_description_es, final_description_en = await translate_field(
                    "company_description", 
                    description_es, 
                    None
                )
            elif lang == "en" and description_en:
                final_description_es, final_description_en = await translate_field(
                    "company_description", 
                    None, 
                    description_en
                )
        
        logger.info(
            "updating_company",
            company_uuid=str(company_uuid),
            user_uuid=str(user_uuid),
            has_new_image=image is not None
        )
        
        # Step 2: Handle image update
        new_image_id = None
        new_image_ext = None
        
        if image:
            # Get company to verify ownership
            old_company = await DB.get_company_by_uuid(
                conn=db, 
                company_uuid=company_uuid
            )
            
            if not old_company:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Company not found"
                )
            
            # Verify ownership
            if old_company.get("user_uuid") != user_uuid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only update your own company"
                )
            
            # Upload new image using company_uuid
            # Note: This automatically overwrites the old image since we use company_uuid
            new_image_id, new_image_ext = await FileHandler.save_image(
                file=image, 
                company_id=str(company_uuid)
            )
        
        try:
            # Step 3: Update company in database
            company = await DB.update_company_by_uuid(
                conn=db,
                company_uuid=company_uuid,
                user_uuid=user_uuid,
                name=name,
                description_es=final_description_es,
                description_en=final_description_en,
                address=address,
                phone=phone,
                email=email,
                image_url=new_image_id,
                image_extension=new_image_ext,
                product_uuid=product_uuid,
                commune_uuid=commune_uuid
            )
            
            # Build response with full URL
            response_data = dict(company)
            response_data["image_url"] = FileHandler.get_image_url(
                company["image_url"],  # company_uuid
                str(request.base_url).rstrip('/')
            )
            
            logger.info(
                "company_updated_successfully",
                company_uuid=str(company_uuid),
                user_uuid=str(user_uuid)
            )
            
            return CompanyResponse(**response_data)
            
        except PermissionError as pe:
            # User doesn't own this company
            if new_image_id:
                await FileHandler.delete_image(str(company_uuid))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(pe)
            )
            
        except ValueError as ve:
            # Business rule violation
            if new_image_id:
                await FileHandler.delete_image(str(company_uuid))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ve)
            )
            
        except Exception as db_error:
            # Database error - cleanup new image if uploaded
            if new_image_id:
                await FileHandler.delete_image(str(company_uuid))
            logger.error(
                "company_update_failed",
                company_uuid=str(company_uuid),
                error=str(db_error),
                exc_info=True
            )
            raise
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_company_unexpected_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update company"
        )


@router.delete("/{company_uuid}", status_code=status.HTTP_200_OK)
async def delete_company(
    company_uuid: UUID,
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf)
):
    """
    Delete own company
    
    Flow:
    1. Verify ownership
    2. Delete from database (soft delete)
    3. Delete image from storage service using company_uuid
    """
    try:
        user_uuid = UUID(current_user["sub"])
        
        logger.info(
            "deleting_company",
            company_uuid=str(company_uuid),
            user_uuid=str(user_uuid)
        )
        
        # Get company to verify ownership
        company = await DB.get_company_by_uuid(
            conn=db, 
            company_uuid=company_uuid
        )
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found"
            )
        
        if company.get("user_uuid") != user_uuid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own company"
            )
        
        image_id = company.get("image_url")  # This is company_uuid
        
        # Delete from database
        result = await DB.delete_company_by_uuid(
            conn=db, 
            company_uuid=company_uuid, 
            user_uuid=user_uuid
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete company from database"
            )
        
        # Delete image from storage service
        if image_id:
            deleted = await FileHandler.delete_image(image_id)  # company_uuid
            logger.info(
                "company_image_deleted",
                company_uuid=str(company_uuid),
                image_id=image_id,
                deleted=deleted
            )
        
        logger.info(
            "company_deleted_successfully",
            company_uuid=str(company_uuid),
            user_uuid=str(user_uuid)
        )
        
        return {
            "message": "Company successfully deleted",
            "uuid": str(company_uuid)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_company_unexpected_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete company"
        )


@router.get("/user/my-company", response_model=CompanyResponse)
async def get_my_company(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get current user's company
    Returns 404 if user has no company
    """
    try:
        user_uuid = UUID(current_user["sub"])
        
        companies = await DB.get_companies_by_user_uuid(
            conn=db, 
            user_uuid=user_uuid
        )
        
        if not companies:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You don't have a company yet"
            )
        
        company = companies[0]
        
        # Build response with full image URL
        response_data = dict(company)
        response_data["image_url"] = FileHandler.get_image_url(
            company["image_url"],  # company_uuid
            str(request.base_url).rstrip('/')
        )
        
        logger.info(
            "user_company_retrieved",
            user_uuid=str(user_uuid),
            company_uuid=str(company["uuid"])
        )
        
        return CompanyResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_my_company_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve your company"
        )


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@router.get(
    "/admin/all-companies/use-postman-or-similar-to-send-csrf",
    response_model=List[CompanyResponse]
)
async def admin_list_all_companies(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_admin),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Admin: List all companies with pagination
    """
    try:
        companies = await DB.get_all_companies(
            conn=db, 
            limit=limit, 
            offset=offset
        )
        
        base_url = str(request.base_url).rstrip('/')
        
        response_companies = []
        for company in companies:
            company_data = dict(company)
            company_data["image_url"] = FileHandler.get_image_url(
                company["image_url"],  # company_uuid
                base_url
            )
            response_companies.append(CompanyResponse(**company_data))
        
        logger.info(
            "admin_listed_companies",
            admin_email=current_user["email"],
            count=len(response_companies),
            limit=limit,
            offset=offset
        )
        
        return response_companies
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("admin_list_companies_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve companies"
        )


@router.delete(
    "/admin/{company_uuid}/use-postman-or-similar-to-send-csrf",
    status_code=status.HTTP_200_OK
)
async def admin_delete_company(
    company_uuid: UUID,
    current_user: dict = Depends(require_admin),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf)
):
    """
    Admin: Delete any company
    
    Flow:
    1. Delete from database (admin permission check inside DB layer)
    2. Delete image from storage service using company_uuid
    """
    try:
        logger.info(
            "admin_deleting_company",
            company_uuid=str(company_uuid),
            admin_email=current_user["email"]
        )
        
        # Delete from database (includes permission check)
        result = await DB.admin_delete_company_by_uuid(
            conn=db,
            company_uuid=company_uuid,
            admin_email=current_user["email"]
        )
        
        image_id = result.get("image_url")  # This is company_uuid
        
        # Delete image from storage service
        if image_id:
            deleted = await FileHandler.delete_image(image_id)  # company_uuid
            logger.info(
                "admin_deleted_company_image",
                company_uuid=str(company_uuid),
                image_id=image_id,
                deleted=deleted,
                admin_email=current_user["email"]
            )
        
        logger.info(
            "admin_deleted_company_successfully",
            company_uuid=str(company_uuid),
            company_name=result["name"],
            admin_email=current_user["email"]
        )
        
        return {
            "message": "Company successfully deleted by admin",
            "uuid": result["uuid"],
            "name": result["name"]
        }
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "admin_delete_company_unexpected_error",
            company_uuid=str(company_uuid),
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete company"
        )