# Profile Service

Graph-based profile service using Neo4j for managing People, Companies, Skills, Interests, Events and their relationships.

## 🎯 Назначение

Сервис управления профилями и связями между сущностями:
- Люди и их связи (кто кого знает)
- Компании и сотрудники
- Навыки и интересы
- События и встречи

## 📊 Граф-модель данных

```
┌─────────────────────────────────────────────────────────────────┐
│                        GRAPH SCHEMA                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────┐         WORKS_AT           ┌─────────┐            │
│   │ Person  │ ──────────────────────────▶│ Company │            │
│   │         │    {role, since}           │         │            │
│   └────┬────┘                            └─────────┘            │
│        │                                                         │
│        │ KNOWS                                                   │
│        │ {strength: 0.0-1.0}                                    │
│        ▼                                                         │
│   ┌─────────┐                                                    │
│   │ Person  │                                                    │
│   └────┬────┘                                                    │
│        │                                                         │
│        │ INTERESTED_IN          HAS_SKILL                       │
│        │                        │                                │
│        ▼                        ▼                                │
│   ┌──────────┐            ┌─────────┐                           │
│   │ Interest │            │  Skill  │                           │
│   │          │            │         │                           │
│   └──────────┘            └─────────┘                           │
│                                                                  │
│   ┌─────────┐     PARTICIPATED_IN      ┌─────────┐             │
│   │ Person  │ ─────────────────────────▶│  Event  │             │
│   │         │    {role: "host"}         │         │             │
│   └─────────┘                           └─────────┘             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 🏗️ Структура проекта

```
profile-service/
├── src/
│   └── profile_service/
│       ├── __init__.py
│       ├── main.py              # FastAPI app
│       ├── config.py            # Settings
│       ├── database.py          # Neo4j connection
│       ├── models/              # Pydantic models
│       │   ├── __init__.py
│       │   ├── person.py
│       │   ├── company.py
│       │   ├── skill.py
│       │   ├── interest.py
│       │   └── event.py
│       ├── repositories/        # Neo4j queries
│       │   ├── __init__.py
│       │   ├── person_repo.py
│       │   ├── company_repo.py
│       │   └── relationship_repo.py
│       └── routers/             # API endpoints
│           ├── __init__.py
│           ├── persons.py
│           ├── companies.py
│           ├── relationships.py
│           └── graph.py
├── tests/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

## 🚀 Быстрый старт

### С Docker Compose

```bash
# Запуск Neo4j + API
docker-compose up -d

# API доступен на http://localhost:8002
# Neo4j Browser на http://localhost:7474
```

### Локально

```bash
# Установка зависимостей
pip install -e .

# Запуск Neo4j (Docker)
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5

# Запуск API
uvicorn profile_service.main:app --reload --port 8002
```

## 📡 API Endpoints

### Persons
- `POST /api/persons` - Создать персону
- `GET /api/persons/{id}` - Получить персону
- `GET /api/persons` - Список персон
- `PUT /api/persons/{id}` - Обновить персону
- `DELETE /api/persons/{id}` - Удалить персону

### Companies
- `POST /api/companies` - Создать компанию
- `GET /api/companies/{id}` - Получить компанию
- `GET /api/companies` - Список компаний

### Relationships
- `POST /api/relationships/works-at` - Человек работает в компании
- `POST /api/relationships/knows` - Люди знакомы
- `POST /api/relationships/interested-in` - Интерес
- `POST /api/relationships/has-skill` - Навык

### Graph Queries
- `GET /api/graph/connections/{person_id}` - Связи человека
- `GET /api/graph/shortest-path` - Кратчайший путь между людьми
- `GET /api/graph/common-interests` - Общие интересы
- `GET /api/graph/colleagues/{person_id}` - Коллеги

## 🔍 Примеры Cypher запросов

```cypher
// Найти всех знакомых с силой связи > 0.5
MATCH (p:Person {id: $personId})-[k:KNOWS]->(friend:Person)
WHERE k.strength > 0.5
RETURN friend, k.strength

// Найти путь между двумя людьми
MATCH path = shortestPath(
  (a:Person {id: $person1})-[*]-(b:Person {id: $person2})
)
RETURN path

// Люди с общими интересами
MATCH (p1:Person)-[:INTERESTED_IN]->(i:Interest)<-[:INTERESTED_IN]-(p2:Person)
WHERE p1.id = $personId AND p1 <> p2
RETURN p2, collect(i.name) as commonInterests

// Коллеги по компании
MATCH (p:Person {id: $personId})-[:WORKS_AT]->(c:Company)<-[:WORKS_AT]-(colleague:Person)
WHERE p <> colleague
RETURN colleague, c.name as company
```

## 🧪 Тесты

```bash
pytest tests/ -v
```

## 📝 Лицензия

MIT
