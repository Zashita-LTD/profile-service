"""Blockchain Module - Web3 integration for reputation SBT.

Provides:
- ReputationContract: Interface to BuilderReputation smart contract
- BlockchainWorker: Event listener for automatic NFT updates
- Custodial wallet creation for users
"""

import asyncio
import json
import logging
from typing import Optional
from pathlib import Path
from dataclasses import dataclass
from enum import IntEnum

from web3 import Web3, AsyncWeb3
from web3.middleware import geth_poa_middleware
from eth_account import Account

from app.config import get_settings

logger = logging.getLogger("blockchain")


class BadgeType(IntEnum):
    """Badge types matching Solidity enum."""
    NONE = 0
    ON_TIME_DELIVERY = 1      # "Сдал объект в срок"
    PAYMENT_RELIABILITY = 2   # "Оплатил 100 счетов без задержек"
    TOP_SUPPLIER = 3          # "Топ поставщик месяца"
    VERIFIED_COMPANY = 4      # "Верифицированная компания"
    QUALITY_MASTER = 5        # "Мастер качества"
    FAST_RESPONDER = 6        # "Быстрый ответ"


@dataclass
class ReputationData:
    """Reputation data from blockchain."""
    token_id: int
    owner: str
    level: int
    deals_completed: int
    skills_hash: str
    total_volume: int
    rating: float  # 0.2 - 10.0
    created_at: int
    updated_at: int
    badges: list[BadgeType]


# Load contract ABI
def load_contract_abi() -> dict:
    """Load BuilderReputation ABI from artifacts."""
    abi_path = Path(__file__).parent.parent / "blockchain" / "artifacts" / "contracts" / "BuilderReputation.sol" / "BuilderReputation.json"
    
    if abi_path.exists():
        with open(abi_path) as f:
            artifact = json.load(f)
            return artifact.get("abi", [])
    
    # Fallback: minimal ABI for key functions
    return [
        {
            "inputs": [{"name": "to", "type": "address"}, {"name": "level", "type": "uint256"}, {"name": "skillsHash", "type": "string"}],
            "name": "mintReputation",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"name": "tokenId", "type": "uint256"}, {"name": "newDeals", "type": "uint256"}, {"name": "volume", "type": "uint256"}],
            "name": "updateStats",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"name": "tokenId", "type": "uint256"}, {"name": "badge", "type": "uint8"}],
            "name": "awardBadge",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"name": "tokenId", "type": "uint256"}],
            "name": "getReputation",
            "outputs": [
                {"name": "level", "type": "uint256"},
                {"name": "dealsCompleted", "type": "uint256"},
                {"name": "skillsHash", "type": "string"},
                {"name": "totalVolume", "type": "uint256"},
                {"name": "rating", "type": "uint256"},
                {"name": "createdAt", "type": "uint256"},
                {"name": "updatedAt", "type": "uint256"},
                {"name": "badges", "type": "uint8[]"}
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [{"name": "owner", "type": "address"}],
            "name": "getTokenByAddress",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [{"name": "owner", "type": "address"}],
            "name": "hasReputation",
            "outputs": [{"name": "", "type": "bool"}],
            "stateMutability": "view",
            "type": "function"
        },
    ]


