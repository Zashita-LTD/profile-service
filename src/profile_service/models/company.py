"""Company node model."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CompanyBase(BaseModel):
    """Base company attributes."""

    name: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None  # "1-10", "11-50", "51-200", "201-500", "500+"
    location: Optional[str] = None
    founded_year: Optional[int] = None


class CompanyCreate(CompanyBase):
    """Schema for creating a company."""

    pass


class CompanyUpdate(BaseModel):
    """Schema for updating a company."""

    name: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    location: Optional[str] = None
    founded_year: Optional[int] = None


class Company(CompanyBase):
    """Complete company model with metadata."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class CompanyWithEmployees(Company):
    """Company with employee list."""

    employees_count: int = 0
    employees: list[dict] = Field(default_factory=list)  # {person, role, since}
