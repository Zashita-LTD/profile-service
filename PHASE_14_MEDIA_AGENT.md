# Profile Service v0.4.0 - Media Understanding & Personal Agent

## Обзор обновления

Версия 0.4.0 добавляет два мощных модуля:

1. **Media Understanding** - анализ фото/видео с Vision AI
2. **Personal Agent** - персональный AI-агент с A2A протоколом

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                     Profile Service v0.4.0                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │   GraphQL    │  │  Life Stream │  │ Media Understanding  │   │
│  │     API      │  │   Module     │  │      Module          │   │
│  │              │  │              │  │                      │   │
│  │ • Biography  │  │ • ClickHouse │  │ • MinIO Storage      │   │
│  │ • Experts    │  │ • Patterns   │  │ • Vision AI          │   │
│  │ • Paths      │  │ • Memory     │  │ • Taste Graph        │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  Personal Agent Module                    │   │
│  │                                                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │   │
│  │  │   Agent     │  │    A2A      │  │    Executor     │   │   │
│  │  │   Factory   │  │  Protocol   │  │   (Tool Use)    │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘   │   │
│  │                                                           │   │
│  │  • Personality extraction from Neo4j profile              │   │
│  │  • System prompt generation                               │   │
│  │  • Agent-to-Agent negotiation via Kafka                   │   │
│  │  • Task execution with tools                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                       Data Layer                                 │
│                                                                  │
│  ┌────────┐  ┌──────────┐  ┌─────────┐  ┌───────┐  ┌────────┐  │
│  │ Neo4j  │  │ClickHouse│  │  MinIO  │  │ChromaDB│  │ Kafka  │  │
│  │ Graph  │  │  Events  │  │ Objects │  │Vectors │  │Messages│  │
│  └────────┘  └──────────┘  └─────────┘  └───────┘  └────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Новые компоненты

### Media Understanding Module

| Компонент | Путь | Описание |
|-----------|------|----------|
| MediaStorage | `app/media/storage.py` | MinIO клиент с AES-256-GCM шифрованием |
| VisionWorker | `app/media/workers/vision_worker.py` | Gemini Vision анализ изображений/видео |
| TasteGraph | `app/media/taste_graph.py` | Neo4j схема для вкусов (бренды, стили) |
| Media API | `app/media/api/__init__.py` | REST endpoints для медиа |

### Personal Agent Module

| Компонент | Путь | Описание |
|-----------|------|----------|
| Models | `app/agent/models.py` | UserAgent, AgentTask, A2AMessage и др. |
| AgentFactory | `app/agent/factory.py` | Создание агента из профиля |
| A2AProtocol | `app/agent/protocol.py` | Kafka-based Agent-to-Agent протокол |
| AgentExecutor | `app/agent/executor.py` | Выполнение задач с инструментами |
| Agent API | `app/agent/api/__init__.py` | REST endpoints для агента |

## API Endpoints

### Media API (`/api/v1/media`)

```bash
# Загрузить медиа файл
POST /api/v1/media/upload
Content-Type: multipart/form-data
- user_id: UUID
- file: binary

# Получить галерею
GET /api/v1/media/{user_id}/gallery?page=1&page_size=20

# Получить профиль вкусов
GET /api/v1/media/{user_id}/taste-profile

# Найти похожие изображения
POST /api/v1/media/{user_id}/similar
{
    "media_id": "uuid",
    "limit": 10
}

# Анализ внешнего изображения
POST /api/v1/media/{user_id}/analyze-external?url=https://...
```

### Agent API (`/api/v1/agent`)

```bash
# Обучить персонального агента
POST /api/v1/agent/train
{
    "user_id": "uuid",
    "agent_role": "buyer",
    "custom_instructions": "Предпочитаю экологичные товары"
}

# Получить агента
GET /api/v1/agent/{user_id}

# Создать задачу
POST /api/v1/agent/{user_id}/task
{
    "instruction": "Найди кроссовки Nike до 15000 рублей",
    "max_iterations": 10
}

# Быстрое действие
POST /api/v1/agent/{user_id}/quick
{
    "action": "search",
    "query": "беспроводные наушники"
}

# Начать переговоры
POST /api/v1/agent/{user_id}/negotiate/start?seller_id=...&item=...&budget=5000
```

## Модели данных

### UserAgent
```python
class UserAgent(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    role: AgentRole  # buyer, seller, assistant
    system_prompt: str
    personality: PersonalityTraits
    preferred_brands: list[str]
    preferred_styles: list[str]
    active: bool
```

### PersonalityTraits
```python
class PersonalityTraits(BaseModel):
    openness: float           # 0-1 открытость новому
    conscientiousness: float  # 0-1 добросовестность
    extraversion: float       # 0-1 экстраверсия
    agreeableness: float      # 0-1 доброжелательность
    neuroticism: float        # 0-1 нейротизм
    risk_tolerance: float     # 0-1 толерантность к риску
    price_sensitivity: float  # 0-1 чувствительность к цене
    brand_loyalty: float      # 0-1 лояльность к брендам
```

### A2AMessage
```python
class A2AMessage(BaseModel):
    id: UUID
    from_agent_id: UUID
    to_agent_id: UUID
    conversation_id: UUID
    message_type: str  # request, offer, counter_offer, accept, reject
    content: str
    payload: dict
    offer: Optional[dict]  # {price, quantity, terms}
```

