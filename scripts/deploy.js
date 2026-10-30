// Deploys MockToken + SimpleVault to BSC testnet (chain id 97) and prints the addresses.
const { ethers, network } = require("hardhat");

async function main() {
  if (!["bscTestnet", "localhost", "hardhat"].includes(network.name)) {
    throw new Error("Refusing to deploy: this project is testnet/local only.");
  }
  const [deployer] = await ethers.getSigners();
  console.log("Deployer:", deployer.address);

  const token = await (await ethers.getContractFactory("MockToken")).deploy();
  await token.waitForDeployment();

  const cap = ethers.parseUnits("100000", 18);
  const vault = await (await ethers.getContractFactory("SimpleVault")).deploy(
    await token.getAddress(), "Simple Vault mUSD", "svmUSD", cap, deployer.address
  );
  await vault.waitForDeployment();

  console.log("MockToken:  ", await token.getAddress());
  console.log("SimpleVault:", await vault.getAddress());
  console.log("Deploy block:", (await vault.deploymentTransaction().wait()).blockNumber);
}

main().catch((e) => { console.error(e); process.exit(1); });
