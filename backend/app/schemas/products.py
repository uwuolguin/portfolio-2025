"""
Product Schemas

Pydantic models for product-related API requests and responses.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional

from app.utils.validators import validate_name, normalize_whitespace, ValidationError


class ProductRecord(BaseModel):
    """
    Internal representation of a product record from the database.
    Used by transaction layer for type-safe database operations.
    """
    uuid: UUID
    name_es: str
    name_en: str
    created_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "uuid": "2b7f0b26-38ab-4a9f-8db6-4b2f8f7a24c2",
                "name_es": "Camiseta Roja",
                "name_en": "Red Shirt",
                "created_at": "2025-10-19T15:30:00Z",
            }
        }
    }


class ProductCreate(BaseModel):
    """Schema for creating a new product"""
    name_es: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Spanish product name (optional if name_en provided)",
    )
    name_en: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="English product name (optional if name_es provided)",
    )

    @field_validator("name_es", "name_en", mode="before")
    @classmethod
    def validate_name_fields(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("Name must be a string")
        try:
            return validate_name(v, "name", min_length=1, max_length=100)
        except ValidationError as e:
            raise ValueError(e.message)

    @model_validator(mode="after")
    def check_at_least_one_name(self):
        if not self.name_es and not self.name_en:
            raise ValueError(
                "At least one product name (name_es or name_en) must be provided"
            )
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "name_es": "Camiseta Roja",
                "name_en": "Red Shirt",
            }
        }
    }


class ProductUpdate(BaseModel):
    """Schema for updating a product"""
    name_es: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Spanish product name",
    )
    name_en: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="English product name",
    )

    @field_validator("name_es", "name_en", mode="before")
    @classmethod
    def validate_name_fields(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("Name must be a string")
        try:
            return validate_name(v, "name", min_length=1, max_length=100)
        except ValidationError as e:
            raise ValueError(e.message)

    @model_validator(mode="after")
    def check_at_least_one_name(self):
        if not self.name_es and not self.name_en:
            raise ValueError(
                "At least one product name (name_es or name_en) must be provided"
            )
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "name_es": "Camiseta Azul",
                "name_en": "Blue Shirt",
            }
        }
    }


class ProductResponse(BaseModel):
    """Public API response for product data"""
    uuid: UUID
    name_es: str
    name_en: str
    created_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "uuid": "2b7f0b26-38ab-4a9f-8db6-4b2f8f7a24c2",
                "name_es": "Camiseta Roja",
                "name_en": "Red Shirt",
                "created_at": "2025-10-19T15:30:00Z",
            }
        }
    }