## Taste Graph (Neo4j)

```cypher
// Новые типы узлов
(:Concept {name, category})
(:Brand {name, category, price_tier})
(:Lifestyle {name, description})

// Новые связи
(:Person)-[:LIKES {score, confidence}]->(:Concept)
(:Person)-[:PREFERS {score, confidence}]->(:Brand)
(:Person)-[:IDENTIFIES_WITH {score}]->(:Lifestyle)
(:MediaFile)-[:CONTAINS]->(:Concept|Brand)
```

## Docker Compose

Новые сервисы:

```yaml
services:
  minio:
    image: minio/minio
    ports:
      - "9001:9000"      # API
      - "9002:9001"      # Console
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin123
    volumes:
      - minio_data:/data

  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - chroma_data:/chroma/chroma

  vision-worker:
    build: .
    command: python -m app.media.workers.vision_worker
    depends_on:
      - minio
      - chromadb

  agent-runtime:
    build: .
    command: python -m app.agent.executor
    depends_on:
      - kafka
```

## Конфигурация

Новые переменные окружения (`.env`):

```bash
# MinIO
MINIO_ENDPOINT=localhost:9001
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET=media-storage
MINIO_SECURE=false

# ChromaDB
CHROMADB_HOST=localhost
CHROMADB_PORT=8001

# Kafka (для A2A)
KAFKA_AGENT_TOPIC=agent.a2a

# Vision
GEMINI_VISION_MODEL=gemini-1.5-pro

# Media
MEDIA_MAX_FILE_SIZE=104857600  # 100MB
MEDIA_ENCRYPTION_KEY=  # auto-generated

# Agent
AGENT_MAX_ITERATIONS=10
```

## Пример использования

### 1. Загрузка и анализ фото

```python
import httpx

# Загрузить фото
with open("photo.jpg", "rb") as f:
    response = httpx.post(
        "http://localhost:8002/api/v1/media/upload",
        params={"user_id": "user-uuid"},
        files={"file": f}
    )

media_id = response.json()["id"]

# Получить анализ
analysis = httpx.get(
    f"http://localhost:8002/api/v1/media/{user_id}/analysis/{media_id}"
).json()

print(analysis["detected_brands"])  # ["Nike", "Adidas"]
print(analysis["style_tags"])       # ["sporty", "casual"]
```

### 2. Создание и использование агента

```python
# Обучить агента на основе профиля
agent = httpx.post(
    "http://localhost:8002/api/v1/agent/train",
    json={
        "user_id": "user-uuid",
        "agent_role": "buyer",
        "custom_instructions": "Ищу качественные товары, готов платить больше за бренд"
    }
).json()

print(agent["personality"])
# {
#     "openness": 0.7,
#     "price_sensitivity": 0.3,
#     "brand_loyalty": 0.8
# }

# Дать задачу агенту
task = httpx.post(
    f"http://localhost:8002/api/v1/agent/{user_id}/task",
    json={
        "instruction": "Найди лучшие кроссовки для бега до 20000 рублей"
    }
).json()
```

### 3. A2A переговоры

```python
# Начать переговоры с продавцом
negotiation = httpx.post(
    f"http://localhost:8002/api/v1/agent/{buyer_id}/negotiate/start",
    params={
        "seller_id": "seller-uuid",
        "item": "iPhone 15 Pro",
        "budget": 100000
    }
).json()

conversation_id = negotiation["conversation_id"]

# Сделать предложение
httpx.post(
    f"http://localhost:8002/api/v1/agent/{buyer_id}/negotiate/{conversation_id}/offer",
    json={"price": 85000}
)

# Проверить статус
status = httpx.get(
    f"http://localhost:8002/api/v1/agent/{buyer_id}/negotiate/{conversation_id}"
).json()

print(status["status"])  # "negotiating" | "agreed" | "failed"
```

## Зависимости

Новые пакеты в `pyproject.toml`:

```toml
dependencies = [
    # ... existing
    "minio>=7.2.0",
    "boto3>=1.34.0",
    "chromadb>=0.4.0",
    "pillow>=10.2.0",
    "cryptography>=42.0.0",
]
```

## Миграция с v0.3.0

1. Обновите зависимости: `pip install -e .`
2. Запустите новые сервисы: `docker-compose up -d minio chromadb`
3. Добавьте новые переменные в `.env`
4. Перезапустите сервис

## Changelog

### v0.4.0 (2025-01-XX)

**Added:**
- Media Understanding module
  - MinIO storage with AES-256-GCM encryption
  - Gemini Vision analysis for images and videos
  - ChromaDB for embedding storage and similarity search
  - Taste Graph in Neo4j (Concept, Brand, Lifestyle nodes)
  - REST API for media upload, gallery, analysis
  
- Personal Agent module
  - Agent Factory from user profile data
  - Personality extraction (Big Five + shopping traits)
  - System prompt generation
  - A2A Protocol via Kafka
  - Agent Executor with tool use
  - Negotiation flow (offer/counter-offer/accept)
  - REST API for training, tasks, quick actions

**Changed:**
- Updated version to 0.4.0
- Added MinIO, ChromaDB to docker-compose
- Extended config with media/agent settings

**Technical:**
- app/media/ module structure
- app/agent/ module structure
- Integration in main.py
- Updated .env.example
