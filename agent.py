import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient

sys.stdout.reconfigure(encoding="utf-8")  # Windows console chokes on model output like "≥" or " "

CODER = "nvidia/Nemotron-3-Ultra-550b-a55b"  # big reasoning model: writes and fixes code
WRITER = "nvidia/nemotron-3-super-120b-a12b"  # faster model: explains the result
MAX_ATTEMPTS = 3
BACKTEST_FILE = Path("generated/backtest.py")
REPORTS_DIR = Path("reports")

IDEA = """Here are today's market news headlines:
{headlines}

Based on these, propose ONE trading hypothesis that can be backtested on daily price data since 2015.
- Use only tickers that exist on Yahoo Finance (for example GC=F, CL=F, SPY, TLT, BTC-USD, DX-Y.NYB, ^VIX).
- State the exact entry rule, exit rule and the ticker traded.
- Reply with only the hypothesis in one or two sentences, nothing else."""

PROMPT = """Write a complete Python script that backtests this trading hypothesis:
{hypothesis}

Rules:
- Use only yfinance, pandas and numpy.
- Download daily data from 2015-01-01 to today with yf.download(ticker, start=..., auto_adjust=True, progress=False).
  yfinance may return MultiIndex columns, so take the close with df["Close"].squeeze().
- If the hypothesis needs data that yfinance price history cannot give (historical fundamentals like EV/EBIT,
  insider trades, earnings surprises), do NOT invent or approximate it. Instead the script must only do
  print('RESULT {{"unsupported": "<one sentence on which data is missing>"}}').
- Execution convention (always use it so the same idea gives the same answer): the signal is computed
  from day T's close, the trade is entered at day T's close, and you earn close-to-close returns from T+1.
  In pandas: position = signal.shift(1). Unless the hypothesis says otherwise, "sell next day" means exit at the T+1 close.
- Never use information from day T+1 to decide a trade on day T (no look-ahead bias).
- Compare the strategy against simply buying and holding the traded asset over the same period.
- Also download SPY and compute spy_same_days_return: the compounded SPY return over only the days
  the strategy held a position (traders only use a strategy while it is active, so this is the fair benchmark).
- time_in_market is the fraction of days the strategy held a position (0 to 1).
- At the end print exactly one line starting with RESULT followed by JSON with the keys
  total_return, buy_and_hold_return, spy_same_days_return, time_in_market, sharpe, max_drawdown, n_trades.
- Reply with only the code in a single ```python block."""

EXPLAIN = """A trader tested this hypothesis on daily data since 2015:
{hypothesis}

Backtest result:
{result}

In 3-4 plain English sentences: what happened historically, whether it beat the S&P 500 over the same
active days (the fair comparison, since a trader runs other strategies the rest of the time), how it compares
with just buying and holding, how risky it was, and a one-word verdict (Promising / Mixed / Weak). Be honest and modest, no hype."""


def find_hypothesis(client):
    news = TavilyClient(os.environ["TAVILY_API_KEY"]).search(
        "biggest financial market moves and macro news today", topic="news", days=1, max_results=5,
    )
    sources = [{"title": r["title"], "url": r["url"]} for r in news["results"]]
    headlines = "\n".join(f"- {r['title']}: {r['content'][:300]}" for r in news["results"])
    answer = client.chat.completions.create(
        model=WRITER, messages=[{"role": "user", "content": IDEA.format(headlines=headlines)}],
    ).choices[0].message.content
    return answer.strip(), sources


def save_report(report):
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"{datetime.now(timezone.utc):%Y-%m-%d_%H%M%S}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def extract_code(answer):
    match = re.search(r"```python\n(.*?)```", answer, re.DOTALL)
    return match.group(1) if match else None


def parse_result(output):
    for line in output.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[len("RESULT "):])
    return None


def sanity_problems(result):
    """Code that runs can still be wrong; catch numbers that cannot be true."""
    if "unsupported" in result:
        return None
    keys = ["total_return", "buy_and_hold_return", "spy_same_days_return", "time_in_market",
            "sharpe", "max_drawdown", "n_trades"]
    missing = [k for k in keys if not isinstance(result.get(k), (int, float))]
    if missing:
        return f"RESULT is missing numeric values for: {missing}"
    problems = []
    if result["total_return"] < -1:
        problems.append(f"total_return is {result['total_return']}, but you cannot lose more than 100% (-1.0)")
    if not -1 <= result["max_drawdown"] <= 0:
        problems.append(f"max_drawdown is {result['max_drawdown']}, but it must be between -1.0 and 0")
    if not 0 < result["time_in_market"] <= 1:
        problems.append(f"time_in_market is {result['time_in_market']}, but it must be a fraction between 0 and 1")
    if result["n_trades"] < 1:
        problems.append("n_trades is 0, so the entry rule never triggered")
    return "; ".join(problems) or None


