# Life Stream Module - Big Data для Profile Service

## Обзор

Life Stream - это модуль для сбора и анализа потока жизненных событий пользователя.
Он позволяет строить "цифровую биографию" в реальном времени, обнаруживать паттерны поведения
и предоставляет интерфейс "Второго мозга" для поиска по памяти.

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                      Life Stream Module                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌───────────────┐    ┌─────────────────┐  │
│  │  Ingestion   │    │  ClickHouse   │    │  Pattern Miner  │  │
│  │     API      │───▶│   (Events)    │◀───│    (AI Worker)  │  │
│  └──────────────┘    └───────────────┘    └─────────────────┘  │
│         │                    │                     │            │
│         │                    ▼                     ▼            │
│         │            ┌───────────────┐    ┌─────────────────┐  │
│         │            │  Patterns &   │    │     Neo4j       │  │
│         │            │   Insights    │───▶│  (Habits Graph) │  │
│         │            └───────────────┘    └─────────────────┘  │
│         │                    │                                  │
│         ▼                    ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Memory Search (RAG)                     │  │
│  │              "С кем я обедал в пятницу?"                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Компоненты

### 1. Ingestion API (`/api/v1/stream/ingest`)

Принимает батчи событий из различных источников:

```python
POST /api/v1/stream/ingest
{
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "events": [
        {"type": "geo", "lat": 55.75, "lon": 37.61, "ts": "2023-10-10T10:00:00"},
        {"type": "purchase", "item": "Latte", "amount": 300, "place": "Starbucks"},
        {"type": "social", "action": "meet", "person_id": "uuid-peter"}
    ]
}
```

#### Типы событий:

| Тип | Описание | Обязательные поля |
|-----|----------|-------------------|
| `geo` | GPS координаты | `lat`, `lon` |
| `purchase` | Покупка/транзакция | `item`, `amount` |
| `social` | Социальное взаимодействие | `action` |
| `health` | Метрики здоровья | `metric`, `value` |
| `activity` | Физическая активность | `activity`, `duration_minutes` |

### 2. ClickHouse Storage

Высокопроизводительное хранилище для миллионов событий:

```sql
-- Основная таблица событий
CREATE TABLE events (
    id UUID,
    user_id UUID,
    timestamp DateTime64(3),
    event_type LowCardinality(String),
    latitude Nullable(Float64),
    longitude Nullable(Float64),
    payload String  -- JSON
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (user_id, timestamp, event_type);
```

#### Материализованные представления:
- `geo_hourly` - почасовая агрегация GPS точек
- `purchase_stats` - статистика покупок по категориям

### 3. Pattern Miner (AI Worker)

Фоновый процесс, который "смотрит кино" вашей жизни:

```python
# Запуск воркера
docker compose --profile workers up pattern-miner

# Или вручную
python -m app.life_stream.workers.pattern_miner
```

#### Обнаруживаемые паттерны:

| Паттерн | Описание | Пример |
|---------|----------|--------|
| `location_cluster` | Часто посещаемые места | Дом, Офис, Спортзал |
| `routine` | Регулярные действия | Дорога на работу в 8:00 |
| `habit` | Поведенческие паттерны | Кофе каждое утро |

#### Алгоритмы:
- **DBSCAN** - кластеризация GPS точек
- **Time Series Analysis** - поиск временных паттернов
- **AI Reasoning (Gemini/OpenAI)** - генерация инсайтов

### 4. Memory Search API (`/api/v1/search/memory`)

"Второй мозг" с RAG (Retrieval Augmented Generation):

```python
POST /api/v1/search/memory
{
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "question": "С кем я обедал в прошлую пятницу?"
}
```

#### Как это работает:

1. **Парсинг вопроса** - извлечение временного диапазона и намерения
2. **Retrieval** - поиск релевантных событий в ClickHouse
3. **Context Building** - сбор контекста из Neo4j (люди, связи)
4. **Generation** - генерация ответа с помощью AI

#### Примеры вопросов:
- "Где я был в выходные?"
- "Сколько я потратил на кофе за месяц?"
- "С кем я чаще всего встречаюсь?"
- "Какие у меня привычки?"

