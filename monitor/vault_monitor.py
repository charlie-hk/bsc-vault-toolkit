#!/usr/bin/env python3
"""Read-only monitor for a SimpleVault (ERC-4626) on BNB Smart Chain.

* follows Deposit / Withdraw events block by block (no websockets needed)
* tracks TVL, share price, cap usage and pause state
* writes dashboard/data.json for the static dashboard
* optional Telegram alerts for large movements and pause changes

It never signs or sends a transaction. Telegram secrets come from the environment:
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (both optional).
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

VAULT_ABI = json.loads("""[
 {"type":"event","name":"Deposit","anonymous":false,"inputs":[
   {"indexed":true,"name":"sender","type":"address"},{"indexed":true,"name":"owner","type":"address"},
   {"indexed":false,"name":"assets","type":"uint256"},{"indexed":false,"name":"shares","type":"uint256"}]},
 {"type":"event","name":"Withdraw","anonymous":false,"inputs":[
   {"indexed":true,"name":"sender","type":"address"},{"indexed":true,"name":"receiver","type":"address"},
   {"indexed":true,"name":"owner","type":"address"},
   {"indexed":false,"name":"assets","type":"uint256"},{"indexed":false,"name":"shares","type":"uint256"}]},
 {"type":"function","name":"totalAssets","stateMutability":"view","inputs":[],"outputs":[{"type":"uint256"}]},
 {"type":"function","name":"totalSupply","stateMutability":"view","inputs":[],"outputs":[{"type":"uint256"}]},
 {"type":"function","name":"decimals","stateMutability":"view","inputs":[],"outputs":[{"type":"uint8"}]},
 {"type":"function","name":"depositCap","stateMutability":"view","inputs":[],"outputs":[{"type":"uint256"}]},
 {"type":"function","name":"paused","stateMutability":"view","inputs":[],"outputs":[{"type":"bool"}]},
 {"type":"function","name":"convertToAssets","stateMutability":"view","inputs":[{"type":"uint256"}],"outputs":[{"type":"uint256"}]}
]""")


# ---------- pure logic (unit-tested, no network) ----------

def is_large(assets: float, tvl: float, min_assets: float, min_pct: float) -> bool:
    """A movement is 'large' if it is big in absolute terms or relative to TVL."""
    if assets >= min_assets:
        return True
    return tvl > 0 and (assets / tvl) * 100 >= min_pct


def share_price(total_assets: int, total_supply: int, vault_decimals: int, asset_decimals: int = 18) -> float:
    """Assets per 1 whole share, adjusted for the vault's decimal offset."""
    if total_supply == 0:
        return 1.0
    return (total_assets / 10**asset_decimals) / (total_supply / 10**vault_decimals)


def describe_event(kind: str, assets: float, shares: float, who: str, tx: str, tvl_after: float) -> str:
    verb = "Deposit" if kind == "Deposit" else "Withdrawal"
    return (f"{verb}: {assets:,.2f} assets ({shares:,.2f} shares)\n"
            f"by {who[:6]}...{who[-4:]}\nTVL now {tvl_after:,.2f}\ntx {tx}")


def trim(history: list, limit: int) -> list:
    return history[-limit:]


# ---------- IO ----------

def telegram(text: str) -> None:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[alert]", text.replace("\n", " | "))
        return
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                  data={"chat_id": chat, "text": text[:4000]}, timeout=30).raise_for_status()


def run(cfg: dict) -> None:
    from web3 import Web3  # imported lazily so the unit tests need no web3

    w3 = Web3(Web3.HTTPProvider(cfg["rpc_url"], request_kwargs={"timeout": 30}))
    vault = w3.eth.contract(address=Web3.to_checksum_address(cfg["vault_address"]), abi=VAULT_ABI)
    vdec = vault.functions.decimals().call()
    out = Path(__file__).parent / cfg["output_file"]
    out.parent.mkdir(parents=True, exist_ok=True)

    state = {"events": [], "history": [], "chain_id": w3.eth.chain_id}
    if out.exists():
        try:
            state.update(json.loads(out.read_text()))
        except Exception:
            pass
    last = max(cfg.get("start_block", 0), state.get("last_block", 0) + 1)
    was_paused = None

    while True:
        try:
            head = w3.eth.block_number
            while last <= head:
                to = min(head, last + cfg["max_blocks_per_query"] - 1)
                for name in ("Deposit", "Withdraw"):
                    ev = getattr(vault.events, name)
                    for e in ev.get_logs(from_block=last, to_block=to):
                        assets = e["args"]["assets"] / 10**18
                        shares = e["args"]["shares"] / 10**vdec
                        tvl = vault.functions.totalAssets().call() / 10**18
                        who = e["args"].get("owner") or e["args"].get("sender")
                        rec = {"kind": name, "assets": assets, "shares": shares, "who": who,
                               "block": e["blockNumber"], "tx": e["transactionHash"].hex()}
                        state["events"].append(rec)
                        if is_large(assets, tvl, cfg["large_event_assets"], cfg["large_event_pct_of_tvl"]):
                            telegram(describe_event(name, assets, shares, who, rec["tx"], tvl))
                last = to + 1

            ta, ts = vault.functions.totalAssets().call(), vault.functions.totalSupply().call()
            cap, paused = vault.functions.depositCap().call(), vault.functions.paused().call()
            if was_paused is not None and paused != was_paused:
                telegram("Vault PAUSED: deposits are blocked." if paused else "Vault UNPAUSED.")
            was_paused = paused

            state["history"].append({"t": int(time.time()), "tvl": ta / 10**18,
                                     "price": share_price(ta, ts, vdec)})
            state.update({
                "history": trim(state["history"], cfg["history_points"]),
                "events": state["events"][-200:],
                "vault": cfg["vault_address"], "tvl": ta / 10**18, "cap": cap / 10**18,
                "paused": paused, "price": share_price(ta, ts, vdec),
                "last_block": head, "updated": int(time.time()),
            })
            out.write_text(json.dumps(state))
        except Exception as exc:  # RPC hiccups must not kill the loop
            print("[warn]", exc)
        time.sleep(cfg["poll_seconds"])


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    run(json.loads(Path(path).read_text()))
