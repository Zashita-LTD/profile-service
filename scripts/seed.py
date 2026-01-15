"""Seed script for initial test data."""

import asyncio
from datetime import datetime
from uuid import uuid4

from profile_service.database import Neo4jDatabase, init_constraints


async def seed_data():
    """Seed Neo4j with test data."""
    await Neo4jDatabase.connect()
    await init_constraints()

    async with Neo4jDatabase.get_session() as session:
        # Clear existing data
        await session.run("MATCH (n) DETACH DELETE n")
        print("🧹 Cleared existing data")

        # Create Persons
        persons = [
            {"id": str(uuid4()), "name": "Виктор Иванов", "email": "viktor@zashita.ru", "location": "Москва"},
            {"id": str(uuid4()), "name": "Артём Петров", "email": "artem@zashita.ru", "location": "Москва"},
            {"id": str(uuid4()), "name": "Мария Сидорова", "email": "maria@partner.ru", "location": "Санкт-Петербург"},
            {"id": str(uuid4()), "name": "Иван Козлов", "email": "ivan@supplier.ru", "location": "Казань"},
            {"id": str(uuid4()), "name": "Елена Новикова", "email": "elena@client.ru", "location": "Москва"},
        ]

        for p in persons:
            await session.run("""
                CREATE (p:Person {
                    id: $id, name: $name, email: $email, location: $location,
                    created_at: $now, updated_at: $now
                })
            """, **p, now=datetime.utcnow().isoformat())
        print(f"👤 Created {len(persons)} persons")

        # Create Companies
        companies = [
            {"id": str(uuid4()), "name": "Защита ЛТД", "industry": "Строительные материалы", "size": "11-50"},
            {"id": str(uuid4()), "name": "СтройПартнёр", "industry": "Строительство", "size": "51-200"},
            {"id": str(uuid4()), "name": "МатериалыПро", "industry": "Оптовая торговля", "size": "11-50"},
        ]

        for c in companies:
            await session.run("""
                CREATE (c:Company {
                    id: $id, name: $name, industry: $industry, size: $size,
                    created_at: $now, updated_at: $now
                })
            """, **c, now=datetime.utcnow().isoformat())
        print(f"🏢 Created {len(companies)} companies")

        # Create Interests
        interests = ["Футбол", "Рыбалка", "Кнауф", "Строительство", "Инвестиции", "Путешествия"]
        for i in interests:
            await session.run("CREATE (i:Interest {name: $name})", name=i)
        print(f"⭐ Created {len(interests)} interests")

        # Create Skills
        skills = ["Продажи", "Переговоры", "Управление проектами", "Excel", "Python", "Закупки"]
        for s in skills:
            await session.run("CREATE (s:Skill {name: $name})", name=s)
        print(f"🎯 Created {len(skills)} skills")

        # Create WORKS_AT relationships
        await session.run("""
            MATCH (p:Person {name: 'Виктор Иванов'}), (c:Company {name: 'Защита ЛТД'})
            CREATE (p)-[:WORKS_AT {role: 'CEO', since: 2018}]->(c)
        """)
        await session.run("""
            MATCH (p:Person {name: 'Артём Петров'}), (c:Company {name: 'Защита ЛТД'})
            CREATE (p)-[:WORKS_AT {role: 'CTO', since: 2020}]->(c)
        """)
        await session.run("""
            MATCH (p:Person {name: 'Мария Сидорова'}), (c:Company {name: 'СтройПартнёр'})
            CREATE (p)-[:WORKS_AT {role: 'Менеджер по закупкам', since: 2019}]->(c)
        """)
        await session.run("""
            MATCH (p:Person {name: 'Иван Козлов'}), (c:Company {name: 'МатериалыПро'})
            CREATE (p)-[:WORKS_AT {role: 'Директор', since: 2015}]->(c)
        """)
        print("🔗 Created WORKS_AT relationships")

        # Create KNOWS relationships
        await session.run("""
            MATCH (p1:Person {name: 'Виктор Иванов'}), (p2:Person {name: 'Артём Петров'})
            CREATE (p1)-[:KNOWS {strength: 0.9, context: 'work'}]->(p2)
        """)
        await session.run("""
            MATCH (p1:Person {name: 'Виктор Иванов'}), (p2:Person {name: 'Мария Сидорова'})
            CREATE (p1)-[:KNOWS {strength: 0.7, context: 'business'}]->(p2)
        """)
        await session.run("""
            MATCH (p1:Person {name: 'Мария Сидорова'}), (p2:Person {name: 'Иван Козлов'})
            CREATE (p1)-[:KNOWS {strength: 0.8, context: 'supplier'}]->(p2)
        """)
        await session.run("""
            MATCH (p1:Person {name: 'Виктор Иванов'}), (p2:Person {name: 'Елена Новикова'})
            CREATE (p1)-[:KNOWS {strength: 0.5, context: 'client'}]->(p2)
        """)
        print("🤝 Created KNOWS relationships")

        # Create INTERESTED_IN relationships
        await session.run("""
            MATCH (p:Person {name: 'Виктор Иванов'}), (i:Interest {name: 'Футбол'})
            CREATE (p)-[:INTERESTED_IN {level: 'hobby'}]->(i)
        """)
        await session.run("""
            MATCH (p:Person {name: 'Виктор Иванов'}), (i:Interest {name: 'Кнауф'})
            CREATE (p)-[:INTERESTED_IN {level: 'professional'}]->(i)
        """)
        await session.run("""
            MATCH (p:Person {name: 'Артём Петров'}), (i:Interest {name: 'Футбол'})
            CREATE (p)-[:INTERESTED_IN {level: 'hobby'}]->(i)
        """)
        await session.run("""
            MATCH (p:Person {name: 'Мария Сидорова'}), (i:Interest {name: 'Путешествия'})
            CREATE (p)-[:INTERESTED_IN {level: 'hobby'}]->(i)
        """)
        await session.run("""
            MATCH (p:Person {name: 'Иван Козлов'}), (i:Interest {name: 'Рыбалка'})
            CREATE (p)-[:INTERESTED_IN {level: 'hobby'}]->(i)
        """)
        print("⭐ Created INTERESTED_IN relationships")

        # Create HAS_SKILL relationships
        await session.run("""
            MATCH (p:Person {name: 'Виктор Иванов'}), (s:Skill {name: 'Продажи'})
            CREATE (p)-[:HAS_SKILL {level: 'expert', years_experience: 15}]->(s)
        """)
        await session.run("""
            MATCH (p:Person {name: 'Артём Петров'}), (s:Skill {name: 'Python'})
            CREATE (p)-[:HAS_SKILL {level: 'expert', years_experience: 8}]->(s)
        """)
        await session.run("""
            MATCH (p:Person {name: 'Мария Сидорова'}), (s:Skill {name: 'Закупки'})
            CREATE (p)-[:HAS_SKILL {level: 'advanced', years_experience: 5}]->(s)
        """)
        print("🎯 Created HAS_SKILL relationships")

    await Neo4jDatabase.disconnect()
    print("\n✅ Seed data created successfully!")


if __name__ == "__main__":
    asyncio.run(seed_data())
