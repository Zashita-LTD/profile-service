"""Media data models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MediaType(str, Enum):
    """Types of media content."""
    PHOTO = "photo"
    VIDEO = "video"
    VOICE = "voice"
    DOCUMENT = "document"


class MediaStatus(str, Enum):
    """Media processing status."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    FAILED = "failed"


class MediaFile(BaseModel):
    """Media file metadata."""
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    media_type: MediaType
    
    # Storage
    bucket: str
    object_key: str
    filename: str
    content_type: str
    size_bytes: int
    
    # Status
    status: MediaStatus = MediaStatus.UPLOADED
    
    # Timestamps
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    analyzed_at: Optional[datetime] = None
    
    # Encryption
    encrypted: bool = False
    encryption_iv: Optional[str] = None  # Base64 encoded
    
    @property
    def storage_path(self) -> str:
        """Get full storage path."""
        return f"{self.user_id}/{self.media_type.value}s/{self.object_key}"


class VisualTag(BaseModel):
    """Tag extracted from visual content."""
    name: str
    category: str  # object, scene, activity, emotion, brand, style
    confidence: float = Field(..., ge=0, le=1)
    bounding_box: Optional[dict] = None  # x, y, width, height (normalized)


class Brand(BaseModel):
    """Detected brand from media."""
    name: str
    category: str  # clothing, electronics, food, automotive, etc.
    confidence: float = Field(..., ge=0, le=1)
    logo_detected: bool = False


class Concept(BaseModel):
    """Abstract concept/preference derived from media."""
    name: str
    category: str  # style, lifestyle, taste, interest
    strength: float = Field(..., ge=0, le=1)  # How strongly associated
    evidence_count: int = 1


class EmotionAnalysis(BaseModel):
    """Emotional analysis of media."""
    dominant_emotion: str  # happy, sad, neutral, excited, etc.
    emotions: dict[str, float]  # emotion -> score
    sentiment: float = Field(..., ge=-1, le=1)  # -1 negative, 1 positive


class LifestyleIndicator(BaseModel):
    """Lifestyle indicator from media analysis."""
    category: str  # health, wealth, social, work, hobby
    indicator: str
    description: str
    confidence: float


class MediaAnalysis(BaseModel):
    """Complete analysis result for media file."""
    media_id: UUID
    user_id: UUID
    media_type: MediaType
    
    # Visual analysis
    tags: list[VisualTag] = Field(default_factory=list)
    brands: list[Brand] = Field(default_factory=list)
    
    # Scene understanding
    scene_description: str = ""
    detected_objects: list[str] = Field(default_factory=list)
    detected_people_count: int = 0
    detected_text: list[str] = Field(default_factory=list)
    
    # Emotional/contextual
    emotion: Optional[EmotionAnalysis] = None
    lifestyle_indicators: list[LifestyleIndicator] = Field(default_factory=list)
    
    # Concepts (abstract)
    concepts: list[Concept] = Field(default_factory=list)
    
    # AI reasoning
    ai_summary: str = ""
    ai_model: str = ""
    
    # Embeddings
    embedding_id: Optional[str] = None  # ChromaDB ID
    
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class TasteProfile(BaseModel):
    """Aggregated taste profile from all media."""
    user_id: UUID
    
    # Style preferences
    preferred_styles: list[Concept] = Field(default_factory=list)
    
    # Brand affinity
    favorite_brands: list[Brand] = Field(default_factory=list)
    
    # Lifestyle
    lifestyle_tags: list[str] = Field(default_factory=list)
    
    # Interests
    interests: list[Concept] = Field(default_factory=list)
    
    # Statistics
    total_media_analyzed: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    # Derived personality traits
    personality_hints: dict[str, str] = Field(default_factory=dict)


class MediaUploadRequest(BaseModel):
    """Request to upload media."""
    user_id: UUID
    media_type: MediaType
    filename: str
    content_type: str
    encrypt: bool = True  # Encrypt by default


class MediaUploadResponse(BaseModel):
    """Response with upload URL."""
    media_id: UUID
    upload_url: str
    expires_in: int = 3600  # seconds


class MediaQueryRequest(BaseModel):
    """Request to query media by similarity."""
    user_id: UUID
    query: str  # Natural language or image embedding
    media_types: Optional[list[MediaType]] = None
    limit: int = Field(default=20, ge=1, le=100)
