# Profile Service - Universal Human Profile / Digital Biographer

Сервис для построения глубоких цифровых профилей людей (Human Knowledge Graph).

## 🎯 Что это даёт

- **Поиск связей**: "Кто из моих знакомых знает директора Кнауф?" — граф найдёт путь за миллисекунды
- **Психологический портрет**: AI проанализирует историю и скажет: "Он консерватор, любит надёжность, не предлагай ему стартапы"
- **Web 3.0 Identity**: В будущем этот профиль может стать SBT (Soulbound Token) — цифровым паспортом репутации

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                     Profile Service                          │
├──────────┬──────────┬──────────┬──────────┬────────────────┤
│ GraphQL  │   REST   │  Kafka   │    AI    │  Enrichment    │
│   API    │   API    │ Consumer │ Analysis │   Pipeline     │
├──────────┴──────────┴──────────┴──────────┴────────────────┤
│                     Business Logic                           │
├─────────────────────────────┬───────────────────────────────┤
│        Neo4j                │         PostgreSQL            │
│   (Graph Database)          │    (Documents & History)      │
│   - Person, Company         │    - PersonDocument           │
│   - Skills, Interests       │    - PersonFact               │
│   - Relationships           │    - Biography                │
└─────────────────────────────┴───────────────────────────────┘
```

## 📊 Графовая модель

```cypher
(:Person)-[:WORKS_AT {role, since, until}]->(:Company)
(:Person)-[:KNOWS {strength, context}]->(:Person)
(:Person)-[:HAS_SKILL {level, years}]->(:Skill)
(:Person)-[:INTERESTED_IN {level}]->(:Interest)
(:Person)-[:PARTICIPATED_IN {role}]->(:Event)
```

## 🚀 Быстрый старт

### Docker Compose

```bash
# Запустить все сервисы
docker compose up -d

# С Kafka consumer
docker compose --profile consumer up -d
```

Сервисы:
- **API**: http://localhost:8002
- **GraphQL**: http://localhost:8002/graphql
- **Neo4j Browser**: http://localhost:7474

### Локально

```bash
# Установить зависимости
pip install -e .

# Запустить базы (Docker)
docker compose up -d neo4j postgres

# Запустить API
python -m app.main
```

## 📡 GraphQL API

### Получить человека с карьерой и друзьями

```graphql
query {
  person(id: "uuid-here") {
    name
    career {
      company { name }
      role
      since
      isCurrent
    }
    friends(depth: 2) {
      person { name }
      distance
      strength
    }
    personality {
      personalityType
      communicationStyle
      decisionMaking
    }
    networkStats {
      directConnections
      secondDegree
      networkReach
    }
  }
}
```

### Найти экспертов

```graphql
query {
  findExperts(skill: "BIM", location: "Москва", minLevel: "advanced") {
    person {
      name
      location
    }
    skill {
      name
      level
      yearsExperience
    }
  }
}
```

### Найти путь между людьми

```graphql
query {
  findPath(fromId: "uuid-1", toId: "uuid-2") {
    nodes { name }
    distance
    intermediaries
  }
}
```

### Сгенерировать биографию (AI)

```graphql
mutation {
  generateBiography(input: {
    personId: "uuid-here"
    style: "professional"
    language: "ru"
  }) {
    content
    factsCount
    modelUsed
  }
}
```

### Анализ личности (AI)

```graphql
mutation {
  analyzePersonality(personId: "uuid-here") {
    personality {
      personalityType
      communicationStyle
      summary
    }
  }
}
```

## 📥 REST API - Импорт данных

### Импорт Email

```bash
curl -X POST http://localhost:8002/api/ingest/email \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Добрый день!\n\nПрошу рассмотреть...\n\nС уважением,\nИван Петров\nДиректор по закупкам\nООО СтройТрест\n+7 (999) 123-45-67"
  }'
```

### Импорт Резюме

```bash
curl -X POST http://localhost:8002/api/ingest/resume \
  -H "Content-Type: application/json" \
  -d '{
    "content": "ИВАНОВ ИВАН ПЕТРОВИЧ\n\nОпыт работы:\n2020-настоящее время: ООО Защита ЛТД, Директор\n..."
  }'
```

### Импорт LinkedIn

```bash
curl -X POST http://localhost:8002/api/ingest/linkedin \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {"firstName": "Ivan", "lastName": "Petrov", ...},
    "url": "https://linkedin.com/in/ivanpetrov"
  }'
```

## 📨 Kafka Events

Топики:
- `events.email` - входящие email
- `events.linkedin` - данные LinkedIn
- `events.resume` - резюме

Формат сообщения:
```json
{
  "type": "email",
  "source": "erp-system",
  "data": {
    "content": "...",
    "person_id": "optional-uuid"
  }
}
```

## 🧠 AI Возможности

### Biography Generator
Собирает все факты из графа и генерирует связный текст:

> *"Иван начал карьеру в 2010 году в СтройТресте, где познакомился с Петром Сидоровым. Вместе они увлекаются рыбалкой и часто обсуждают новые строительные технологии. В 2018 году Иван перешёл в Защиту ЛТД, где применил свой 15-летний опыт в продажах..."*

### Personality Analyzer
Определяет психологический профиль на основе:
- Карьерного пути (стабильность/смена работ)
- Навыков (технические/коммуникативные)
- Интересов
- Стиля переписки

Выдаёт рекомендации: *"Предпочитает надёжных поставщиков с историей. Не предлагайте стартапы."*

## 📁 Структура проекта

```
profile-service/
├── app/
│   ├── api/
│   │   └── graphql/        # GraphQL Schema & Resolvers
│   ├── analysis/           # AI аналитика
│   │   ├── biography.py    # Генератор биографий
│   │   └── personality.py  # Анализ личности
│   ├── db/                 # Database connections
│   │   ├── neo4j.py
│   │   ├── postgres.py
│   │   └── models.py       # SQLAlchemy models
│   ├── events/             # Kafka consumer
│   ├── graph/              # Neo4j models & queries
│   │   ├── nodes.py
│   │   ├── rels.py
│   │   └── queries.py
│   ├── ingestion/          # Data parsers
│   │   ├── email_parser.py
│   │   ├── resume_parser.py
│   │   ├── linkedin_parser.py
│   │   └── enrichment.py
│   ├── config.py
│   └── main.py
├── docker-compose.yml
└── pyproject.toml
```

## 🔧 Переменные окружения

```env
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_USER=profile
POSTGRES_PASSWORD=profile123
POSTGRES_DB=profile_db

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# AI (Gemini)
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-1.5-flash
```

## 📈 Roadmap

- [x] GraphQL API
- [x] Neo4j Integration
- [x] PostgreSQL for documents
- [x] AI Biography Generator
- [x] Personality Analyzer
- [x] Email/Resume/LinkedIn parsers
- [x] Kafka event consumer
- [ ] Telegram bot integration
- [ ] CalDAV calendar sync
- [ ] SBT (Soulbound Token) export

## 📄 License

MIT