## Запуск

### Docker Compose

```bash
# Запуск всех сервисов включая ClickHouse
docker compose up -d

# Запуск с Pattern Miner воркером
docker compose --profile workers up -d
```

### Проверка

```bash
# Health check
curl http://localhost:8002/health

# Ожидаемый ответ
{
    "status": "healthy",
    "neo4j": "connected",
    "postgres": "connected",
    "clickhouse": "connected"
}
```

## API Endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/v1/stream/ingest` | POST | Прием батча событий |
| `/api/v1/stream/ingest/single` | POST | Прием одного события |
| `/api/v1/stream/events/{user_id}` | GET | Получение событий |
| `/api/v1/stream/stats/{user_id}` | GET | Статистика событий |
| `/api/v1/stream/patterns/{user_id}` | GET | Обнаруженные паттерны |
| `/api/v1/search/memory` | POST | Поиск по памяти (RAG) |
| `/api/v1/search/memory/{user_id}/summary` | GET | Сводка за период |

## Конфигурация

### Переменные окружения

```env
# ClickHouse
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_DATABASE=life_stream

# Pattern Miner
PATTERN_MINER_SCHEDULE=0 3 * * *  # Cron: каждый день в 3:00
PATTERN_MINER_BATCH_SIZE=1000
PATTERN_MINER_MIN_CLUSTER_SIZE=3

# AI (для Pattern Miner и Memory Search)
GEMINI_API_KEY=your_key
```

## Интеграция с Neo4j

Pattern Miner создает связи в графе:

```cypher
// Обнаруженная привычка
(Person)-[:HAS_HABIT]->(Habit {
    name: "Кофе в 9:00",
    confidence: 0.85,
    discovered_at: datetime()
})

// Посещенное место
(Person)-[:VISITED]->(Location {
    name: "Офис",
    lat: 55.75,
    lon: 37.61
})
```

## Пример использования

### 1. Отправка GPS трека

```python
import httpx
from datetime import datetime, timedelta

# Симуляция GPS трека
events = []
start = datetime.now() - timedelta(hours=2)
for i in range(100):
    events.append({
        "type": "geo",
        "lat": 55.75 + i * 0.001,
        "lon": 37.61 + i * 0.001,
        "ts": (start + timedelta(minutes=i)).isoformat(),
        "speed": 1.5
    })

# Отправка
response = httpx.post(
    "http://localhost:8002/api/v1/stream/ingest",
    json={
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "events": events
    }
)
print(response.json())
```

### 2. Запрос к памяти

```python
response = httpx.post(
    "http://localhost:8002/api/v1/search/memory",
    json={
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "question": "Где я был сегодня?"
    }
)
print(response.json()["answer"])
```

## Масштабирование

### ClickHouse Cluster

Для production рекомендуется использовать ClickHouse cluster:

```yaml
# docker-compose.prod.yml
clickhouse:
    image: clickhouse/clickhouse-server:24-alpine
    deploy:
      replicas: 3
    environment:
      - CLICKHOUSE_CLUSTER=life_stream_cluster
```

### Pattern Miner Workers

```yaml
pattern-miner:
    deploy:
      replicas: 2  # Несколько воркеров для параллельного анализа
```

## Мониторинг

### ClickHouse метрики

```sql
-- Статистика по событиям
SELECT 
    event_type,
    count() as cnt,
    min(timestamp) as first,
    max(timestamp) as last
FROM events
GROUP BY event_type;

-- Размер данных
SELECT 
    table,
    formatReadableSize(sum(bytes)) as size,
    sum(rows) as rows
FROM system.parts
WHERE database = 'life_stream'
GROUP BY table;
```

## Roadmap

- [ ] Real-time streaming через WebSocket
- [ ] Интеграция с Apple Health / Google Fit
- [ ] Telegram/WhatsApp connector
- [ ] Голосовой интерфейс для Memory Search
- [ ] Экспорт в Personal Knowledge Graph (Obsidian, Notion)
