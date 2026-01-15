"""Vision Worker - AI Eyes for Media Analysis.

Analyzes photos and videos using Gemini Vision to:
- Extract tags (objects, scenes, activities)
- Detect brands and logos
- Understand lifestyle and preferences
- Generate embeddings for similarity search
"""

import asyncio
import base64
import json
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import get_settings
from app.db.neo4j import Neo4jDB
from app.media.storage import MediaStorage
from app.media.models import (
    MediaFile,
    MediaType,
    MediaStatus,
    MediaAnalysis,
    VisualTag,
    Brand,
    Concept,
    LifestyleIndicator,
    EmotionAnalysis,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vision_worker")


# Vision analysis prompt
VISION_PROMPT = """Ты - эксперт по анализу визуального контента для построения профиля человека.

Проанализируй это изображение/видео и предоставь детальный анализ в JSON формате:

{
    "scene_description": "Подробное описание сцены на русском языке",
    "detected_objects": ["список", "обнаруженных", "объектов"],
    "detected_people_count": 0,
    "detected_text": ["текст", "если виден"],
    
    "tags": [
        {"name": "название тега", "category": "object|scene|activity|emotion|style", "confidence": 0.9}
    ],
    
    "brands": [
        {"name": "название бренда", "category": "категория", "confidence": 0.8, "logo_detected": true}
    ],
    
    "emotion": {
        "dominant_emotion": "happy|sad|neutral|excited|relaxed",
        "emotions": {"happy": 0.8, "neutral": 0.2},
        "sentiment": 0.7
    },
    
    "lifestyle_indicators": [
        {"category": "health|wealth|social|work|hobby", "indicator": "индикатор", "description": "описание", "confidence": 0.8}
    ],
    
    "concepts": [
        {"name": "концепт (напр. минимализм, роскошь)", "category": "style|lifestyle|taste|interest", "strength": 0.8}
    ],
    
    "ai_summary": "Краткое резюме о человеке на основе контента. Что можно сказать о его вкусах, стиле жизни, интересах?"
}

Важно:
- Определяй бренды одежды, техники, автомобилей
- Выделяй стиль (минимализм, лофт, классика и т.д.)
- Оценивай уровень достатка по косвенным признакам
- Определяй интересы и хобби
- Анализируй эмоциональный фон
"""


class VisionWorker:
    """AI Vision Worker for media analysis."""
    
    def __init__(self):
        self.settings = get_settings()
        self._ai_client = None
        self._chroma_client = None
        self._collection = None
    
    async def _get_ai_client(self):
        """Get AI vision client (Gemini or OpenAI)."""
        if self._ai_client is None:
            if self.settings.gemini_api_key:
                import google.generativeai as genai
                genai.configure(api_key=self.settings.gemini_api_key)
                self._ai_client = genai.GenerativeModel(self.settings.gemini_vision_model)
            elif self.settings.openai_api_key:
                from openai import AsyncOpenAI
                self._ai_client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        return self._ai_client
    
    def _get_chroma_client(self):
        """Get ChromaDB client for embeddings."""
        if self._chroma_client is None:
            self._chroma_client = chromadb.HttpClient(
                host=self.settings.chroma_host,
                port=self.settings.chroma_port,
            )
            # Get or create collection for media embeddings
            self._collection = self._chroma_client.get_or_create_collection(
                name="media_embeddings",
                metadata={"hnsw:space": "cosine"}
            )
        return self._chroma_client, self._collection
    
    async def analyze_media(self, media: MediaFile) -> MediaAnalysis:
        """Analyze a media file using AI Vision.
        
        Args:
            media: MediaFile to analyze
            
        Returns:
            MediaAnalysis with extracted information
        """
        logger.info(f"Analyzing media: {media.id} ({media.media_type})")
        
        # Download file from storage
        try:
            file_data = MediaStorage.download_file(media)
        except Exception as e:
            logger.error(f"Failed to download media {media.id}: {e}")
            raise
        
        # Get AI client
        ai_client = await self._get_ai_client()
        if not ai_client:
            raise ValueError("No AI client configured (need GEMINI_API_KEY or OPENAI_API_KEY)")
        
        # Prepare image/video for AI
        if media.media_type == MediaType.PHOTO:
            result = await self._analyze_image(ai_client, file_data, media.content_type)
        elif media.media_type == MediaType.VIDEO:
            result = await self._analyze_video(ai_client, file_data, media.content_type)
        else:
            raise ValueError(f"Unsupported media type: {media.media_type}")
        
        # Create analysis object
        analysis = MediaAnalysis(
            media_id=media.id,
            user_id=media.user_id,
            media_type=media.media_type,
            **result,
            ai_model=self.settings.gemini_vision_model if self.settings.gemini_api_key else self.settings.openai_vision_model,
        )
        
        # Save embedding to ChromaDB
        embedding_id = await self._save_embedding(analysis, file_data)
        analysis.embedding_id = embedding_id
        
        # Save to Neo4j Taste Graph
        await self._update_taste_graph(analysis)
        
        logger.info(f"Analysis complete: {len(analysis.tags)} tags, {len(analysis.brands)} brands")
        return analysis
    
    async def _analyze_image(
        self,
        ai_client,
        image_data: bytes,
        content_type: str,
    ) -> dict:
        """Analyze image using AI Vision."""
        
        if hasattr(ai_client, 'generate_content'):
            # Gemini
            import google.generativeai as genai
            
            # Create image part
            image_part = {
                "mime_type": content_type,
                "data": image_data
            }
            
            response = await ai_client.generate_content_async([
                VISION_PROMPT,
                image_part,
            ])
            response_text = response.text
        else:
            # OpenAI
            base64_image = base64.b64encode(image_data).decode()
            
            response = await ai_client.chat.completions.create(
                model=self.settings.openai_vision_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type};base64,{base64_image}"
                            }
                        }
                    ]
                }],
                max_tokens=2000,
            )
            response_text = response.choices[0].message.content
        
        return self._parse_vision_response(response_text)
    
    async def _analyze_video(
        self,
        ai_client,
        video_data: bytes,
        content_type: str,
    ) -> dict:
        """Analyze video using AI Vision (Gemini 1.5 Pro supports video)."""
        
        if hasattr(ai_client, 'generate_content'):
            # Gemini - supports video directly
            video_part = {
                "mime_type": content_type,
                "data": video_data
            }
            
            response = await ai_client.generate_content_async([
                VISION_PROMPT + "\n\nЭто видео. Проанализируй ключевые моменты.",
                video_part,
            ])
            response_text = response.text
        else:
            # OpenAI - extract frames and analyze
            # For simplicity, we'll just note that video analysis requires Gemini
            return {
                "scene_description": "Видео анализ требует Gemini 1.5 Pro",
                "tags": [],
                "brands": [],
                "concepts": [],
                "ai_summary": "Для анализа видео настройте GEMINI_API_KEY",
            }
        
        return self._parse_vision_response(response_text)
    
    def _parse_vision_response(self, response_text: str) -> dict:
        """Parse AI vision response JSON."""
        try:
            # Find JSON in response
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start != -1 and end > start:
                data = json.loads(response_text[start:end])
            else:
                raise ValueError("No JSON found in response")
            
            # Convert to model objects
            result = {
                "scene_description": data.get("scene_description", ""),
                "detected_objects": data.get("detected_objects", []),
                "detected_people_count": data.get("detected_people_count", 0),
                "detected_text": data.get("detected_text", []),
                "ai_summary": data.get("ai_summary", ""),
            }
            
            # Parse tags
            result["tags"] = [
                VisualTag(**t) for t in data.get("tags", [])
            ]
            
            # Parse brands
            result["brands"] = [
                Brand(**b) for b in data.get("brands", [])
            ]
            
            # Parse concepts
            result["concepts"] = [
                Concept(**c) for c in data.get("concepts", [])
            ]
            
            # Parse emotion
            if "emotion" in data and data["emotion"]:
                result["emotion"] = EmotionAnalysis(**data["emotion"])
            
            # Parse lifestyle
            result["lifestyle_indicators"] = [
                LifestyleIndicator(**li) for li in data.get("lifestyle_indicators", [])
            ]
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse vision response: {e}")
            return {
                "scene_description": response_text[:500],
                "tags": [],
                "brands": [],
                "concepts": [],
                "ai_summary": "Не удалось распарсить ответ AI",
            }
    
    async def _save_embedding(
        self,
        analysis: MediaAnalysis,
        file_data: bytes,
    ) -> Optional[str]:
        """Save media embedding to ChromaDB."""
        try:
            _, collection = self._get_chroma_client()
            
            # Create text representation for embedding
            text = f"""
            Scene: {analysis.scene_description}
            Objects: {', '.join(analysis.detected_objects)}
            Tags: {', '.join(t.name for t in analysis.tags)}
            Brands: {', '.join(b.name for b in analysis.brands)}
            Concepts: {', '.join(c.name for c in analysis.concepts)}
            Summary: {analysis.ai_summary}
            """
            
            embedding_id = str(analysis.media_id)
            
            collection.add(
                ids=[embedding_id],
                documents=[text],
                metadatas=[{
                    "user_id": str(analysis.user_id),
                    "media_type": analysis.media_type.value,
                    "analyzed_at": analysis.analyzed_at.isoformat(),
                }]
            )
            
            return embedding_id
            
        except Exception as e:
            logger.error(f"Failed to save embedding: {e}")
            return None
    
    async def _update_taste_graph(self, analysis: MediaAnalysis) -> None:
        """Update Neo4j Taste Graph with analysis results."""
        try:
            async with Neo4jDB.session() as session:
                # Add concepts as preferences
                for concept in analysis.concepts:
                    await session.run("""
                        MATCH (p:Person {id: $person_id})
                        MERGE (c:Concept {name: $concept_name})
                        ON CREATE SET c.category = $category
                        MERGE (p)-[r:LIKES]->(c)
                        ON CREATE SET r.strength = $strength, r.first_seen = datetime()
                        ON MATCH SET r.strength = (r.strength + $strength) / 2,
                                     r.evidence_count = coalesce(r.evidence_count, 0) + 1,
                                     r.last_seen = datetime()
                    """, {
                        "person_id": str(analysis.user_id),
                        "concept_name": concept.name,
                        "category": concept.category,
                        "strength": concept.strength,
                    })
                
                # Add brands
                for brand in analysis.brands:
                    await session.run("""
                        MATCH (p:Person {id: $person_id})
                        MERGE (b:Brand {name: $brand_name})
                        ON CREATE SET b.category = $category
                        MERGE (p)-[r:WEARS]->(b)
                        ON CREATE SET r.confidence = $confidence, r.first_seen = datetime()
                        ON MATCH SET r.confidence = (r.confidence + $confidence) / 2,
                                     r.evidence_count = coalesce(r.evidence_count, 0) + 1,
                                     r.last_seen = datetime()
                    """, {
                        "person_id": str(analysis.user_id),
                        "brand_name": brand.name,
                        "category": brand.category,
                        "confidence": brand.confidence,
                    })
                
                # Add lifestyle indicators
                for indicator in analysis.lifestyle_indicators:
                    await session.run("""
                        MATCH (p:Person {id: $person_id})
                        MERGE (l:Lifestyle {name: $indicator, category: $category})
                        MERGE (p)-[r:HAS_LIFESTYLE]->(l)
                        ON CREATE SET r.description = $description,
                                      r.confidence = $confidence,
                                      r.first_seen = datetime()
                        ON MATCH SET r.confidence = (r.confidence + $confidence) / 2,
                                     r.last_seen = datetime()
                    """, {
                        "person_id": str(analysis.user_id),
                        "indicator": indicator.indicator,
                        "category": indicator.category,
                        "description": indicator.description,
                        "confidence": indicator.confidence,
                    })
                
                logger.info(f"Updated taste graph for user {analysis.user_id}")
                
        except Exception as e:
            logger.error(f"Failed to update taste graph: {e}")
    
    async def search_similar(
        self,
        user_id: UUID,
        query: str,
        limit: int = 20,
    ) -> list[dict]:
        """Search for similar media by text query."""
        try:
            _, collection = self._get_chroma_client()
            
            results = collection.query(
                query_texts=[query],
                n_results=limit,
                where={"user_id": str(user_id)},
            )
            
            return [
                {
                    "media_id": results["ids"][0][i],
                    "distance": results["distances"][0][i] if results.get("distances") else None,
                    "document": results["documents"][0][i] if results.get("documents") else None,
                }
                for i in range(len(results["ids"][0]))
            ]
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []


async def run_worker():
    """Run Vision Worker as background service."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    
    settings = get_settings()
    
    logger.info("Starting Vision Worker...")
    
    # Connect to services
    MediaStorage.connect()
    await Neo4jDB.connect()
    
    worker = VisionWorker()
    
    async def process_pending_media():
        """Process pending media files."""
        logger.info("Checking for pending media...")
        # In production, query database for unprocessed media
        # For now, just log
        logger.info("Vision Worker cycle complete")
    
    # Setup scheduler
    scheduler = AsyncIOScheduler()
    
    # Parse cron schedule
    cron_parts = settings.vision_worker_schedule.split()
    trigger = CronTrigger(
        minute=cron_parts[0],
        hour=cron_parts[1],
        day=cron_parts[2],
        month=cron_parts[3],
        day_of_week=cron_parts[4],
    )
    
    scheduler.add_job(process_pending_media, trigger, id="vision_worker")
    scheduler.start()
    
    logger.info(f"Vision Worker started. Schedule: {settings.vision_worker_schedule}")
    
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        await Neo4jDB.disconnect()
        logger.info("Vision Worker stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())
