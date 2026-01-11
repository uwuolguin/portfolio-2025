"""
User Schemas

Pydantic models for user-related API requests and responses.
Includes validation rules and examples.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.validators import (
    validate_name,
    validate_password
)


class UserRecord(BaseModel):
    uuid: UUID
    name: str
    email: EmailStr
    role: str
    email_verified: bool
    created_at: datetime
    verification_token: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "uuid": "4d6f9c3b-ef34-42b8-b2a5-9d4b8e7a12aa",
                "name": "Andres Olguin",
                "email": "andres@example.com",
                "role": "user",
                "email_verified": False,
                "created_at": "2025-10-19T15:30:00Z",
                "verification_token": "sahashasjshhsahsa",
            }
        }
    }


class UserRecordHash(BaseModel):
    uuid: UUID
    name: str
    email: EmailStr
    role: str
    email_verified: bool
    created_at: datetime
    hashed_password: str


class UserSignup(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name_field(cls, v):
        if not isinstance(v, str):
            raise ValueError("Name must be a string")
        return validate_name(v, "name", min_length=1, max_length=100)

    @field_validator("password", mode="before")
    @classmethod
    def validate_password_field(cls, v):
        if not isinstance(v, str):
            raise ValueError("Password must be a string")
        return validate_password(v, "password", min_length=8, max_length=100)

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Andres Olguin",
                "email": "andres@example.com",
                "password": "strongpassword123",
            }
        }
    }


class UserResponse(BaseModel):
    uuid: UUID
    name: str
    email: EmailStr
    role: str = "user"
    email_verified: bool = False
    created_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "uuid": "4d6f9c3b-ef34-42b8-b2a5-9d4b8e7a12aa",
                "name": "Andres Olguin",
                "email": "andres@example.com",
                "role": "user",
                "email_verified": True,
                "created_at": "2025-10-19T15:30:00Z",
            }
        }
    }


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=100)

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "andres@example.com",
                "password": "strongpassword123",
            }
        }
    }


class LoginUserInfo(BaseModel):
    email: EmailStr
    email_verified: bool


class LoginResponse(BaseModel):
    message: str
    csrf_token: str
    user: LoginUserInfo

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Login successful",
                "csrf_token": "abc123...",
                "user": {
                    "email": "andres@example.com",
                    "email_verified": True,
                },
            }
        }
    }


class AdminUserResponse(BaseModel):
    uuid: UUID
    name: str
    email: EmailStr
    role: str = "user"
    email_verified: bool = False
    created_at: datetime
    company_count: int = 0

    model_config = {
        "json_schema_extra": {
            "example": {
                "uuid": "7bde63f0-5d79-41b3-bd8f-5a23f44dbd94",
                "name": "Admin User",
                "email": "admin@example.com",
                "role": "admin",
                "email_verified": True,
                "created_at": "2025-10-19T12:00:00Z",
                "company_count": 2,
            }
        }
    }


class DeletedCompanyRecord(BaseModel):
    uuid: UUID
    user_uuid: UUID
    product_uuid: UUID
    commune_uuid: UUID
    name: str
    description_es: Optional[str]
    description_en: Optional[str]
    address: Optional[str]
    phone: Optional[str]
    email: Optional[EmailStr]
    image_url: Optional[str]
    image_extension: Optional[str]
    created_at: datetime
    updated_at: datetime


class DeletedUserRecord(BaseModel):
    uuid: UUID
    name: str
    email: EmailStr
    hashed_password: str
    role: str
    email_verified: bool
    created_at: datetime


class UserDeletionResponse(BaseModel):
    user_uuid: UUID
    email: EmailStr
    company_deleted: int = 0
    image_deleted: int = 0

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_uuid": "4d6f9c3b-ef34-42b8-b2a5-9d4b8e7a12aa",
                "email": "andres@example.com",
                "company_deleted": 1,
                "image_deleted": 1,
            }
        }
    }
