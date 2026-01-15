"""API routers."""

from .persons import router as persons_router
from .companies import router as companies_router
from .relationships import router as relationships_router
from .graph import router as graph_router

__all__ = [
    "persons_router",
    "companies_router",
    "relationships_router",
    "graph_router",
]