def run_backtest(code):
    BACKTEST_FILE.parent.mkdir(exist_ok=True)
    BACKTEST_FILE.write_text(code, encoding="utf-8")
    # shortcut: the generated code runs in a plain subprocess, not a real sandbox; fine for a local demo,
    # move to Nebius Serverless Jobs before letting strangers submit hypotheses
    env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}  # generated code never sees keys
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.run(
            [sys.executable, str(BACKTEST_FILE)],
            capture_output=True, text=True, encoding="utf-8", timeout=120, env=env,
        )
    except subprocess.TimeoutExpired:
        return None, "The script took longer than 120 seconds and was stopped."
    result = parse_result(proc.stdout)
    if result is None:
        return None, (proc.stderr or proc.stdout)[-3000:] or "The script printed no RESULT line."
    problems = sanity_problems(result)
    if problems:
        return None, f"The script ran but the numbers are impossible, so the backtest logic has a bug: {problems}"
    return result, None


def research(client, hypothesis):
    messages = [{"role": "user", "content": PROMPT.format(hypothesis=hypothesis)}]
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"[{attempt}/{MAX_ATTEMPTS}] Nemotron is writing the backtest...")
        answer = client.chat.completions.create(model=CODER, messages=messages).choices[0].message.content
        messages.append({"role": "assistant", "content": answer})

        code = extract_code(answer)
        if code is None:
            error = "Your reply had no ```python code block."
        else:
            print(f"[{attempt}/{MAX_ATTEMPTS}] Running it...")
            result, error = run_backtest(code)
            if result is not None:
                return result

        print(f"[{attempt}/{MAX_ATTEMPTS}] It failed, sending the error back so Nemotron can fix it.")
        messages.append({"role": "user", "content": f"That failed with this error:\n{error}\n\nFix it and reply with the full corrected script."})
    return None


def readable(result):
    # the model misreads raw fractions (262.3 read as +262%), so hand it percentages
    return (
        f"Strategy total return: {result['total_return']:+.1%}\n"
        f"Buy-and-hold total return: {result['buy_and_hold_return']:+.1%}\n"
        f"Time in market: {result['time_in_market']:.0%} of days\n"
        f"S&P 500 (SPY) return over only the days the strategy was active: {result['spy_same_days_return']:+.1%}\n"
        f"Sharpe ratio: {result['sharpe']:.2f}\n"
        f"Max drawdown: {result['max_drawdown']:.1%}\n"
        f"Number of trades: {result['n_trades']}"
    )


def make_client():
    load_dotenv()
    return OpenAI(base_url="https://api.tokenfactory.nebius.com/v1/", api_key=os.environ["NEBIUS_API_KEY"])


def run(client, hypothesis=None):
    """Full research cycle. Without a hypothesis the agent finds one in today's news."""
    sources = []
    if not hypothesis:
        print("Reading today's market news with Tavily...")
        hypothesis, sources = find_hypothesis(client)
    print(f"Hypothesis: {hypothesis}\n")

    result = research(client, hypothesis)
    if result is None:
        explanation = f"The agent could not get a working backtest after {MAX_ATTEMPTS} attempts."
    elif "unsupported" in result:
        explanation = f"Not testable with free daily price data: {result['unsupported']}"
        result = None
    else:
        print(f"\nNumbers: {json.dumps(result)}\n")
        explanation = client.chat.completions.create(
            model=WRITER,
            messages=[{"role": "user", "content": EXPLAIN.format(hypothesis=hypothesis, result=readable(result))}],
        ).choices[0].message.content
    print(explanation)

    report = {
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": hypothesis,
        "sources": sources,
        "result": result,
        "explanation": explanation,
        "code": BACKTEST_FILE.read_text(encoding="utf-8") if BACKTEST_FILE.exists() else "",
    }
    print(f"\nSaved {save_report(report)}")
    return report


def main():
    run(make_client(), " ".join(sys.argv[1:]))


if __name__ == "__main__":
    main()
