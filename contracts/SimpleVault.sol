// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {ERC4626} from "@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/// @title SimpleVault
/// @notice ERC-4626 tokenised vault with an owner-controlled deposit cap and an
///         emergency pause. Deposits/mints stop while paused or when the cap is
///         reached; withdrawals and redeems are ALWAYS available so users can exit.
/// @dev Educational / portfolio code. Unaudited. Holds no strategy: share price only
///      moves if assets are sent to the vault directly (simulated yield in tests).
contract SimpleVault is ERC4626, Ownable, Pausable {
    /// @notice Maximum total assets the vault accepts.
    uint256 public depositCap;

    event DepositCapUpdated(uint256 oldCap, uint256 newCap);

    constructor(IERC20 asset_, string memory name_, string memory symbol_, uint256 cap_, address owner_)
        ERC20(name_, symbol_)
        ERC4626(asset_)
        Ownable(owner_)
    {
        depositCap = cap_;
        emit DepositCapUpdated(0, cap_);
    }

    function setDepositCap(uint256 newCap) external onlyOwner {
        emit DepositCapUpdated(depositCap, newCap);
        depositCap = newCap;
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    /// @dev ERC4626.deposit() reverts when assets > maxDeposit(), so this enforces cap + pause.
    function maxDeposit(address) public view override returns (uint256) {
        if (paused()) return 0;
        uint256 assets = totalAssets();
        return assets >= depositCap ? 0 : depositCap - assets;
    }

    function maxMint(address receiver) public view override returns (uint256) {
        if (paused()) return 0;
        return convertToShares(maxDeposit(receiver));
    }

    /// @dev Virtual shares make the classic first-depositor inflation attack uneconomical.
    function _decimalsOffset() internal pure override returns (uint8) {
        return 3;
    }
}
