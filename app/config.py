"""Application configuration."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8002
    api_debug: bool = False
    
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password123"
    
    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "profile"
    postgres_password: str = "profile123"
    postgres_db: str = "profile_db"
    
    # ClickHouse (Life Stream)
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "life_stream"
    
    # MinIO (Object Storage for Media)
    minio_endpoint: str = "localhost:9001"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket: str = "profile-media"
    minio_secure: bool = False
    
    # ChromaDB (Vector Database)
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    
    # Media Encryption
    media_encryption_key: str = ""  # 32-byte key for AES-256
    
    @property
    def chroma_url(self) -> str:
        """Get ChromaDB URL."""
        return f"http://{self.chroma_host}:{self.chroma_port}"
    
    @property
    def clickhouse_url(self) -> str:
        """Get ClickHouse HTTP URL."""
        return f"http://{self.clickhouse_host}:{self.clickhouse_port}"
    
    @property
    def postgres_url(self) -> str:
        """Get PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def postgres_url_sync(self) -> str:
        """Get sync PostgreSQL URL for Alembic."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "profile-service"
    kafka_topics: str = "events.email,events.linkedin,events.resume"
    kafka_agent_topic: str = "agent.messages"
    
    # AI - Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    gemini_vision_model: str = "gemini-1.5-pro"  # Vision-capable model
    
    # AI - OpenAI (fallback)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_vision_model: str = "gpt-4o"
    
    # Life Stream - Pattern Miner
    pattern_miner_schedule: str = "0 3 * * *"  # Run at 3 AM daily
    pattern_miner_batch_size: int = 1000
    pattern_miner_min_cluster_size: int = 3
    
    # Vision Worker
    vision_worker_schedule: str = "*/15 * * * *"  # Every 15 minutes
    vision_batch_size: int = 10
    
    # Agent Settings
    agent_max_iterations: int = 10
    agent_timeout_seconds: int = 300
    
    # Blockchain - Polygon
    polygon_rpc_url: str = "https://polygon-rpc.com"
    polygon_network: str = "polygon"  # polygon, mumbai, amoy
    reputation_contract_address: str = ""
    deployer_private_key: str = ""  # Only needed for minting
    
    # Voice - STT/TTS
    whisper_api_url: str = "https://api.openai.com/v1/audio/transcriptions"
    google_tts_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "pNInz6obpgDQGcFmaJgB"  # Adam
    
    chromadb_host: str = "localhost"
    chromadb_port: int = 8001
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
