from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


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
                "verification_token":"sahashasjshhsahsa",
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

    model_config = {
        "json_schema_extra": {
            "example": {
                "uuid": "4d6f9c3b-ef34-42b8-b2a5-9d4b8e7a12aa",
                "name": "Andres Olguin",
                "email": "andres@example.com",
                "role": "user",
                "email_verified": False,
                "hashed_password": "zajbasbsas",
                "created_at": "2025-10-19T15:30:00Z",
            }
        }
    }

class UserSignup(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="User's full name")
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(
        ..., min_length=8, max_length=100, description="User's password (min 8 chars)"
    )

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
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=1, max_length=100, description="User's password")

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

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "andres@example.com",
                "email_verified": True,
            }
        }
    }


class LoginResponse(BaseModel):
    message: str = Field(..., description="Success message")
    csrf_token: str = Field(..., description="CSRF token for subsequent requests")
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

    model_config = {
        "json_schema_extra": {
            "example": {
                "uuid": "1a2b3c4d-1111-2222-3333-444455556666",
                "user_uuid": "4d6f9c3b-ef34-42b8-b2a5-9d4b8e7a12aa",
                "product_uuid": "9a8b7c6d-aaaa-bbbb-cccc-ddddeeeeffff",
                "commune_uuid": "a3c1d96b-0a3b-4d53-bb32-9e8e9cf5a71e",
                "name": "Deleted Company",
                "description_es": "Descripción",
                "description_en": "Description",
                "address": "Some address",
                "phone": "+56 9 1234 5678",
                "email": "company@example.com",
                "image_url": "https://example.com/image.png",
                "image_extension": "png",
                "created_at": "2025-10-01T10:00:00Z",
                "updated_at": "2025-10-19T15:30:00Z",
            }
        }
    }


class DeletedUserRecord(BaseModel):
    uuid: UUID
    name: str
    email: EmailStr
    hashed_password: str
    role: str
    email_verified: bool
    created_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "uuid": "4d6f9c3b-ef34-42b8-b2a5-9d4b8e7a12aa",
                "name": "Deleted User",
                "email": "deleted@example.com",
                "hashed_password": "$2b$12$...",
                "role": "user",
                "email_verified": False,
                "created_at": "2025-10-01T09:00:00Z",
            }
        }
    }


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
