const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("SimpleVault", () => {
  const E = (n) => ethers.parseUnits(String(n), 18);
  let owner, alice, bob, token, vault;

  beforeEach(async () => {
    [owner, alice, bob] = await ethers.getSigners();
    token = await (await ethers.getContractFactory("MockToken")).deploy();
    vault = await (await ethers.getContractFactory("SimpleVault")).deploy(
      await token.getAddress(), "Simple Vault", "sv", E(1000), owner.address
    );
    for (const u of [alice, bob]) {
      await token.mint(u.address, E(10000));
      await token.connect(u).approve(await vault.getAddress(), ethers.MaxUint256);
    }
  });

  it("deposits and redeems 1:1 at the start", async () => {
    await vault.connect(alice).deposit(E(100), alice.address);
    expect(await vault.totalAssets()).to.equal(E(100));
    const shares = await vault.balanceOf(alice.address);
    await vault.connect(alice).redeem(shares, alice.address, alice.address);
    expect(await token.balanceOf(alice.address)).to.be.closeTo(E(10000), 1000n);
  });

  it("emits the Deposit event the monitor listens to", async () => {
    await expect(vault.connect(alice).deposit(E(5), alice.address)).to.emit(vault, "Deposit");
  });

  it("enforces the deposit cap", async () => {
    await vault.connect(alice).deposit(E(900), alice.address);
    expect(await vault.maxDeposit(bob.address)).to.equal(E(100));
    await expect(vault.connect(bob).deposit(E(101), bob.address))
      .to.be.revertedWithCustomError(vault, "ERC4626ExceededMaxDeposit");
    await vault.connect(bob).deposit(E(100), bob.address);
    expect(await vault.maxDeposit(bob.address)).to.equal(0);
  });

  it("owner can raise the cap, others cannot", async () => {
    await expect(vault.connect(alice).setDepositCap(E(5000)))
      .to.be.revertedWithCustomError(vault, "OwnableUnauthorizedAccount");
    await expect(vault.setDepositCap(E(5000))).to.emit(vault, "DepositCapUpdated").withArgs(E(1000), E(5000));
    expect(await vault.maxDeposit(alice.address)).to.equal(E(5000));
  });

  it("pause blocks deposits but never withdrawals", async () => {
    await vault.connect(alice).deposit(E(100), alice.address);
    await vault.pause();
    expect(await vault.maxDeposit(alice.address)).to.equal(0);
    await expect(vault.connect(bob).deposit(E(1), bob.address)).to.be.reverted;
    const shares = await vault.balanceOf(alice.address);
    await expect(vault.connect(alice).redeem(shares, alice.address, alice.address)).to.not.be.reverted;
    await vault.unpause();
    await vault.connect(bob).deposit(E(1), bob.address);
  });

  it("share price rises when assets are donated (simulated yield)", async () => {
    await vault.connect(alice).deposit(E(100), alice.address);
    await token.mint(await vault.getAddress(), E(10)); // +10% yield
    const shares = await vault.balanceOf(alice.address);
    const assets = await vault.convertToAssets(shares);
    expect(assets).to.be.closeTo(E(110), E(1) / 100n);
  });

  it("resists the first-depositor inflation attack", async () => {
    // attacker deposits 1 wei, then donates a lot to skew the share price
    await vault.connect(alice).deposit(1n, alice.address);
    await token.connect(alice).transfer(await vault.getAddress(), E(500));
    // victim deposits; with virtual shares they must still receive a non-zero, fair share
    await vault.connect(bob).deposit(E(400), bob.address);
    const bobAssets = await vault.convertToAssets(await vault.balanceOf(bob.address));
    expect(bobAssets).to.be.gt(E(390)); // loses well under 3%
  });
});
