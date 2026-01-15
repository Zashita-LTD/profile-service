"""Media Understanding Module.

Provides:
- Object Storage integration (MinIO/S3) for photos, videos, voice
- Vision AI Worker for content analysis
- Taste Graph for preferences and brands
- Vector embeddings for similarity search
"""

from app.media.storage import MediaStorage
from app.media.models import (
    MediaFile,
    MediaType,
    MediaAnalysis,
    TasteProfile,
    Brand,
    Concept,
)

__all__ = [
    "MediaStorage",
    "MediaFile",
    "MediaType",
    "MediaAnalysis",
    "TasteProfile",
    "Brand",
    "Concept",
]
