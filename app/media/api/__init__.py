"""Media API - Endpoints for media management and analysis."""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query, BackgroundTasks
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from app.config import get_settings
from app.media.models import MediaType, MediaFile, MediaAnalysis, TasteProfile
from app.media.storage import MediaStorage, get_storage
from app.media.workers.vision_worker import VisionWorker

router = APIRouter(prefix="/media", tags=["media"])


# Request/Response models

class MediaUploadResponse(BaseModel):
    """Response for media upload."""
    id: UUID
    user_id: UUID
    media_type: MediaType
    original_filename: str
    storage_key: str
    size_bytes: int
    created_at: datetime
    analysis_status: str = "pending"


class MediaListResponse(BaseModel):
    """Response for media list."""
    items: list[MediaFile]
    total: int
    page: int
    page_size: int


class MediaAnalysisResponse(BaseModel):
    """Response with media analysis."""
    id: UUID
    media_id: UUID
    analysis_type: str
    detected_objects: list[str]
    detected_brands: list[str]
    detected_colors: list[str]
    style_tags: list[str]
    embedding: Optional[list[float]] = None
    raw_analysis: dict
    confidence: float
    created_at: datetime


class TasteProfileResponse(BaseModel):
    """Response with taste profile."""
    user_id: UUID
    preferred_brands: dict[str, float]
    preferred_colors: dict[str, float]
    preferred_styles: dict[str, float]
    lifestyle_indicators: dict[str, float]
    updated_at: datetime


class SimilarMediaRequest(BaseModel):
    """Request for similar media search."""
    media_id: Optional[UUID] = None
    embedding: Optional[list[float]] = None
    media_type: Optional[MediaType] = None
    limit: int = Field(default=10, ge=1, le=50)


class SimilarMediaResponse(BaseModel):
    """Response with similar media."""
    query_id: Optional[UUID]
    results: list[dict]
    total: int


# Endpoints

