from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request, Query, Form
from typing import List, Optional
from uuid import UUID
import asyncpg
from app.config import settings
from app.database.connection import get_db
from app.database.transactions import DB
from app.auth.dependencies import require_verified_email, require_admin, verify_csrf, get_current_user
from app.schemas.companies import CompanyResponse, CompanySearchResponse
from app.utils.translator import translate_field
from app.utils.file_handler import FileHandler
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/companies", tags=["companies"])

@router.get("/search", response_model=List[CompanySearchResponse])
async def search_companies(


@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    request: Request,
    name: str = Form(...),
    product_uuid: UUID = Form(...),
    commune_uuid: UUID = Form(...),
    description_es: Optional[str] = Form(None),
    description_en: Optional[str] = Form(None),
    address: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    lang: str = Form(...),
    image: UploadFile = File(...),
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf)
):
    try:
        user_uuid = UUID(current_user["sub"])
        
        # Translate if needed
        if lang == "es":
            description_es, description_en = await translate_field("company_description", description_es, None)
        else:
            description_es, description_en = await translate_field("company_description", None, description_en)
        
        # Upload image (validates, checks NSFW, uploads to service)
        image_id = await FileHandler.save_image(file=image, user_uuid=str(user_uuid))
        
        try:
            # Create company with image_id instead of path
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
                image_url=image_id  # Store image_id instead of path
            )
            
            # Build response with full image URL
            response_data = dict(company)
            response_data["image_url"] = FileHandler.get_image_url(
                image_id, 
                str(request.base_url).rstrip('/')
            )
            
            logger.info("company_created", company_uuid=str(company["uuid"]))
            return CompanyResponse(**response_data)
            
        except Exception as db_error:
            # If database fails, clean up uploaded image
            await FileHandler.delete_image(image_id)
            raise db_error
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_company_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create company")

@router.put("/{company_uuid}", response_model=CompanyResponse)
async def update_company(
    company_uuid: UUID,
    request: Request,
    name: Optional[str] = Form(None),
    product_uuid: Optional[UUID] = Form(None),
    commune_uuid: Optional[UUID] = Form(None),
    description_es: Optional[str] = Form(None),
    description_en: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    lang: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf)
):
    try:
        user_uuid = UUID(current_user["sub"])
        
        # Translate if needed
        final_description_es, final_description_en = description_es, description_en
        if (description_es or description_en) and lang:
            if lang == "es":
                final_description_es, final_description_en = await translate_field(
                    "company_description", description_es, None
                )
            else:
                final_description_es, final_description_en = await translate_field(
                    "company_description", None, description_en
                )
        
        # Handle image update
        new_image_id = None
        old_image_id = None
        
        if image:
            # Get old image ID
            old_company = await DB.get_company_by_uuid(conn=db, company_uuid=company_uuid)
            if old_company:
                old_image_id = old_company.get("image_url")
            
            # Upload new image
            new_image_id = await FileHandler.save_image(file=image, user_uuid=str(user_uuid))
        
        # Update company
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
            product_uuid=product_uuid,
            commune_uuid=commune_uuid
        )
        
        # Delete old image if we uploaded a new one
        if new_image_id and old_image_id and old_image_id != new_image_id:
            await FileHandler.delete_image(old_image_id)
        
        # Build response with full URL
        response_data = dict(company)
        response_data["image_url"] = FileHandler.get_image_url(
            company["image_url"], 
            str(request.base_url).rstrip('/')
        )
        
        logger.info("company_updated", company_uuid=str(company_uuid))
        return CompanyResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_company_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update company")

@router.delete("/{company_uuid}", status_code=status.HTTP_200_OK)
async def delete_company(
    company_uuid: UUID,
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf)
):
    try:
        user_uuid = UUID(current_user["sub"])
        
        # Get company to get image_id
        company = await DB.get_company_by_uuid(conn=db, company_uuid=company_uuid)
        
        if company and company.get("user_uuid") == user_uuid:
            image_id = company.get("image_url")
            
            # Delete from database
            result = await DB.delete_company_by_uuid(
                conn=db, 
                company_uuid=company_uuid, 
                user_uuid=user_uuid
            )
            
            # Delete image from storage service
            if result and image_id:
                await FileHandler.delete_image(image_id)
            
            return {"message": "Company successfully deleted", "uuid": str(company_uuid)}
        
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_company_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete company")

@router.get("/user/my-company", response_model=CompanyResponse)
async def get_my_company(request: Request, current_user: dict = Depends(get_current_user), db: asyncpg.Connection = Depends(get_db)):
    try:
        user_uuid = UUID(current_user["sub"])
        companies = await DB.get_companies_by_user_uuid(conn=db, user_uuid=user_uuid)
        if not companies:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You don't have a company yet")
        company = companies[0]
        response_data = dict(company)
        response_data["image_url"] = FileHandler.get_image_url(company["image_url"], str(request.base_url).rstrip('/'))
        return CompanyResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_my_company_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve your company")

@router.get("/admin/all-companies/use-postman-or-similar-to-send-csrf", response_model=List[CompanyResponse])
async def admin_list_all_companies(request: Request, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), current_user: dict = Depends(require_admin), db: asyncpg.Connection = Depends(get_db)):
    try:
        companies = await DB.get_all_companies(conn=db, limit=limit, offset=offset)
        base_url = str(request.base_url).rstrip('/')
        response_companies = []
        for company in companies:
            company_data = dict(company)
            company_data["image_url"] = FileHandler.get_image_url(company["image_url"], base_url)
            response_companies.append(CompanyResponse(**company_data))
        return response_companies
    except HTTPException:
        raise
    except Exception as e:
        logger.error("admin_list_companies_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve companies")

@router.delete("/admin/{company_uuid}/use-postman-or-similar-to-send-csrf", status_code=status.HTTP_200_OK)
async def admin_delete_company(company_uuid: UUID, current_user: dict = Depends(require_admin), db: asyncpg.Connection = Depends(get_db), _: None = Depends(verify_csrf)):
    try:
        result = await DB.admin_delete_company_by_uuid(conn=db, company_uuid=company_uuid, admin_email=current_user["email"])
        image_path = result.get("image_url")
        if image_path:
            FileHandler.delete_image(image_path)
        return {"message": "Company successfully deleted by admin", "uuid": result["uuid"], "name": result["name"]}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error("admin_delete_company_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete company")
