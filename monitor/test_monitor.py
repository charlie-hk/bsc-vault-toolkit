from vault_monitor import describe_event, is_large, share_price, trim


def test_large_by_absolute_amount():
    assert is_large(1500, tvl=1_000_000, min_assets=1000, min_pct=20)


def test_large_by_share_of_tvl():
    assert is_large(250, tvl=1000, min_assets=1000, min_pct=20)


def test_small_event_is_ignored():
    assert not is_large(10, tvl=1000, min_assets=1000, min_pct=20)


def test_empty_vault_never_triggers_pct_rule():
    assert not is_large(5, tvl=0, min_assets=1000, min_pct=20)


def test_share_price_starts_at_one():
    assert share_price(0, 0, 21) == 1.0
    # 100 assets minted 100*10^3 shares at the 3-decimal offset -> price 1.0
    assert abs(share_price(100 * 10**18, 100 * 10**21, 21) - 1.0) < 1e-9


def test_share_price_rises_with_yield():
    assert share_price(110 * 10**18, 100 * 10**21, 21) > 1.09


def test_trim_keeps_latest():
    assert trim(list(range(10)), 3) == [7, 8, 9]


def test_alert_text_contains_key_facts():
    msg = describe_event("Deposit", 12.5, 12500.0, "0x" + "ab" * 20, "0xtx", 99.0)
    assert "Deposit" in msg and "12.50" in msg and "0xabab" in msg and "99.00" in msg
