"""GraphQL API."""

from app.api.graphql.schema import schema, graphql_router
from app.api.graphql.types import PersonType, CompanyType, SkillType
from app.api.graphql.resolvers import Query, Mutation

__all__ = [
    "schema",
    "graphql_router",
    "PersonType",
    "CompanyType",
    "SkillType",
    "Query",
    "Mutation",
]
