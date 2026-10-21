import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from agent import REPORTS_DIR, make_client, run

# shortcut: counts today's reports on disk, so it resets if the host wipes the disk; enough to stop a public demo
# from draining the API credits, swap for a real per-user limit if this ever gets real traffic
MAX_RUNS_PER_DAY = 20

st.set_page_config(page_title="Nemotron Quant Researcher", page_icon="📈")
st.title("📈 Nemotron Quant Researcher")
st.caption(
    "An agent that reads today's market news, turns it into a trading hypothesis, "
    "writes and runs its own backtest, fixes its own bugs, and explains the result. "
    "Powered by NVIDIA Nemotron on Nebius Token Factory and Tavily search. Historical results only, not financial advice."
)

with st.form("ask"):
    hypothesis = st.text_input("Your hypothesis (leave empty to let the agent find one in today's news)")
    if st.form_submit_button("Run research"):
        runs_today = len(list(REPORTS_DIR.glob(f"{datetime.now(timezone.utc):%Y-%m-%d}_*.json")))
        if runs_today >= MAX_RUNS_PER_DAY:
            st.warning(f"The demo is limited to {MAX_RUNS_PER_DAY} runs per day to protect its API credits. Try again tomorrow.")
        else:
            with st.spinner("Researching... this takes 1-3 minutes"):
                run(make_client(), hypothesis)


def show(report):
    st.subheader(report["hypothesis"])
    st.caption(report["date"])
    result = report["result"]
    if result:
        cols = st.columns(3)
        cols[0].metric("Strategy", f"{result['total_return']:+.0%}")
        if "spy_same_days_return" in result:  # older reports predate this metric
            beat = result["total_return"] - result["spy_same_days_return"]
            cols[1].metric("S&P 500, same days", f"{result['spy_same_days_return']:+.0%}", f"{beat:+.0%} vs S&P")
            cols[2].metric("Time in market", f"{result['time_in_market']:.0%}")
        cols = st.columns(3)
        cols[0].metric("Buy & hold", f"{result['buy_and_hold_return']:+.0%}")
        cols[1].metric("Max drawdown", f"{result['max_drawdown']:.0%}")
        cols[2].metric("Trades", result["n_trades"])
    if report.get("equity"):  # older reports have no curve
        eq = report["equity"]
        st.line_chart(
            pd.DataFrame({"Strategy": eq["strategy"], "S&P 500 (buy & hold)": eq["spy"]}, index=pd.to_datetime(eq["date"])),
            y_label="Growth of $1",
            color=["#76B900", "#888888"],  # Strategy NVIDIA green, S&P grey
        )
    st.write(report["explanation"])
    if report["sources"]:
        st.markdown("**Inspired by:** " + " · ".join(f"[{s['title']}]({s['url']})" for s in report["sources"]))
    with st.expander("Code the agent wrote"):
        st.code(report["code"], language="python")
    st.divider()


reports = sorted(REPORTS_DIR.glob("*.json"), reverse=True) if REPORTS_DIR.exists() else []
if not reports:
    st.info("No research yet. Press Run research.")
for path in reports:
    show(json.loads(path.read_text(encoding="utf-8")))
