const { ethers } = require("hardhat");

async function main() {
  console.log("🚀 Deploying BuilderReputation contract...");

  const [deployer] = await ethers.getSigners();
  console.log("📍 Deployer address:", deployer.address);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log("💰 Deployer balance:", ethers.formatEther(balance), "MATIC");

  // Deploy contract
  const BuilderReputation = await ethers.getContractFactory("BuilderReputation");
  const contract = await BuilderReputation.deploy();
  
  await contract.waitForDeployment();
  const contractAddress = await contract.getAddress();

  console.log("✅ BuilderReputation deployed to:", contractAddress);
  console.log("");
  console.log("📝 Save this address in your .env file:");
  console.log(`   REPUTATION_CONTRACT_ADDRESS=${contractAddress}`);
  console.log("");
  console.log("🔍 Verify on PolygonScan:");
  console.log(`   npx hardhat verify --network polygon ${contractAddress}`);
  
  return contractAddress;
}

main()
  .then((address) => {
    console.log("\n🎉 Deployment successful!");
    process.exit(0);
  })
  .catch((error) => {
    console.error("❌ Deployment failed:", error);
    process.exit(1);
  });
