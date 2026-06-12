from agent.montecarlo import simulate_monthly_returns, summarize


def test_distribution_shape_and_floor():
    r = simulate_monthly_returns(0.10, 0.20, leverage=1.0, n_paths=20_000, seed=1)
    assert len(r) == 20_000
    assert r.min() >= -1.0                      # cannot lose more than everything
    s = summarize(r)
    assert -1.0 <= s["p5"] <= s["median"] <= s["p95"]


def test_leverage_raises_both_upside_and_ruin():
    low = summarize(simulate_monthly_returns(0.30, 0.40, leverage=2, n_paths=40_000, seed=2))
    high = summarize(simulate_monthly_returns(0.30, 0.40, leverage=15, n_paths=40_000, seed=2))
    # More leverage => more chance of doubling, but also far more chance of ruin.
    assert high["p_double"] > low["p_double"]
    assert high["p_ruin"] > low["p_ruin"]
    assert high["p_lose_half"] > low["p_lose_half"]
