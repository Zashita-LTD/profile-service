"""Skill node model."""

from pydantic import BaseModel, Field


class SkillBase(BaseModel):
    """Base skill attributes."""

    name: str = Field(..., min_length=1, max_length=100)
    category: str | None = None  # "Technical", "Soft", "Language", etc.


class SkillCreate(SkillBase):
    """Schema for creating a skill."""

    pass


class Skill(SkillBase):
    """Complete skill model."""

    persons_count: int = 0

    class Config:
        from_attributes = True
