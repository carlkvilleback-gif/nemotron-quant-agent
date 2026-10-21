import json

from agent import extract_code, parse_result, readable, run_backtest, sanity_problems

good = {"total_return": 0.6, "buy_and_hold_return": 262.3, "spy_same_days_return": 0.2, "time_in_market": 0.12,
        "sharpe": 0.7, "max_drawdown": -0.1, "n_trades": 316}
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

print("all tests passed")
