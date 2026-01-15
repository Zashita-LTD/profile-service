"""Pattern Miner Worker - AI Analyst for Life Stream.

This worker runs periodically (default: daily at 3 AM) and analyzes
life events to discover patterns, habits, and routines.

Capabilities:
- Geo clustering: Discovers frequently visited places
- Time patterns: Identifies daily/weekly routines
- Social patterns: Analyzes relationship interactions
- Purchase patterns: Finds spending habits
- Generates insights and saves them to Neo4j graph
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

import numpy as np
from sklearn.cluster import DBSCAN

from app.config import get_settings
from app.life_stream.clickhouse import ClickHouseDB
from app.db.neo4j import Neo4jDB

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("pattern_miner")


class PatternMiner:
    """AI Pattern Mining Worker for Life Stream data.
    
    Analyzes life events and discovers patterns like:
    - Location clusters (home, work, gym, favorite cafe)
    - Time-based routines (morning coffee, evening walk)
    - Social patterns (weekly lunch with X)
    - Purchase habits (coffee every morning)
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._ai_client = None
    
    async def _get_ai_client(self):
        """Get AI client for reasoning."""
        if self._ai_client is None:
            if self.settings.gemini_api_key:
                import google.generativeai as genai
                genai.configure(api_key=self.settings.gemini_api_key)
                self._ai_client = genai.GenerativeModel(self.settings.gemini_model)
            elif self.settings.openai_api_key:
                from openai import AsyncOpenAI
                self._ai_client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        return self._ai_client
    
    async def run_analysis(
        self,
        user_id: UUID,
        days_back: int = 30,
    ) -> dict:
        """Run full pattern analysis for a user.
        
        Args:
            user_id: User to analyze
            days_back: Days of history to analyze
            
        Returns:
            Analysis results with discovered patterns
        """
        logger.info(f"Starting pattern analysis for user {user_id}, {days_back} days back")
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days_back)
        
        results = {
            "user_id": str(user_id),
            "analyzed_period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "patterns_found": [],
            "insights_generated": [],
        }
        
        # 1. Analyze geo patterns (location clusters)
        geo_patterns = await self.analyze_geo_patterns(user_id, start_time, end_time)
        results["patterns_found"].extend(geo_patterns)
        
        # 2. Analyze time patterns (routines)
        time_patterns = await self.analyze_time_patterns(user_id, start_time, end_time)
        results["patterns_found"].extend(time_patterns)
        
        # 3. Generate AI insights
        if geo_patterns or time_patterns:
            insights = await self.generate_ai_insights(user_id, geo_patterns, time_patterns)
            results["insights_generated"].extend(insights)
        
        # 4. Save patterns to ClickHouse
        for pattern in results["patterns_found"]:
            pattern["user_id"] = str(user_id)
            await ClickHouseDB.save_pattern(pattern)
        
        # 5. Save insights to Neo4j graph
        for insight in results["insights_generated"]:
            await self.save_insight_to_graph(user_id, insight)
        
        logger.info(f"Analysis complete: {len(results['patterns_found'])} patterns, "
                   f"{len(results['insights_generated'])} insights")
        
        return results
    
    async def analyze_geo_patterns(
        self,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict]:
        """Discover location clusters using DBSCAN.
        
        Groups geo points into clusters representing frequently visited places.
        """
        logger.info("Analyzing geo patterns...")
        
        # Get geo points
        points = await ClickHouseDB.get_geo_points(
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            limit=self.settings.pattern_miner_batch_size,
        )
        
        if len(points) < self.settings.pattern_miner_min_cluster_size:
            logger.info(f"Not enough geo points ({len(points)}), skipping clustering")
            return []
        
        # Prepare coordinates for clustering
        coords = np.array([[p["lat"], p["lon"]] for p in points])
        timestamps = [p["timestamp"] for p in points]
        
        # DBSCAN clustering
        # eps in degrees (roughly 100m at equator)
        db = DBSCAN(eps=0.001, min_samples=self.settings.pattern_miner_min_cluster_size)
        labels = db.fit_predict(coords)
        
        # Analyze clusters
        patterns = []
        unique_labels = set(labels)
        
        for label in unique_labels:
            if label == -1:  # Noise points
                continue
            
            # Get cluster points
            mask = labels == label
            cluster_coords = coords[mask]
            cluster_times = [t for t, m in zip(timestamps, mask) if m]
            
            # Calculate cluster center and stats
            center_lat = float(np.mean(cluster_coords[:, 0]))
            center_lon = float(np.mean(cluster_coords[:, 1]))
            
            # Calculate radius (max distance from center)
            distances = np.sqrt(
                (cluster_coords[:, 0] - center_lat) ** 2 +
                (cluster_coords[:, 1] - center_lon) ** 2
            )
            radius_deg = float(np.max(distances))
            radius_meters = radius_deg * 111000  # Rough conversion
            
            # Time analysis
            visit_hours = [t.hour for t in cluster_times if t]
            most_common_hour = max(set(visit_hours), key=visit_hours.count) if visit_hours else 12
            
            # Generate name based on visit times
            if 6 <= most_common_hour <= 9:
                name_hint = "Утреннее место"
            elif 9 <= most_common_hour <= 18:
                name_hint = "Дневное место"
            elif 18 <= most_common_hour <= 22:
                name_hint = "Вечернее место"
            else:
                name_hint = "Ночное место"
            
            pattern = {
                "id": str(uuid4()),
                "pattern_type": "location_cluster",
                "name": f"{name_hint} #{label}",
                "description": f"Часто посещаемое место ({len(cluster_coords)} посещений)",
                "confidence": min(0.95, 0.5 + len(cluster_coords) / 100),
                "center_lat": center_lat,
                "center_lon": center_lon,
                "radius_meters": radius_meters,
                "first_seen": min(cluster_times).isoformat() if cluster_times else start_time.isoformat(),
                "last_seen": max(cluster_times).isoformat() if cluster_times else end_time.isoformat(),
                "occurrences": len(cluster_coords),
                "data": {
                    "visit_count": len(cluster_coords),
                    "most_common_hour": most_common_hour,
                    "visit_hours_distribution": {str(h): visit_hours.count(h) for h in set(visit_hours)},
                },
            }
            patterns.append(pattern)
        
        logger.info(f"Found {len(patterns)} location clusters")
        return patterns
    
    async def analyze_time_patterns(
        self,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict]:
        """Analyze time-based patterns and routines."""
        logger.info("Analyzing time patterns...")
        
        # Get hourly geo summary
        hourly = await ClickHouseDB.get_hourly_geo_summary(
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
        )
        
        if not hourly:
            logger.info("No hourly data for time pattern analysis")
            return []
        
        # Analyze by day of week and hour
        patterns = []
        
        # Group by hour of day
        hour_activity = {}
        for h in hourly:
            hour = h["hour"].hour if h["hour"] else 0
            if hour not in hour_activity:
                hour_activity[hour] = []
            hour_activity[hour].append(h)
        
        # Find peak activity hours
        for hour, activities in hour_activity.items():
            if len(activities) >= 5:  # At least 5 occurrences
                avg_points = np.mean([a["points_count"] for a in activities])
                
                if avg_points > 10:  # Significant activity
                    # Determine activity type by time
                    if 7 <= hour <= 9:
                        activity_name = "Утренняя активность (возможно дорога на работу)"
                    elif 12 <= hour <= 14:
                        activity_name = "Обеденная активность"
                    elif 17 <= hour <= 19:
                        activity_name = "Вечерняя активность (возможно дорога домой)"
                    else:
                        activity_name = f"Регулярная активность в {hour}:00"
                    
                    pattern = {
                        "id": str(uuid4()),
                        "pattern_type": "routine",
                        "name": activity_name,
                        "description": f"Регулярная активность около {hour}:00 ({len(activities)} дней)",
                        "confidence": min(0.9, 0.4 + len(activities) / 30),
                        "time_pattern": f"0 {hour} * * *",  # Cron format
                        "frequency_per_week": len(activities) / ((end_time - start_time).days / 7),
                        "first_seen": min(a["hour"] for a in activities).isoformat(),
                        "last_seen": max(a["hour"] for a in activities).isoformat(),
                        "occurrences": len(activities),
                        "data": {
                            "hour": hour,
                            "avg_points": float(avg_points),
                            "days_observed": len(activities),
                        },
                    }
                    patterns.append(pattern)
        
        logger.info(f"Found {len(patterns)} time patterns")
        return patterns
    
    async def generate_ai_insights(
        self,
        user_id: UUID,
        geo_patterns: list[dict],
        time_patterns: list[dict],
    ) -> list[dict]:
        """Generate AI insights from discovered patterns."""
        logger.info("Generating AI insights...")
        
        ai_client = await self._get_ai_client()
        if not ai_client:
            logger.warning("No AI client configured, skipping insight generation")
            return []
        
        # Prepare context for AI
        context = f"""
Analyze the following life patterns discovered from GPS and activity data:

## Location Clusters (Frequently Visited Places):
{json.dumps(geo_patterns, indent=2, default=str)}

## Time Patterns (Routines):
{json.dumps(time_patterns, indent=2, default=str)}

Based on these patterns, generate 2-3 meaningful insights about the person's lifestyle.
For each insight, provide:
1. A short title (habit name)
2. A description of the habit/pattern
3. Confidence score (0-1)

Format your response as JSON array:
[
    {{
        "title": "Habit name",
        "description": "Description of the pattern/habit",
        "confidence": 0.8,
        "insight_type": "habit|routine|preference"
    }}
]
"""
        
        try:
            if hasattr(ai_client, 'generate_content'):
                # Gemini
                response = await ai_client.generate_content_async(context)
                response_text = response.text
            else:
                # OpenAI
                response = await ai_client.chat.completions.create(
                    model=self.settings.openai_model,
                    messages=[{"role": "user", "content": context}],
                )
                response_text = response.choices[0].message.content
            
            # Parse response
            # Find JSON in response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            if start_idx != -1 and end_idx > start_idx:
                insights_data = json.loads(response_text[start_idx:end_idx])
            else:
                logger.warning("Could not parse AI response as JSON")
                return []
            
            insights = []
            for data in insights_data:
                insight = {
                    "id": str(uuid4()),
                    "user_id": str(user_id),
                    "insight_type": data.get("insight_type", "habit"),
                    "title": data.get("title", ""),
                    "description": data.get("description", ""),
                    "confidence": data.get("confidence", 0.5),
                    "evidence_count": len(geo_patterns) + len(time_patterns),
                    "time_range_start": datetime.utcnow() - timedelta(days=30),
                    "time_range_end": datetime.utcnow(),
                    "ai_model": self.settings.gemini_model if self.settings.gemini_api_key else self.settings.openai_model,
                    "reasoning": f"Based on {len(geo_patterns)} location clusters and {len(time_patterns)} time patterns",
                }
                insights.append(insight)
            
            logger.info(f"Generated {len(insights)} AI insights")
            return insights
            
        except Exception as e:
            logger.error(f"Failed to generate AI insights: {e}")
            return []
    
    async def save_insight_to_graph(self, user_id: UUID, insight: dict) -> Optional[str]:
        """Save insight to Neo4j as Habit node linked to Person.
        
        Creates: (Person)-[:HAS_HABIT]->(Habit)
        """
        try:
            async with Neo4jDB.session() as session:
                query = """
                    MATCH (p:Person {id: $person_id})
                    CREATE (h:Habit {
                        id: $habit_id,
                        name: $name,
                        description: $description,
                        confidence: $confidence,
                        insight_type: $insight_type,
                        discovered_at: datetime(),
                        ai_model: $ai_model
                    })
                    CREATE (p)-[:HAS_HABIT {discovered_at: datetime(), source: 'pattern_miner'}]->(h)
                    RETURN h.id as habit_id
                """
                
                result = await session.run(query, {
                    "person_id": str(user_id),
                    "habit_id": insight["id"],
                    "name": insight["title"],
                    "description": insight["description"],
                    "confidence": insight["confidence"],
                    "insight_type": insight["insight_type"],
                    "ai_model": insight.get("ai_model", ""),
                })
                
                record = await result.single()
                if record:
                    insight["neo4j_node_id"] = record["habit_id"]
                    await ClickHouseDB.save_insight(insight)
                    logger.info(f"Saved habit to graph: {insight['title']}")
                    return record["habit_id"]
                    
        except Exception as e:
            logger.error(f"Failed to save insight to graph: {e}")
        
        return None


