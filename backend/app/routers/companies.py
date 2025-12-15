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
from app.schemas.companies import CompanyResponse, CompanySearchResponse
from app.services.translation_service import translate_field
from app.services.image_service_client import image_service_client, ImageServiceError

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/companies", tags=["companies"])


# ============================================================================
# PUBLIC
# ============================================================================

@router.get("/search", response_model=List[CompanySearchResponse])
async def search_companies(
    q: Optional[str] = Query(None),
    commune: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    lang: str = Query("es"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: asyncpg.Connection = Depends(get_db),
):
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
        return [CompanySearchResponse(**r) for r in results]
    except Exception as e:
        logger.error("search_companies_failed", error=str(e), exc_info=True)
        raise HTTPException(500, "Search failed")


# ============================================================================
# CREATE
# ============================================================================

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
    lang: str = Form(..., regex="^(es|en)$"),
    image: UploadFile = File(...),
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    user_uuid = UUID(current_user["sub"])

    if lang == "es":
        if not description_es:
            raise HTTPException(400, "description_es required")
        description_es, description_en = await translate_field(
            "company_description", description_es, None
        )
    else:
        if not description_en:
            raise HTTPException(400, "description_en required")
        description_es, description_en = await translate_field(
            "company_description", None, description_en
        )

    company_uuid = str(uuid.uuid4())

    try:
        image_ext = image_service_client.get_extension_from_content_type(image.content_type)
        file_bytes = await image.read()
        await image.seek(0)

        result = await image_service_client.upload_image(
            file_bytes=file_bytes,
            company_id=company_uuid,          # ✅ FIXED
            content_type=image.content_type,
            extension=image_ext,
            user_id=str(user_uuid),
        )

        image_id = result["image_id"]
        image_ext = result["extension"]

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
            company_uuid=company_uuid,
        )

        response = dict(company)
        response["image_url"] = image_service_client.build_image_url(
            image_id, image_ext, str(request.base_url)
        )

        return CompanyResponse(**response)

    except Exception:
        await image_service_client.delete_image(f"{company_uuid}{image_ext}")
        raise


# ============================================================================
# UPDATE
# ============================================================================

@router.put("/{company_uuid}", response_model=CompanyResponse)
async def update_company(
    company_uuid: UUID,
    request: Request,
    name: Optional[str] = Form(None),
    description_es: Optional[str] = Form(None),
    description_en: Optional[str] = Form(None),
    lang: Optional[str] = Form(None, regex="^(es|en)$"),
    image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    user_uuid = UUID(current_user["sub"])

    image_id = None
    image_ext = None

    if image:
        image_ext = image_service_client.get_extension_from_content_type(image.content_type)
        file_bytes = await image.read()
        await image.seek(0)

        result = await image_service_client.upload_image(
            file_bytes=file_bytes,
            company_id=str(company_uuid),      # ✅ FIXED
            content_type=image.content_type,
            extension=image_ext,
            user_id=str(user_uuid),
        )

        image_id = result["image_id"]
        image_ext = result["extension"]

    company = await DB.update_company_by_uuid(
        conn=db,
        company_uuid=company_uuid,
        user_uuid=user_uuid,
        name=name,
        description_es=description_es,
        description_en=description_en,
        image_url=image_id,
        image_extension=image_ext,
    )

    response = dict(company)
    response["image_url"] = image_service_client.build_image_url(
        company["image_url"], company["image_extension"], str(request.base_url)
    )

    return CompanyResponse(**response)


# ============================================================================
# DELETE (USER)
# ============================================================================

@router.delete("/{company_uuid}")
async def delete_company(
    company_uuid: UUID,
    current_user: dict = Depends(require_verified_email),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    user_uuid = UUID(current_user["sub"])

    company = await DB.get_company_by_uuid(db, company_uuid)
    if not company:
        raise HTTPException(404, "Company not found")

    if company["user_uuid"] != user_uuid:
        raise HTTPException(403, "Forbidden")

    await DB.delete_company_by_uuid(db, company_uuid, user_uuid)

    if company["image_url"] and company["image_extension"]:
        await image_service_client.delete_image(
            f"{company['image_url']}{company['image_extension']}"
        )

    return {"status": "deleted"}


# ============================================================================
# GET MY COMPANY
# ============================================================================

@router.get("/user/my-company", response_model=CompanyResponse)
async def get_my_company(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    user_uuid = UUID(current_user["sub"])

    companies = await DB.get_companies_by_user_uuid(db, user_uuid)
    if not companies:
        raise HTTPException(404, "No company")

    company = companies[0]
    response = dict(company)
    response["image_url"] = image_service_client.build_image_url(
        company["image_url"], company["image_extension"], str(request.base_url)
    )

    return CompanyResponse(**response)


# ============================================================================
# ADMIN
# ============================================================================

@router.get("/admin/all-companies/use-postman-or-similar-to-bypass-csrf",
            response_model=List[CompanyResponse])
async def admin_list_companies(
    request: Request,
    limit: int = Query(50),
    offset: int = Query(0),
    current_user: dict = Depends(require_admin),
    db: asyncpg.Connection = Depends(get_db),
):
    companies = await DB.get_all_companies(db, limit, offset)
    base = str(request.base_url)

    result = []
    for c in companies:
        r = dict(c)
        r["image_url"] = image_service_client.build_image_url(
            c["image_url"], c["image_extension"], base
        )
        result.append(CompanyResponse(**r))

    return result


@router.delete("/admin/{company_uuid}/use-postman-or-similar-to-bypass-csrf")
async def admin_delete_company(
    company_uuid: UUID,
    current_user: dict = Depends(require_admin),
    db: asyncpg.Connection = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    company = await DB.admin_delete_company_by_uuid(
        db, company_uuid, current_user["email"]
    )

    if company["image_url"] and company["image_extension"]:
        await image_service_client.delete_image(
            f"{company['image_url']}{company['image_extension']}"
        )

    return {"status": "deleted", "uuid": str(company_uuid)}
