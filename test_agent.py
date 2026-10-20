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

print("all tests passed")