async def run_miner():
    """Run pattern miner as standalone worker."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    
    settings = get_settings()
    
    # Connect to databases
    logger.info("Connecting to databases...")
    await ClickHouseDB.connect()
    await Neo4jDB.connect()
    
    miner = PatternMiner()
    
    async def analyze_all_users():
        """Analyze all users with recent activity."""
        # In production, this would query for users with recent events
        # For now, just log that it would run
        logger.info("Pattern Miner scheduled job would run here")
        logger.info("In production, iterate over users with recent activity")
    
    # Setup scheduler
    scheduler = AsyncIOScheduler()
    
    # Parse cron schedule (default: 0 3 * * * = daily at 3 AM)
    cron_parts = settings.pattern_miner_schedule.split()
    trigger = CronTrigger(
        minute=cron_parts[0],
        hour=cron_parts[1],
        day=cron_parts[2],
        month=cron_parts[3],
        day_of_week=cron_parts[4],
    )
    
    scheduler.add_job(analyze_all_users, trigger, id="pattern_miner")
    scheduler.start()
    
    logger.info(f"Pattern Miner started. Schedule: {settings.pattern_miner_schedule}")
    
    try:
        # Keep running
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        await ClickHouseDB.disconnect()
        await Neo4jDB.disconnect()
        logger.info("Pattern Miner stopped")


if __name__ == "__main__":
    asyncio.run(run_miner())
