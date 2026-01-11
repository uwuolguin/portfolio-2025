"""
Commune Schemas

Pydantic models for commune/location-related API requests and responses.
"""

from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from datetime import datetime

from app.utils.validators import validate_name
from app.utils.exceptions import ValidationError


class CommuneRecord(BaseModel):
    """Internal commune record from database"""
    uuid: UUID
    name: str
    created_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "uuid": "a3c1d96b-0a3b-4d53-bb32-9e8e9cf5a71e",
                "name": "Santiago",
                "created_at": "2025-10-19T15:30:00Z",
            }
        }
    }


class CommuneCreate(BaseModel):
    """Schema for creating a new commune"""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Commune name (e.g., 'Santiago', 'Valparaíso')",
    )

    @field_validator("name", mode="before")
    @classmethod
    def validate_name_field(cls, v):
        if not isinstance(v, str):
            raise ValueError("Name must be a string")
        try:
            return validate_name(v, "name", min_length=1, max_length=100)
        except ValidationError as e:
            raise ValueError(e.message)

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Santiago"
            }
        }
    }


class CommuneUpdate(BaseModel):
    """Schema for updating a commune"""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="New commune name",
    )

    @field_validator("name", mode="before")
    @classmethod
    def validate_name_field(cls, v):
        if not isinstance(v, str):
            raise ValueError("Name must be a string")
        try:
            return validate_name(v, "name", min_length=1, max_length=100)
        except ValidationError as e:
            raise ValueError(e.message)

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Valparaíso"
            }
        }
    }


class CommuneResponse(BaseModel):
    """Public API response for commune data"""
    uuid: UUID = Field(..., description="Unique identifier for the commune")
    name: str = Field(..., description="Commune name")
    created_at: datetime = Field(..., description="Timestamp when commune was created")

    model_config = {
        "json_schema_extra": {
            "example": {
                "uuid": "a3c1d96b-0a3b-4d53-bb32-9e8e9cf5a71e",
                "name": "Santiago",
                "created_at": "2025-10-19T15:30:00Z",
            }
        }
    }