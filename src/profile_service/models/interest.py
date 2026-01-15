"""Interest node model."""

from pydantic import BaseModel, Field


class InterestBase(BaseModel):
    """Base interest attributes."""

    name: str = Field(..., min_length=1, max_length=100)
    category: str | None = None  # "Sports", "Technology", "Business", "Brands", etc.
    icon: str | None = None


class InterestCreate(InterestBase):
    """Schema for creating an interest."""

    pass


class Interest(InterestBase):
    """Complete interest model."""

    persons_count: int = 0

    class Config:
        from_attributes = True
