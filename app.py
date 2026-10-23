import json
from datetime import datetime, timezone

import openai
import pandas as pd
import streamlit as st

from agent import COST_PER_TRADE, MIN_TRADES, REPORTS_DIR, benchmark, make_client, run, verdict_word, with_cost

# shortcut: counts today's reports on disk, so it resets if the host wipes the disk; enough to stop a public demo
# from draining the API credits, swap for a real per-user limit if this ever gets real traffic
MAX_RUNS_PER_DAY = 20  # a run costs a few cents; this caps a public demo at well under $1 a day

EXAMPLES = {
    "Dip buying (RSI-2)": "Buy SPY when its 2-day RSI closes below 10 and SPY is above its 200-day moving average; "
                          "sell when SPY closes above its 5-day moving average",
    "Micron overnight": "Overnight effect: buy Micron (MU) at every close and sell at the next day's open, every trading day",
    "QQQ in a panic": "Buy QQQ when VIX (^VIX) closes above 30, sell after 10 trading days",
    "Today's news": "",
}

st.set_page_config(page_title="Nemotron Quant Researcher", page_icon="📈")
st.title("📈 Nemotron Quant Researcher")
st.caption(
    "An agent that reads today's market news, turns it into a trading hypothesis, "
    "writes and runs its own backtest, fixes its own bugs, and explains the result. "
    "Powered by NVIDIA Nemotron on Nebius Token Factory and Tavily search. Historical results only, not financial advice."
)

st.write("**Try an example**, or write your own idea below:")
for col, (label, text) in zip(st.columns(len(EXAMPLES)), EXAMPLES.items()):
    col.button(label, on_click=lambda t=text: st.session_state.update(hypothesis=t), use_container_width=True)

with st.form("ask"):
    hypothesis = st.text_input("Your hypothesis (leave empty to let the agent find one in today's news)", key="hypothesis")
    if st.form_submit_button("Run research"):
        runs_today = len(list(REPORTS_DIR.glob(f"{datetime.now(timezone.utc):%Y-%m-%d}_*.json")))
        if runs_today >= MAX_RUNS_PER_DAY:
            st.warning(f"The demo is limited to {MAX_RUNS_PER_DAY} runs per day to protect its API credits. Try again tomorrow.")
        else:
            try:
                with st.spinner("Researching... this takes 1-3 minutes"):
                    run(make_client(), hypothesis)
            except openai.APIStatusError as e:
                if e.status_code != 402:
                    raise
                st.warning(
                    "The demo's API account is paused right now, so new research is on hold. "
                    "Every report below was produced by the agent earlier and is shown unchanged."
                )


def show(report, cost):
    st.subheader(report["hypothesis"])
    st.caption(report["date"])
    for bug in report.get("reviewer_caught") or []:
        st.info(f"🔍 **The reviewer agent caught a bug before the code ran**, and the coder fixed it: {bug}")
    result = report["result"]
    if result:
        strategy = with_cost(result, cost)
        cols = st.columns(3)
        cols[0].metric("Strategy", f"{strategy:+.0%}")
        if "spy_random_days_return" in result:  # older reports predate the fair benchmark
            label, bench = benchmark(result)
            cols[1].metric(label, f"{bench:+.0%}", f"{strategy - bench:+.0%} vs S&P")
            cols[2].metric("Time in market", f"{result['time_in_market']:.0%}")
        cols = st.columns(3)
        cols[0].metric("Buy & hold", f"{result['buy_and_hold_return']:+.0%}")
        cols[1].metric("Max drawdown", f"{result['max_drawdown']:.0%}")
        cols[2].metric("Trades", result["n_trades"])
        if result["n_trades"] < MIN_TRADES:
            st.warning(f"Only {result['n_trades']} trades: far too few to tell skill from luck.")
    if report.get("equity"):  # older reports have no curve
        eq = report["equity"]
        st.line_chart(
            pd.DataFrame({"Strategy": eq["strategy"], "S&P 500 (buy & hold)": eq["spy"]}, index=pd.to_datetime(eq["date"])),
            y_label=f"Growth of $1 (at {COST_PER_TRADE:.1%} cost per trade)",
            color=["#76B900", "#888888"],  # Strategy NVIDIA green, S&P grey
        )
    rob = report.get("robustness")
    if rob:
        icon = "✅" if rob["verdict"] == "Robust" else "⚠️"
        st.markdown(f"**{icon} Robustness check: {rob['verdict']}** · edge vs S&P on the same days")
        checks = [("2015–2020", rob["first_half_edge"]), ("2021–today", rob["second_half_edge"]),
                  ("Doubled 0.2% trading costs", rob["cost_edge"])] + [(v["label"], v["edge"]) for v in rob["variants"]]
        st.dataframe(
            pd.DataFrame(checks, columns=["Test", "Edge"]), hide_index=True,
            column_config={"Edge": st.column_config.NumberColumn(format="percent")},
        )
    if result and cost != COST_PER_TRADE:
        st.caption(f"The numbers above use your {cost:.2%} cost per trade; the chart and the text below were made at {COST_PER_TRADE:.1%}.")
    st.write(report["explanation"])
    if report["sources"]:
        st.markdown("**Inspired by:** " + " · ".join(f"[{s['title']}]({s['url']})" for s in report["sources"]))
    with st.expander("Code the agent wrote"):
        st.code(report["code"], language="python")
    st.divider()


def leaderboard(reports, cost):
    rows = [
        {
            "Hypothesis": r["hypothesis"],
            "Edge vs S&P": with_cost(r["result"], cost) - benchmark(r["result"])[1],
            "Strategy": with_cost(r["result"], cost),
            "Time in market": r["result"]["time_in_market"],
            "Robustness": (r.get("robustness") or {}).get("verdict", "–"),  # only run when the idea beat the S&P
            "Verdict": verdict_word(r),
        }
        for r in reports
        if r["result"] and "spy_random_days_return" in r["result"]  # older reports predate the fair benchmark
    ]
    if not rows:
        return
    st.header("🏆 Leaderboard")
    st.caption("Every idea the agent has tested, ranked by how much it beat the S&P 500 on the days it was invested (or average S&P days when the idea trades SPY itself). Returns use the trading cost chosen above.")
    percent = st.column_config.NumberColumn(format="percent")
    st.dataframe(
        pd.DataFrame(rows).sort_values("Edge vs S&P", ascending=False),
        hide_index=True,
        column_config={"Edge vs S&P": percent, "Strategy": percent, "Time in market": percent},
    )
    st.header("📄 Reports")


reports = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(REPORTS_DIR.glob("*.json"), reverse=True)] if REPORTS_DIR.exists() else []
if not reports:
    st.info("No research yet. Press Run research.")
cost = st.slider(
    "Trading cost per trade (%) · 0.1 is a realistic default", 0.0, 0.5, COST_PER_TRADE * 100, 0.05,
    help="What you pay your broker each time you buy and sell: commission, spread and currency exchange. "
         "Moving it does not cost anything or call the AI; it only shows what the results would be at that cost. "
         "0 is theory, about 0.1 is a cheap broker on a big ETF, 0.2-0.5 is common for a Swedish broker trading US stocks.",
) / 100
leaderboard(reports, cost)
for report in reports:
    show(report, cost)