class ReputationContract:
    """Interface to BuilderReputation smart contract."""
    
    def __init__(self):
        self.settings = get_settings()
        self._w3: Optional[Web3] = None
        self._contract = None
        self._account = None
    
    @property
    def w3(self) -> Web3:
        """Get Web3 instance."""
        if self._w3 is None:
            rpc_url = getattr(self.settings, 'polygon_rpc_url', 'https://polygon-rpc.com')
            self._w3 = Web3(Web3.HTTPProvider(rpc_url))
            # Add PoA middleware for Polygon
            self._w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        return self._w3
    
    @property
    def contract(self):
        """Get contract instance."""
        if self._contract is None:
            contract_address = getattr(self.settings, 'reputation_contract_address', None)
            if not contract_address:
                raise ValueError("REPUTATION_CONTRACT_ADDRESS not configured")
            
            abi = load_contract_abi()
            self._contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=abi
            )
        return self._contract
    
    @property
    def account(self):
        """Get deployer/owner account."""
        if self._account is None:
            private_key = getattr(self.settings, 'deployer_private_key', None)
            if not private_key:
                raise ValueError("DEPLOYER_PRIVATE_KEY not configured")
            self._account = Account.from_key(private_key)
        return self._account
    
    async def mint_reputation(
        self,
        user_address: str,
        level: int = 1,
        skills_hash: str = "",
    ) -> int:
        """Mint a new reputation token for user.
        
        Args:
            user_address: User's wallet address
            level: Initial level (1-100)
            skills_hash: IPFS hash of skills JSON
            
        Returns:
            Token ID
        """
        logger.info(f"Minting reputation for {user_address} at level {level}")
        
        # Check if already has token
        has_token = self.contract.functions.hasReputation(
            Web3.to_checksum_address(user_address)
        ).call()
        
        if has_token:
            token_id = self.contract.functions.getTokenByAddress(
                Web3.to_checksum_address(user_address)
            ).call()
            logger.info(f"User already has token {token_id}")
            return token_id
        
        # Build transaction
        tx = self.contract.functions.mintReputation(
            Web3.to_checksum_address(user_address),
            level,
            skills_hash,
        ).build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 300000,
            'gasPrice': self.w3.eth.gas_price,
        })
        
        # Sign and send
        signed = self.w3.eth.account.sign_transaction(tx, self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        
        # Wait for receipt
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt['status'] != 1:
            raise Exception(f"Transaction failed: {tx_hash.hex()}")
        
        # Get token ID from logs
        token_id = self.contract.functions.getTokenByAddress(
            Web3.to_checksum_address(user_address)
        ).call()
        
        logger.info(f"Minted token {token_id} for {user_address}, tx: {tx_hash.hex()}")
        return token_id
    
    async def update_stats(
        self,
        token_id: int,
        new_deals: int,
        volume: int = 0,
    ) -> str:
        """Update reputation stats after completed deals.
        
        Args:
            token_id: Token to update
            new_deals: Number of new completed deals
            volume: Transaction volume in wei
            
        Returns:
            Transaction hash
        """
        logger.info(f"Updating token {token_id}: +{new_deals} deals, +{volume} volume")
        
        tx = self.contract.functions.updateStats(
            token_id,
            new_deals,
            volume,
        ).build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 100000,
            'gasPrice': self.w3.eth.gas_price,
        })
        
        signed = self.w3.eth.account.sign_transaction(tx, self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt['status'] != 1:
            raise Exception(f"Transaction failed: {tx_hash.hex()}")
        
        logger.info(f"Updated token {token_id}, tx: {tx_hash.hex()}")
        return tx_hash.hex()
    
    async def award_badge(
        self,
        token_id: int,
        badge: BadgeType,
    ) -> str:
        """Award a badge to token.
        
        Args:
            token_id: Token to award
            badge: Badge type
            
        Returns:
            Transaction hash
        """
        logger.info(f"Awarding badge {badge.name} to token {token_id}")
        
        tx = self.contract.functions.awardBadge(
            token_id,
            badge.value,
        ).build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 100000,
            'gasPrice': self.w3.eth.gas_price,
        })
        
        signed = self.w3.eth.account.sign_transaction(tx, self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt['status'] != 1:
            raise Exception(f"Transaction failed: {tx_hash.hex()}")
        
        logger.info(f"Awarded badge to token {token_id}, tx: {tx_hash.hex()}")
        return tx_hash.hex()
    
    async def get_reputation(self, token_id: int) -> Optional[ReputationData]:
        """Get reputation data for token."""
        try:
            data = self.contract.functions.getReputation(token_id).call()
            owner = self.contract.functions.ownerOf(token_id).call()
            
            return ReputationData(
                token_id=token_id,
                owner=owner,
                level=data[0],
                deals_completed=data[1],
                skills_hash=data[2],
                total_volume=data[3],
                rating=data[4] / 5.0,  # Convert 1-50 to 0.2-10.0
                created_at=data[5],
                updated_at=data[6],
                badges=[BadgeType(b) for b in data[7]],
            )
        except Exception as e:
            logger.error(f"Failed to get reputation for token {token_id}: {e}")
            return None
    
    async def get_reputation_by_address(self, address: str) -> Optional[ReputationData]:
        """Get reputation data by wallet address."""
        token_id = self.contract.functions.getTokenByAddress(
            Web3.to_checksum_address(address)
        ).call()
        
        if token_id == 0:
            return None
        
        return await self.get_reputation(token_id)
    
    def get_polygonscan_url(self, token_id: int) -> str:
        """Get PolygonScan URL for token."""
        contract_address = getattr(self.settings, 'reputation_contract_address', '')
        network = getattr(self.settings, 'polygon_network', 'polygon')
        
        if network == 'mumbai':
            base_url = "https://mumbai.polygonscan.com"
        elif network == 'amoy':
            base_url = "https://amoy.polygonscan.com"
        else:
            base_url = "https://polygonscan.com"
        
        return f"{base_url}/token/{contract_address}?a={token_id}"


class CustodialWalletManager:
    """Create and manage custodial wallets for users."""
    
    def __init__(self):
        self.settings = get_settings()
    
    def create_wallet(self) -> tuple[str, str]:
        """Create a new wallet.
        
        Returns:
            (address, private_key)
        """
        account = Account.create()
        return account.address, account.key.hex()
    
    async def store_wallet(self, user_id: str, address: str, encrypted_key: str):
        """Store encrypted wallet in database.
        
        In production, use proper key management (HSM, Vault, etc.)
        """
        # TODO: Store in secure database
        logger.info(f"Stored wallet {address} for user {user_id}")


class BlockchainWorker:
    """Event listener for automatic reputation updates."""
    
    def __init__(self):
        self.contract = ReputationContract()
        self.wallet_manager = CustodialWalletManager()
        self._running = False
    
    async def process_event(self, event: dict):
        """Process system event and update blockchain.
        
        Supported events:
        - project_completed: Update deals count
        - payment_completed: Update volume, check badges
        - user_verified: Create wallet and mint token
        """
        event_type = event.get("type")
        
        if event_type == "project_completed":
            await self._handle_project_completed(event)
        elif event_type == "payment_completed":
            await self._handle_payment_completed(event)
        elif event_type == "user_verified":
            await self._handle_user_verified(event)
        else:
            logger.debug(f"Unknown event type: {event_type}")
    
    async def _handle_project_completed(self, event: dict):
        """Handle project completion - update deals."""
        user_address = event.get("user_address")
        if not user_address:
            return
        
        rep = await self.contract.get_reputation_by_address(user_address)
        if not rep:
            logger.warning(f"No reputation token for {user_address}")
            return
        
        await self.contract.update_stats(
            token_id=rep.token_id,
            new_deals=1,
            volume=event.get("volume", 0),
        )
        
        # Check for ON_TIME_DELIVERY badge
        if event.get("on_time", False):
            if BadgeType.ON_TIME_DELIVERY not in rep.badges:
                await self.contract.award_badge(
                    rep.token_id,
                    BadgeType.ON_TIME_DELIVERY
                )
    
    async def _handle_payment_completed(self, event: dict):
        """Handle payment completion - check for badge."""
        user_address = event.get("user_address")
        if not user_address:
            return
        
        rep = await self.contract.get_reputation_by_address(user_address)
        if not rep:
            return
        
        # Update stats with payment volume
        await self.contract.update_stats(
            token_id=rep.token_id,
            new_deals=0,
            volume=event.get("amount", 0),
        )
        
        # Check for PAYMENT_RELIABILITY badge (100 payments)
        payments_count = event.get("total_payments", 0)
        if payments_count >= 100 and BadgeType.PAYMENT_RELIABILITY not in rep.badges:
            await self.contract.award_badge(
                rep.token_id,
                BadgeType.PAYMENT_RELIABILITY
            )
    
    async def _handle_user_verified(self, event: dict):
        """Handle user verification - create wallet and mint."""
        user_id = event.get("user_id")
        if not user_id:
            return
        
        # Check if user already has wallet
        existing_address = event.get("wallet_address")
        
        if not existing_address:
            # Create custodial wallet
            address, private_key = self.wallet_manager.create_wallet()
            
            # Store encrypted (in production, use proper encryption)
            await self.wallet_manager.store_wallet(
                user_id=user_id,
                address=address,
                encrypted_key=private_key,  # Should be encrypted!
            )
        else:
            address = existing_address
        
        # Mint reputation token
        skills_hash = event.get("skills_hash", "")
        await self.contract.mint_reputation(
            user_address=address,
            level=1,
            skills_hash=skills_hash,
        )
        
        # Award VERIFIED_COMPANY badge
        rep = await self.contract.get_reputation_by_address(address)
        if rep:
            await self.contract.award_badge(
                rep.token_id,
                BadgeType.VERIFIED_COMPANY
            )


# Singleton
_contract: Optional[ReputationContract] = None


def get_reputation_contract() -> ReputationContract:
    """Get reputation contract singleton."""
    global _contract
    if _contract is None:
        _contract = ReputationContract()
    return _contract
