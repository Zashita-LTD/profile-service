"""GraphQL schema definition."""

import strawberry
from strawberry.fastapi import GraphQLRouter

from app.api.graphql.resolvers import Query, Mutation


# Create schema
schema = strawberry.Schema(query=Query, mutation=Mutation)

# Create router for FastAPI
graphql_router = GraphQLRouter(schema)
