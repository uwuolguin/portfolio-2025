from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Form, Request
from typing import List, Optional,Union
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

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/companies", tags=["companies"])


async def resolve_commune_uuid(conn: asyncpg.Connection, commune_name: str) -> UUID:
    """Convert commune name to UUID"""
    result = await conn.fetchrow(
        "SELECT uuid FROM proveo.communes WHERE name = $1",
        commune_name
    )
    if not result:
        raise ValueError(f"Commune '{commune_name}' not found")
    return result['uuid']

async def resolve_product_uuid(conn: asyncpg.Connection, product_name: str, lang: str) -> UUID:
    """Convert product name (in current language) to UUID"""
    if lang == 'es':
        result = await conn.fetchrow(
            "SELECT uuid FROM proveo.products WHERE name_es = $1",
            product_name
        )
    else:
        result = await conn.fetchrow(
            "SELECT uuid FROM proveo.products WHERE name_en = $1",
            product_name
        )
    
    if not result:
        raise ValueError(f"Product '{product_name}' not found")
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
    try:
        return await DB.search_companies(
            conn=db,
            query=q or "",
            lang=lang,
            commune=commune,
            product=product,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error("search_companies_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed",
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
    user_uuid = UUID(current_user["sub"])

    try:
        company = await DB.get_company_by_user_uuid(db, user_uuid)
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No company found for this user",
            )

        response_dict = company.model_dump()
        response_dict["image_url"] = image_service_client.build_image_url(
            company.image_url,
            company.image_extension,
        )
        return CompanyResponse(**response_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_my_company_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve company",
        )

@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    name: str = Form(...),
    product_name: str = Form(...),
    commune_name: str = Form(...),
    description_es: Optional[str] = Form(None),
    description_en: Optional[str] = Form(None),
    address: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    lang: str = Form(..., pattern="^(es|en)$"),
    image: UploadFile = File(...),
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    user_uuid = UUID(current_user["sub"])
    company_uuid = uuid.uuid4()

    try:
        if lang == "es":
            if not description_es:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="description_es required when lang=es",
                )
        else:
            if not description_en:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="description_en required when lang=en",
                )
            
        description_es, description_en = await translate_field(
            "company_description",
            description_es,
            description_en,
        )

        try:
            product_uuid = await resolve_product_uuid(db, product_name, lang)
            commune_uuid = await resolve_commune_uuid(db, commune_name)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        image_ext = image_service_client.get_extension_from_content_type(
            image.content_type,
        )

        upload_result = await image_service_client.upload_image_streaming(
            file_obj=image.file,
            company_id=str(company_uuid),
            content_type=image.content_type,
            extension=image_ext,
            user_id=str(user_uuid),
        )

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
            image_url=upload_result["image_id"],
            image_extension=upload_result["extension"],
        )

        company_with_relations = await DB.get_company_by_uuid(db, company_uuid)
        if not company_with_relations:
            raise RuntimeError("Failed to fetch created company")

        response_dict = company_with_relations.model_dump()
        response_dict["image_url"] = image_service_client.build_image_url(
            company_with_relations.image_url,
            company_with_relations.image_extension,
        )

        return CompanyResponse(**response_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_company_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create company",
        )

@router.put(
    "/{company_uuid}",
    response_model=CompanyResponse,
    summary="Update company",
)
async def update_company(
    company_uuid: UUID,
    name: Optional[str] = Form(None, min_length=1, max_length=100),
    description_es: Optional[str] = Form(None, max_length=500),
    description_en: Optional[str] = Form(None, max_length=500),
    address: Optional[str] = Form(None, max_length=200),
    phone: Optional[str] = Form(None, max_length=20),
    email: Optional[str] = Form(None),
    product_name: Optional[str] = Form(None),
    commune_name: Optional[str] = Form(None),
    lang: str = Form(pattern="^(es|en)$"),
    image: Optional[Union[UploadFile, str]] = File(None),
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    if not isinstance(image, UploadFile):
        image = None
    user_uuid = UUID(current_user["sub"])
    image_id = None
    image_ext = None

    try:
        product_uuid = None
        commune_uuid = None
        
        if product_name and lang:
            try:
                product_uuid = await resolve_product_uuid(db, product_name, lang)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
        
        if commune_name:
            try:
                commune_uuid = await resolve_commune_uuid(db, commune_name)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )

        if image:
            image_ext = image_service_client.get_extension_from_content_type(
                image.content_type,
            )
            upload_result = await image_service_client.upload_image_streaming(
                file_obj=image.file,
                company_id=str(company_uuid),
                content_type=image.content_type,
                extension=image_ext,
                user_id=str(user_uuid),
            )
            image_id = upload_result["image_id"]
            image_ext = upload_result["extension"]

        await DB.update_company_by_uuid(
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

        company_with_relations = await DB.get_company_by_uuid(db, company_uuid)
        if not company_with_relations:
            raise RuntimeError("Failed to fetch updated company")

        response_dict = company_with_relations.model_dump()
        response_dict["image_url"] = image_service_client.build_image_url(
            company_with_relations.image_url,
            company_with_relations.image_extension,
        )

        return CompanyResponse(**response_dict)

    except Exception as e:
        logger.error("update_company_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update company",
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
    try:
        companies = await DB.get_all_companies(db, limit, offset)

        result = []
        for company in companies:
            response_dict = company.model_dump()
            response_dict["image_url"] = image_service_client.build_image_url(
                company.image_url, 
                company.image_extension
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