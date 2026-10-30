// Generates demo activity (deposits, redeems, a simulated yield) so the monitor and
// dashboard have something to show. Local node or testnet.
//   set TOKEN=0x...   set VAULT=0x...   npm run simulate:local
const { ethers } = require("hardhat");

const E = (n) => ethers.parseUnits(String(n), 18);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const { TOKEN, VAULT } = process.env;
  if (!TOKEN || !VAULT) throw new Error("Set TOKEN and VAULT environment variables first.");

  const signers = await ethers.getSigners();
  const users = signers.slice(0, Math.min(4, signers.length));
  const token = await ethers.getContractAt("MockToken", TOKEN);
  const vault = await ethers.getContractAt("SimpleVault", VAULT);

  for (const u of users) {
    await (await token.mint(u.address, E(10000))).wait();
    await (await token.connect(u).approve(VAULT, ethers.MaxUint256)).wait();
  }

  for (let i = 0; i < 14; i++) {
    const u = users[Math.floor(Math.random() * users.length)];
    const shares = await vault.balanceOf(u.address);
    if (shares > 0n && Math.random() < 0.4) {
      const part = shares / BigInt(1 + Math.floor(Math.random() * 3));
      if (part > 0n) {
        await (await vault.connect(u).redeem(part, u.address, u.address)).wait();
        console.log("redeem", u.address.slice(0, 8));
      }
    } else {
      const amount = E(10 + Math.floor(Math.random() * 300));
      if ((await vault.maxDeposit(u.address)) >= amount) {
        await (await vault.connect(u).deposit(amount, u.address)).wait();
        console.log("deposit", u.address.slice(0, 8));
      }
    }
    await sleep(1500);
  }

  // simulated yield: send assets straight to the vault so the share price rises
  await (await token.mint(VAULT, E(5))).wait();
  console.log("done");
}

main().catch((e) => { console.error(e); process.exit(1); });
