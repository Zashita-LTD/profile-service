// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Counters.sol";

/**
 * @title BuilderReputation
 * @dev Soulbound Token (SBT) for builder reputation on Polygon
 * 
 * Key features:
 * - Non-transferable (Soulbound) - tokens cannot be transferred once minted
 * - Level system (1-100) representing skill mastery
 * - Deal tracking for completed transactions
 * - Skills stored as IPFS hash
 * - Only owner (backend) can mint and update
 * 
 * @author Zashita-LTD
 */
contract BuilderReputation is ERC721, ERC721URIStorage, Ownable {
    using Counters for Counters.Counter;

    Counters.Counter private _tokenIdCounter;

    // Reputation data for each token
    struct ReputationData {
        uint256 level;           // Skill level (1-100)
        uint256 dealsCompleted;  // Number of successful deals
        string skillsHash;       // IPFS hash of skills JSON
        uint256 totalVolume;     // Total transaction volume in smallest unit
        uint256 rating;          // Average rating (1-50, representing 0.2-10.0)
        uint256 createdAt;       // Timestamp when minted
        uint256 updatedAt;       // Last update timestamp
    }

    // Badge types
    enum BadgeType {
        NONE,
        ON_TIME_DELIVERY,      // "Сдал объект в срок"
        PAYMENT_RELIABILITY,   // "Оплатил 100 счетов без задержек"
        TOP_SUPPLIER,          // "Топ поставщик месяца"
        VERIFIED_COMPANY,      // "Верифицированная компания"
        QUALITY_MASTER,        // "Мастер качества"
        FAST_RESPONDER         // "Быстрый ответ"
    }

    // Mapping from token ID to reputation data
    mapping(uint256 => ReputationData) public reputations;
    
    // Mapping from address to token ID (one token per address)
    mapping(address => uint256) public addressToTokenId;
    
    // Mapping from token ID to earned badges
    mapping(uint256 => BadgeType[]) public tokenBadges;

    // Events
    event ReputationMinted(address indexed to, uint256 indexed tokenId, uint256 level);
    event ReputationUpdated(uint256 indexed tokenId, uint256 newLevel, uint256 newDeals);
    event BadgeAwarded(uint256 indexed tokenId, BadgeType badge);
    event SkillsUpdated(uint256 indexed tokenId, string newSkillsHash);

    constructor() ERC721("Builder Reputation", "BLDR") Ownable(msg.sender) {}

    /**
     * @dev Mint a new reputation token to an address
     * @param to The address to mint to
     * @param level Initial level (1-100)
     * @param skillsHash IPFS hash of skills data
     */
    function mintReputation(
        address to,
        uint256 level,
        string memory skillsHash
    ) public onlyOwner returns (uint256) {
        require(addressToTokenId[to] == 0, "Address already has reputation token");
        require(level >= 1 && level <= 100, "Level must be 1-100");

        _tokenIdCounter.increment();
        uint256 tokenId = _tokenIdCounter.current();

        _safeMint(to, tokenId);
        
        reputations[tokenId] = ReputationData({
            level: level,
            dealsCompleted: 0,
            skillsHash: skillsHash,
            totalVolume: 0,
            rating: 25, // 5.0 default
            createdAt: block.timestamp,
            updatedAt: block.timestamp
        });

        addressToTokenId[to] = tokenId;

        emit ReputationMinted(to, tokenId, level);
        return tokenId;
    }

    /**
     * @dev Update reputation stats after completed deals
     * @param tokenId The token to update
     * @param newDeals Additional deals completed
     * @param volume Transaction volume to add
     */
    function updateStats(
        uint256 tokenId,
        uint256 newDeals,
        uint256 volume
    ) public onlyOwner {
        require(_ownerOf(tokenId) != address(0), "Token does not exist");

        ReputationData storage rep = reputations[tokenId];
        rep.dealsCompleted += newDeals;
        rep.totalVolume += volume;
        rep.updatedAt = block.timestamp;

        // Auto level-up based on deals
        uint256 newLevel = calculateLevel(rep.dealsCompleted, rep.totalVolume);
        if (newLevel > rep.level) {
            rep.level = newLevel;
        }

        emit ReputationUpdated(tokenId, rep.level, rep.dealsCompleted);
    }

    /**
     * @dev Update user's skills hash
     * @param tokenId The token to update
     * @param newSkillsHash New IPFS hash
     */
    function updateSkills(
        uint256 tokenId,
        string memory newSkillsHash
    ) public onlyOwner {
        require(_ownerOf(tokenId) != address(0), "Token does not exist");
        
        reputations[tokenId].skillsHash = newSkillsHash;
        reputations[tokenId].updatedAt = block.timestamp;

        emit SkillsUpdated(tokenId, newSkillsHash);
    }

    /**
     * @dev Award a badge to a token
     * @param tokenId The token to award
     * @param badge The badge type to award
     */
    function awardBadge(
        uint256 tokenId,
        BadgeType badge
    ) public onlyOwner {
        require(_ownerOf(tokenId) != address(0), "Token does not exist");
        require(badge != BadgeType.NONE, "Invalid badge");

        // Check if badge already awarded
        BadgeType[] storage badges = tokenBadges[tokenId];
        for (uint i = 0; i < badges.length; i++) {
            require(badges[i] != badge, "Badge already awarded");
        }

        tokenBadges[tokenId].push(badge);
        reputations[tokenId].updatedAt = block.timestamp;

        emit BadgeAwarded(tokenId, badge);
    }

    /**
     * @dev Update user's rating
     * @param tokenId The token to update
     * @param newRating New rating (1-50)
     */
    function updateRating(
        uint256 tokenId,
        uint256 newRating
    ) public onlyOwner {
        require(_ownerOf(tokenId) != address(0), "Token does not exist");
        require(newRating >= 1 && newRating <= 50, "Rating must be 1-50");

        reputations[tokenId].rating = newRating;
        reputations[tokenId].updatedAt = block.timestamp;
    }

    /**
     * @dev Calculate level based on activity
     */
    function calculateLevel(
        uint256 deals,
        uint256 volume
    ) public pure returns (uint256) {
        // Simple formula: base level from deals + bonus from volume
        uint256 dealLevel = deals / 10; // 1 level per 10 deals
        uint256 volumeBonus = volume / (1000 * 10**18); // 1 level per 1000 tokens volume
        
        uint256 level = 1 + dealLevel + volumeBonus;
        if (level > 100) level = 100;
        
        return level;
    }

    /**
     * @dev Get full reputation data
     */
    function getReputation(uint256 tokenId) public view returns (
        uint256 level,
        uint256 dealsCompleted,
        string memory skillsHash,
        uint256 totalVolume,
        uint256 rating,
        uint256 createdAt,
        uint256 updatedAt,
        BadgeType[] memory badges
    ) {
        require(_ownerOf(tokenId) != address(0), "Token does not exist");
        
        ReputationData storage rep = reputations[tokenId];
        return (
            rep.level,
            rep.dealsCompleted,
            rep.skillsHash,
            rep.totalVolume,
            rep.rating,
            rep.createdAt,
            rep.updatedAt,
            tokenBadges[tokenId]
        );
    }

    /**
     * @dev Get token ID for an address
     */
    function getTokenByAddress(address owner) public view returns (uint256) {
        return addressToTokenId[owner];
    }

    /**
     * @dev Check if address has reputation token
     */
    function hasReputation(address owner) public view returns (bool) {
        return addressToTokenId[owner] != 0;
    }

    // ============================================
    // SOULBOUND LOGIC - Disable transfers
    // ============================================

    /**
     * @dev Override transfer to make token soulbound
     */
    function _update(
        address to,
        uint256 tokenId,
        address auth
    ) internal override returns (address) {
        address from = _ownerOf(tokenId);
        
        // Allow minting (from == address(0)) and burning (to == address(0))
        // Disallow transfers
        if (from != address(0) && to != address(0)) {
            revert("Soulbound: transfer not allowed");
        }

        return super._update(to, tokenId, auth);
    }

    /**
     * @dev Disable approve for soulbound
     */
    function approve(address, uint256) public pure override {
        revert("Soulbound: approval not allowed");
    }

    /**
     * @dev Disable setApprovalForAll for soulbound
     */
    function setApprovalForAll(address, bool) public pure override {
        revert("Soulbound: approval not allowed");
    }

    // ============================================
    // ERC721URIStorage overrides
    // ============================================

    function tokenURI(uint256 tokenId)
        public
        view
        override(ERC721, ERC721URIStorage)
        returns (string memory)
    {
        return super.tokenURI(tokenId);
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721, ERC721URIStorage)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }
}