@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media(
    user_id: UUID,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    storage: MediaStorage = Depends(get_storage),
):
    """Upload media file and queue for analysis.
    
    Supported types:
    - Images: jpg, jpeg, png, gif, webp, heic
    - Videos: mp4, mov, avi, mkv, webm
    - Audio: mp3, wav, m4a, ogg, flac
    """
    settings = get_settings()
    
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    extension = file.filename.split(".")[-1].lower()
    
    if extension in ["jpg", "jpeg", "png", "gif", "webp", "heic"]:
        media_type = MediaType.PHOTO
    elif extension in ["mp4", "mov", "avi", "mkv", "webm"]:
        media_type = MediaType.VIDEO
    elif extension in ["mp3", "wav", "m4a", "ogg", "flac"]:
        media_type = MediaType.VOICE
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type: {extension}"
        )
    
    # Check file size
    content = await file.read()
    if len(content) > settings.media_max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {settings.media_max_file_size // 1024 // 1024}MB"
        )
    
    # Upload to storage
    try:
        media_file = await storage.upload_file(
            user_id=user_id,
            file_data=content,
            original_filename=file.filename,
            media_type=media_type,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    # Queue for analysis in background
    if background_tasks:
        background_tasks.add_task(
            _analyze_media_task,
            media_file.id,
            user_id,
            media_file.storage_key,
            media_type,
        )
    
    return MediaUploadResponse(
        id=media_file.id,
        user_id=user_id,
        media_type=media_type,
        original_filename=file.filename,
        storage_key=media_file.storage_key,
        size_bytes=len(content),
        created_at=media_file.created_at,
        analysis_status="queued",
    )


async def _analyze_media_task(
    media_id: UUID,
    user_id: UUID,
    storage_key: str,
    media_type: MediaType,
):
    """Background task to analyze media."""
    try:
        worker = VisionWorker()
        storage = get_storage()
        
        # Get file from storage
        file_data = await storage.get_file(user_id, storage_key)
        
        # Run analysis
        if media_type == MediaType.PHOTO:
            await worker.analyze_image(media_id, user_id, file_data)
        elif media_type == MediaType.VIDEO:
            await worker.analyze_video(media_id, user_id, file_data)
        # Audio analysis would go here
        
    except Exception as e:
        import logging
        logging.error(f"Media analysis failed for {media_id}: {e}")


@router.get("/{user_id}/gallery", response_model=MediaListResponse)
async def get_user_gallery(
    user_id: UUID,
    media_type: Optional[MediaType] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    storage: MediaStorage = Depends(get_storage),
):
    """Get user's media gallery with pagination."""
    
    # List files from storage
    files = await storage.list_files(
        user_id=user_id,
        media_type=media_type,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    
    total = await storage.count_files(user_id, media_type)
    
    return MediaListResponse(
        items=files,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{user_id}/file/{media_id}")
async def get_media_file(
    user_id: UUID,
    media_id: UUID,
    storage: MediaStorage = Depends(get_storage),
):
    """Get media file metadata and download URL."""
    
    file_info = await storage.get_file_info(user_id, media_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="Media not found")
    
    # Generate presigned URL for download
    download_url = await storage.get_presigned_url(
        user_id=user_id,
        storage_key=file_info.storage_key,
        expires_in=3600,  # 1 hour
    )
    
    return {
        **file_info.model_dump(),
        "download_url": download_url,
    }


@router.delete("/{user_id}/file/{media_id}")
async def delete_media_file(
    user_id: UUID,
    media_id: UUID,
    storage: MediaStorage = Depends(get_storage),
):
    """Delete media file."""
    
    deleted = await storage.delete_file(user_id, media_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Media not found")
    
    return {"deleted": True, "media_id": str(media_id)}


@router.get("/{user_id}/analysis/{media_id}", response_model=MediaAnalysisResponse)
async def get_media_analysis(
    user_id: UUID,
    media_id: UUID,
):
    """Get analysis results for a media file."""
    
    worker = VisionWorker()
    analysis = await worker.get_analysis(media_id)
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return MediaAnalysisResponse(
        id=analysis.id,
        media_id=analysis.media_id,
        analysis_type=analysis.analysis_type,
        detected_objects=analysis.detected_objects,
        detected_brands=analysis.detected_brands,
        detected_colors=analysis.detected_colors,
        style_tags=analysis.style_tags,
        raw_analysis=analysis.raw_analysis,
        confidence=analysis.confidence,
        created_at=analysis.created_at,
    )


@router.get("/{user_id}/taste-profile", response_model=TasteProfileResponse)
async def get_taste_profile(
    user_id: UUID,
):
    """Get user's aggregated taste profile from media analysis."""
    
    worker = VisionWorker()
    profile = await worker.get_user_taste_profile(user_id)
    
    if not profile:
        # Return empty profile if no data yet
        return TasteProfileResponse(
            user_id=user_id,
            preferred_brands={},
            preferred_colors={},
            preferred_styles={},
            lifestyle_indicators={},
            updated_at=datetime.utcnow(),
        )
    
    return TasteProfileResponse(
        user_id=user_id,
        preferred_brands=profile.preferred_brands,
        preferred_colors=profile.preferred_colors,
        preferred_styles=profile.preferred_styles,
        lifestyle_indicators=profile.lifestyle_indicators,
        updated_at=profile.updated_at,
    )


@router.post("/{user_id}/similar", response_model=SimilarMediaResponse)
async def find_similar_media(
    user_id: UUID,
    request: SimilarMediaRequest,
):
    """Find similar media by embedding or media_id."""
    
    worker = VisionWorker()
    
    if request.media_id:
        # Get embedding from existing media
        results = await worker.find_similar_by_media(
            media_id=request.media_id,
            limit=request.limit,
            media_type=request.media_type,
        )
    elif request.embedding:
        # Use provided embedding
        results = await worker.find_similar_by_embedding(
            embedding=request.embedding,
            limit=request.limit,
            media_type=request.media_type,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Either media_id or embedding must be provided"
        )
    
    return SimilarMediaResponse(
        query_id=request.media_id,
        results=results,
        total=len(results),
    )


@router.post("/{user_id}/analyze-external")
async def analyze_external_media(
    user_id: UUID,
    url: str = Query(..., description="URL of external media to analyze"),
    background_tasks: BackgroundTasks = None,
):
    """Analyze external media from URL (e.g., product images)."""
    
    import aiohttp
    from uuid import uuid4
    
    # Fetch external media
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to fetch URL: {response.status}"
                )
            
            content = await response.read()
    
    # Detect media type from content-type
    content_type = response.headers.get("content-type", "")
    if "image" in content_type:
        media_type = MediaType.PHOTO
    elif "video" in content_type:
        media_type = MediaType.VIDEO
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type: {content_type}"
        )
    
    # Analyze directly without storing
    worker = VisionWorker()
    
    if media_type == MediaType.PHOTO:
        analysis = await worker.analyze_image(
            media_id=uuid4(),
            user_id=user_id,
            image_data=content,
            store_result=False,  # Don't persist
        )
    else:
        analysis = await worker.analyze_video(
            media_id=uuid4(),
            user_id=user_id,
            video_data=content,
            store_result=False,
        )
    
    return {
        "url": url,
        "media_type": media_type.value,
        "analysis": analysis,
    }
