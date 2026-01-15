"""Company API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from ..models.company import Company, CompanyCreate, CompanyUpdate, CompanyWithEmployees
from ..repositories.company_repo import CompanyRepository

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.post("", response_model=Company, status_code=201)
async def create_company(data: CompanyCreate) -> Company:
    """Create a new company."""
    return await CompanyRepository.create(data)


@router.get("", response_model=list[Company])
async def list_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[Company]:
    """List all companies with pagination."""
    return await CompanyRepository.list_all(skip=skip, limit=limit)


@router.get("/search", response_model=list[Company])
async def search_companies(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
) -> list[Company]:
    """Search companies by name."""
    return await CompanyRepository.search(q, limit=limit)


@router.get("/{company_id}", response_model=Company)
async def get_company(company_id: UUID) -> Company:
    """Get a company by ID."""
    company = await CompanyRepository.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/{company_id}/employees", response_model=CompanyWithEmployees)
async def get_company_with_employees(company_id: UUID) -> CompanyWithEmployees:
    """Get a company with all employees."""
    company = await CompanyRepository.get_with_employees(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.put("/{company_id}", response_model=Company)
async def update_company(company_id: UUID, data: CompanyUpdate) -> Company:
    """Update a company."""
    company = await CompanyRepository.update(company_id, data)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.delete("/{company_id}", status_code=204)
async def delete_company(company_id: UUID) -> None:
    """Delete a company."""
    deleted = await CompanyRepository.delete(company_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Company not found")
