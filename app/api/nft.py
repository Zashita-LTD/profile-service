"""NFT API endpoints for blockchain reputation."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.blockchain import (
    ReputationContract,
    BadgeType,
    get_reputation_contract,
)

router = APIRouter(prefix="/nft", tags=["NFT"])


# ========== Pydantic Models ==========

class ReputationResponse(BaseModel):
    """Reputation data response."""
    token_id: int
    owner: str
    level: int
    deals_completed: int = Field(alias="dealsCompleted")
    skills_hash: str = Field(alias="skillsHash")
    total_volume_wei: int = Field(alias="totalVolumeWei")
    total_volume_matic: float = Field(alias="totalVolumeMatic")
    rating: float
    created_at: int = Field(alias="createdAt")
    updated_at: int = Field(alias="updatedAt")
    badges: list[str]
    
    class Config:
        populate_by_name = True


class NFTLinkResponse(BaseModel):
    """NFT link response."""
    token_id: int = Field(alias="tokenId")
    polygonscan_url: str = Field(alias="polygonscanUrl")
    opensea_url: Optional[str] = Field(default=None, alias="openseaUrl")
    
    class Config:
        populate_by_name = True


class MintRequest(BaseModel):
    """Request to mint reputation token."""
    wallet_address: str = Field(alias="walletAddress")
    level: int = 1
    skills_hash: str = Field(default="", alias="skillsHash")


class MintResponse(BaseModel):
    """Mint response."""
    token_id: int = Field(alias="tokenId")
    tx_hash: Optional[str] = Field(default=None, alias="txHash")
    polygonscan_url: str = Field(alias="polygonscanUrl")


class UpdateStatsRequest(BaseModel):
    """Request to update stats."""
    token_id: int = Field(alias="tokenId")
    new_deals: int = Field(alias="newDeals")
    volume_wei: int = Field(default=0, alias="volumeWei")


class AwardBadgeRequest(BaseModel):
    """Request to award badge."""
    token_id: int = Field(alias="tokenId")
    badge: str


# ========== Endpoints ==========

@router.get(
    "/profile/{profile_id}/reputation",
    response_model=ReputationResponse,
    summary="Get reputation data",
    description="Returns on-chain reputation data for profile",
)
async def get_profile_reputation(
    profile_id: str,
    contract: ReputationContract = Depends(get_reputation_contract),
):
    """Get reputation data for profile.
    
    Profile ID should be linked to a wallet address in database.
    For now, we assume profile_id is the wallet address.
    """
    try:
        rep = await contract.get_reputation_by_address(profile_id)
        
        if not rep:
            raise HTTPException(
                status_code=404,
                detail=f"No reputation token found for profile {profile_id}",
            )
        
        return ReputationResponse(
            token_id=rep.token_id,
            owner=rep.owner,
            level=rep.level,
            dealsCompleted=rep.deals_completed,
            skillsHash=rep.skills_hash,
            totalVolumeWei=rep.total_volume,
            totalVolumeMatic=rep.total_volume / 1e18,
            rating=rep.rating,
            createdAt=rep.created_at,
            updatedAt=rep.updated_at,
            badges=[BadgeType(b).name for b in rep.badges],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/profile/{profile_id}/nft",
    response_model=NFTLinkResponse,
    summary="Get NFT links",
    description="Returns PolygonScan and OpenSea links for reputation NFT",
)
async def get_nft_links(
    profile_id: str,
    contract: ReputationContract = Depends(get_reputation_contract),
):
    """Get links to view NFT on explorers."""
    try:
        rep = await contract.get_reputation_by_address(profile_id)
        
        if not rep:
            raise HTTPException(
                status_code=404,
                detail=f"No reputation token found for profile {profile_id}",
            )
        
        polygonscan_url = contract.get_polygonscan_url(rep.token_id)
        
        # OpenSea URL (mainnet only)
        contract_address = getattr(contract.settings, 'reputation_contract_address', '')
        opensea_url = f"https://opensea.io/assets/matic/{contract_address}/{rep.token_id}"
        
        return NFTLinkResponse(
            tokenId=rep.token_id,
            polygonscanUrl=polygonscan_url,
            openseaUrl=opensea_url,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/token/{token_id}",
    response_model=ReputationResponse,
    summary="Get reputation by token ID",
    description="Returns reputation data for specific token ID",
)
async def get_token_reputation(
    token_id: int,
    contract: ReputationContract = Depends(get_reputation_contract),
):
    """Get reputation data by token ID."""
    try:
        rep = await contract.get_reputation(token_id)
        
        if not rep:
            raise HTTPException(
                status_code=404,
                detail=f"Token {token_id} not found",
            )
        
        return ReputationResponse(
            token_id=rep.token_id,
            owner=rep.owner,
            level=rep.level,
            dealsCompleted=rep.deals_completed,
            skillsHash=rep.skills_hash,
            totalVolumeWei=rep.total_volume,
            totalVolumeMatic=rep.total_volume / 1e18,
            rating=rep.rating,
            createdAt=rep.created_at,
            updatedAt=rep.updated_at,
            badges=[BadgeType(b).name for b in rep.badges],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/mint",
    response_model=MintResponse,
    summary="Mint reputation token",
    description="Mints a new SBT for wallet address",
)
async def mint_reputation(
    request: MintRequest,
    contract: ReputationContract = Depends(get_reputation_contract),
):
    """Mint new reputation token.
    
    Requires deployer private key to be configured.
    """
    try:
        token_id = await contract.mint_reputation(
            user_address=request.wallet_address,
            level=request.level,
            skills_hash=request.skills_hash,
        )
        
        polygonscan_url = contract.get_polygonscan_url(token_id)
        
        return MintResponse(
            tokenId=token_id,
            polygonscanUrl=polygonscan_url,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/update-stats",
    summary="Update reputation stats",
    description="Updates deals and volume for token",
)
async def update_stats(
    request: UpdateStatsRequest,
    contract: ReputationContract = Depends(get_reputation_contract),
):
    """Update reputation stats after deal completion."""
    try:
        tx_hash = await contract.update_stats(
            token_id=request.token_id,
            new_deals=request.new_deals,
            volume=request.volume_wei,
        )
        
        return {"txHash": tx_hash, "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/award-badge",
    summary="Award badge to token",
    description="Awards a badge to reputation token",
)
async def award_badge(
    request: AwardBadgeRequest,
    contract: ReputationContract = Depends(get_reputation_contract),
):
    """Award badge to reputation token."""
    try:
        # Convert badge name to enum
        try:
            badge = BadgeType[request.badge]
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid badge type. Valid: {[b.name for b in BadgeType]}",
            )
        
        tx_hash = await contract.award_badge(
            token_id=request.token_id,
            badge=badge,
        )
        
        return {"txHash": tx_hash, "success": True, "badge": badge.name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/badges",
    summary="List all badge types",
    description="Returns all available badge types",
)
async def list_badges():
    """List all available badge types."""
    return {
        "badges": [
            {
                "id": b.value,
                "name": b.name,
                "description": _get_badge_description(b),
            }
            for b in BadgeType
            if b != BadgeType.NONE
        ]
    }


def _get_badge_description(badge: BadgeType) -> str:
    """Get Russian description for badge."""
    descriptions = {
        BadgeType.ON_TIME_DELIVERY: "Сдал объект в срок",
        BadgeType.PAYMENT_RELIABILITY: "Оплатил 100 счетов без задержек",
        BadgeType.TOP_SUPPLIER: "Топ поставщик месяца",
        BadgeType.VERIFIED_COMPANY: "Верифицированная компания",
        BadgeType.QUALITY_MASTER: "Мастер качества",
        BadgeType.FAST_RESPONDER: "Быстрый ответ",
    }
    return descriptions.get(badge, "")
