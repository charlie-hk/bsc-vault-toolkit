require("@nomicfoundation/hardhat-toolbox");

// Testnet only. Put the key in an environment variable, never in this file.
const { BSC_TESTNET_RPC, DEPLOYER_KEY } = process.env;

module.exports = {
  solidity: { version: "0.8.24", settings: { optimizer: { enabled: true, runs: 200 } } },
  networks: {
    bscTestnet: {
      url: BSC_TESTNET_RPC || "https://data-seed-prebsc-1-s1.bnbchain.org:8545",
      chainId: 97,
      accounts: DEPLOYER_KEY ? [DEPLOYER_KEY] : [],
    },
  },
};
