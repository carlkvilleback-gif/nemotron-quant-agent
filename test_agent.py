import json

from agent import benchmark, extract_code, parse_result, readable, run_backtest, sanity_problems

good = {"traded_ticker": "GC=F", "total_return": 0.6, "buy_and_hold_return": 262.3, "spy_same_days_return": 0.2,
        "spy_random_days_return": 0.15, "time_in_market": 0.12, "sharpe": 0.7, "max_drawdown": -0.1, "n_trades": 316}
assert "traded_ticker" in sanity_problems({**good, "traded_ticker": None})

# trading SPY itself: same-days SPY is the strategy, so compare with average SPY days instead
assert benchmark(good) == ("S&P 500, same days", 0.2)
assert benchmark({**good, "traded_ticker": "spy"}) == ("S&P 500, average days", 0.15)
assert "time_in_market" in sanity_problems({**good, "time_in_market": 45})  # percent instead of fraction
assert sanity_problems(good) is None
assert "100%" in sanity_problems({**good, "total_return": -515.6})
assert "max_drawdown" in sanity_problems({**good, "max_drawdown": 91.9})
assert "missing" in sanity_problems({"sharpe": 1})
assert sanity_problems({"unsupported": "needs EV/EBIT history"}) is None
assert "+26230.0%" in readable(good)

assert extract_code("text\n```python\nprint(1)\n```\nmore") == "print(1)\n"
assert extract_code("no code here") is None

assert parse_result('noise\nRESULT {"sharpe": 1.5}\n') == {"sharpe": 1.5}
assert parse_result("no result line") is None

# a crashing script must come back as an error, not a result
result, error = run_backtest("raise ValueError('boom')")
assert result is None and "boom" in error

result, error = run_backtest(f"print('RESULT {json.dumps(good)}')")
assert result == good and error is None

# a script that runs but reports impossible numbers is treated as a bug
result, error = run_backtest(f"print('RESULT {json.dumps({**good, 'max_drawdown': 91.9})}')")
assert result is None and "impossible" in error

# equity curve: daily rows become weekly points, a missing file means no chart
from pathlib import Path
import tempfile
from agent import load_equity

with tempfile.TemporaryDirectory() as tmp:
    csv = Path(tmp) / "equity.csv"
    csv.write_text("date,strategy,spy\n2024-01-01,1.0,1.0\n2024-01-02,1.1,1.01\n2024-01-09,1.2,1.02\n")
    eq = load_equity(csv)
    assert eq["date"] == ["2024-01-07", "2024-01-14"] and eq["strategy"] == [1.1, 1.2]
    assert load_equity(Path(tmp) / "missing.csv") is None

# robustness: an edge must survive both halves, costs and most rule tweaks
from agent import robust_problems, robust_verdict

robust = {"first_half_edge": 0.1, "second_half_edge": 0.2, "cost_edge": 0.05,
          "variants": [{"label": "a", "edge": 0.1}, {"label": "b", "edge": 0.2}, {"label": "c", "edge": -0.1}]}
assert robust_problems(robust) is None and robust_verdict(robust) == "Robust"
assert robust_verdict({**robust, "second_half_edge": -0.01}) == "Fragile"  # only worked in the first half
assert robust_verdict({**robust, "variants": [{"label": "a", "edge": 0.1}, {"label": "b", "edge": -0.1}]}) == "Fragile"
assert robust_problems({**robust, "variants": [{"label": "a"}]}) is not None
assert robust_problems({"unsupported": "x"}) is not None
assert "Verdict: Robust" in readable(good, {**robust, "verdict": "Robust"})

# memory: past reports become a list the idea prompt can avoid repeating
from agent import past_ideas

with tempfile.TemporaryDirectory() as tmp:
    assert past_ideas(Path(tmp)) == "- none yet"
    report = {"hypothesis": "Buy gold when the dollar falls", "explanation": "... Verdict: **Weak**.",
              "robustness": {"verdict": "Fragile"}}
    (Path(tmp) / "2026-01-01_000000.json").write_text(json.dumps(report), encoding="utf-8")
    assert past_ideas(Path(tmp)) == "- Buy gold when the dollar falls -> Weak, Fragile"

print("all tests passed")
