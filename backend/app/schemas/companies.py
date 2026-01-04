"""
Company Schemas

Pydantic models for company-related API requests and responses.
Includes comprehensive validation for all fields.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional

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


class CompanyRecord(BaseModel):
    """
    Internal representation of a company record from the database.
    Used by transaction layer for type-safe database operations.
    """
    uuid: UUID
    user_uuid: UUID
    product_uuid: UUID
    commune_uuid: UUID
    name: str
    description_es: str
    description_en: str
    address: str
    phone: str
    email: EmailStr
    image_url: str
    image_extension: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "uuid": "550e8400-e29b-41d4-a716-446655440001",
                "user_uuid": "4d6f9c3b-ef34-42b8-b2a5-9d4b8e7a12aa",
                "product_uuid": "2b7f0b26-38ab-4a9f-8db6-4b2f8f7a24c2",
                "commune_uuid": "a3c1d96b-0a3b-4d53-bb32-9e8e9cf5a71e",
                "name": "Tech Solutions SA",
                "description_es": "Soluciones tecnológicas innovadoras",
                "description_en": "Innovative technological solutions",
                "address": "Av. Providencia 1234, Santiago",
                "phone": "+56912345001",
                "email": "contact@techsolutions.cl",
                "image_url": "550e8400-e29b-41d4-a716-446655440001",
                "image_extension": ".jpg",
                "created_at": "2025-10-19T15:30:00Z",
                "updated_at": "2025-10-19T15:30:00Z"
            }
        }
    }


class CompanyWithRelations(CompanyRecord):
    """
    Company record with joined relation names.
    Used when fetching company data with related entities.
    """
    user_name: str
    user_email: EmailStr
    product_name_es: str
    product_name_en: str
    commune_name: str


class CompanyCreate(BaseModel):
    """
    Schema for creating a new company.
    Note: image and image_extension are handled separately in multipart/form-data
    """
    name: str = Field(..., min_length=1, max_length=100)
    description_es: Optional[str] = Field(None, min_length=1, max_length=500)
    description_en: Optional[str] = Field(None, min_length=1, max_length=500)
    address: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=1, max_length=20)
    email: EmailStr
    product_uuid: UUID
    commune_uuid: UUID
    lang: str = Field(..., pattern="^(es|en)$")

    @field_validator("name", mode="before")
    @classmethod
    def validate_name_field(cls, v):
        if not isinstance(v, str):
            raise ValueError("Name must be a string")
        try:
            return validate_name(v, "name", min_length=1, max_length=100)
        except ValidationError as e:
            raise ValueError(e.message)

    @field_validator("address", mode="before")
    @classmethod
    def validate_address_field(cls, v):
        if not isinstance(v, str):
            raise ValueError("Address must be a string")
        try:
            return validate_address(v, "address", max_length=200)
        except ValidationError as e:
            raise ValueError(e.message)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone_field(cls, v):
        if not isinstance(v, str):
            raise ValueError("Phone must be a string")
        try:
            return validate_phone(v, "phone", min_length=8, max_length=20)
        except ValidationError as e:
            raise ValueError(e.message)

    @field_validator("description_es", "description_en", mode="before")
    @classmethod
    def validate_description_fields(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("Description must be a string")
        try:
            return validate_description(v, "description", max_length=500, allow_empty=True)
        except ValidationError as e:
            raise ValueError(e.message)

    @field_validator("lang", mode="before")
    @classmethod
    def validate_lang_field(cls, v):
        if not isinstance(v, str):
            raise ValueError("Language must be a string")
        try:
            return validate_language(v, "lang")
        except ValidationError as e:
            raise ValueError(e.message)


class CompanyUpdate(BaseModel):
    """
    Schema for updating an existing company.
    All fields are optional.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description_es: Optional[str] = Field(None, min_length=1, max_length=500)
    description_en: Optional[str] = Field(None, min_length=1, max_length=500)
    address: Optional[str] = Field(None, min_length=1, max_length=200)
    phone: Optional[str] = Field(None, min_length=1, max_length=20)
    email: Optional[EmailStr] = None
    product_uuid: Optional[UUID] = None
    commune_uuid: Optional[UUID] = None
    lang: Optional[str] = Field(None, pattern="^(es|en)$")

    @field_validator("name", mode="before")
    @classmethod
    def validate_name_field(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("Name must be a string")
        try:
            return validate_name(v, "name", min_length=1, max_length=100)
        except ValidationError as e:
            raise ValueError(e.message)

    @field_validator("address", mode="before")
    @classmethod
    def validate_address_field(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("Address must be a string")
        try:
            return validate_address(v, "address", max_length=200)
        except ValidationError as e:
            raise ValueError(e.message)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone_field(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("Phone must be a string")
        try:
            return validate_phone(v, "phone", min_length=8, max_length=20)
        except ValidationError as e:
            raise ValueError(e.message)

    @field_validator("description_es", "description_en", mode="before")
    @classmethod
    def validate_description_fields(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("Description must be a string")
        try:
            return validate_description(v, "description", max_length=500, allow_empty=True)
        except ValidationError as e:
            raise ValueError(e.message)

    @field_validator("lang", mode="before")
    @classmethod
    def validate_lang_field(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("Language must be a string")
        try:
            return validate_language(v, "lang")
        except ValidationError as e:
            raise ValueError(e.message)


class CompanyResponse(BaseModel):
    """
    Public API response for company data.
    Includes full URL for image and all related entity names.
    """
    uuid: UUID
    user_uuid: UUID
    product_uuid: UUID
    commune_uuid: UUID
    name: str
    description_es: str
    description_en: str
    address: str
    phone: str
    email: EmailStr
    image_url: str
    image_extension: str
    created_at: datetime
    updated_at: datetime
    user_name: str
    user_email: EmailStr
    product_name_es: str
    product_name_en: str
    commune_name: str


class CompanySearchResponse(BaseModel):
    """
    Simplified response for search results.
    Language-specific and optimized for list views.
    """
    uuid: UUID
    name: str
    description: str
    address: str
    email: EmailStr
    phone: str
    img_url: str
    product_name: str
    commune_name: str


class CompanyDeleteResponse(BaseModel):
    """Response for successful company deletion"""
    uuid: UUID
    name: str
    message: str = "Company successfully deleted"