"""Pydantic models for username/password authentication."""

from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class LoginResponse(BaseModel):
    api_key: str
    tenant_id: str
    username: str
    display_name: Optional[str] = None
    role: str = "user"


class LogoutResponse(BaseModel):
    success: bool = True


class MeResponse(BaseModel):
    tenant_id: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    role: str = "user"
    last_login: Optional[str] = None


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=200)
    display_name: Optional[str] = Field(None, max_length=200)
    role: str = Field("admin", pattern="^(admin|editor|viewer|user)$")


class CreateUserResponse(BaseModel):
    tenant_id: str
    username: str
    display_name: Optional[str] = None
    role: str = "admin"
    created: bool
