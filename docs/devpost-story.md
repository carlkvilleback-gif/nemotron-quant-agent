## Inspiration

Every quant beginner knows the feeling. You find a trading idea, run a quick backtest, and the curve goes straight up. Then you add trading costs, test another period, or find the one line that accidentally peeks at tomorrow's prices, and the idea is gone.

We are three 18-year-old students from Sweden, and that happened to us almost every week this autumn. We realised that having ideas is the easy part. **The hard part is proving them wrong, quickly and honestly.** So we built an AI agent whose only job is exactly that.

## What it does

You give **Nemotron Quant Researcher** a trading idea in plain English, or let it find one in today's market news, and it does the whole research job on its own:

1. **Writes the backtest** in Python, on daily prices from 2015 to today.
2. **Gets a second opinion.** A reviewer agent reads the code *before* it runs and looks for bugs that would still run but give wrong numbers. In our demo it caught a strategy that held TLT for 6 days instead of 5, and the coder fixed it.
3. **Runs and fixes its own code.** Crashes and impossible results, like a loss of more than 100%, go straight back to the model, up to three attempts.
4. **Compares fairly.** It measures the strategy against the S&P 500 *on the days it was actually invested*, because a trader only runs a strategy while it is on. If the idea trades SPY itself, it compares with the same number of average S&P days instead.
5. **Counts the real costs.** You pick your own cost per trade, and every report shows exactly what costs ate.
6. **Checks for luck.** If an idea beats the S&P, the agent re-tests it on 2015–2020 and 2021–today separately, with doubled costs, and with every number in the rule moved about 20%. Only an idea that survives all of that is called **Robust**.
7. **Explains the verdict** in a few honest sentences, flags ideas with fewer than 20 trades, and refuses to invent data it does not have.
8. **Runs by itself** every weekday morning, remembers what it has already tested, and ranks every idea on a leaderboard.

What that looks like in practice:

| Idea | Looks like | After the agent is done |
|---|---|---|
| Buy Micron at the close, sell at the open | **+4,417%** before costs | **+132%** at 0.1% per trade, while just holding Micron made over 2,500% |
| Buy gold when the dollar falls 0.5% | **+60%** before costs | Loses to the S&P 500 on the same days after costs |
| Buy SPY after a short-term dip (RSI-2) | **+51%**, Sharpe 0.6 | *Fragile*: the edge disappears in 2015–2020 |

Most ideas come back *Weak*. That is the point: better to find out from an agent than from your bank account.

## How we built it

- **NVIDIA Nemotron 3 Ultra** on **Nebius Token Factory** writes and fixes the backtest code. A backtest that runs but is subtly wrong is worse than one that crashes, so this is where the big reasoning model earns its cost.
- **NVIDIA Nemotron 3 Super** turns headlines into a testable hypothesis, reviews the code as the second agent, and writes the explanation. It is fast and cheap for short text.
- **Token Factory's OpenAI-compatible API** meant the standard `openai` Python client worked by changing only `base_url`. Our first Nemotron call was ten lines.
- **Tavily** searches today's market news for new ideas.
- **Safety:** generated code runs in a separate process that never sees the API keys, with a timeout and automatic sanity checks on every result.
- **Streamlit** for the app, **yfinance** for free daily prices, **GitHub Actions** for the morning run and for keeping the demo awake.
- We used **Claude Code** as a pair programmer while building it.
- A full research cycle costs **a few cents** of Token Factory credits.

## Challenges we ran into

- **Code that ran perfectly and was still wrong.** Our first holding-period backtests held every position for one day instead of ten, because of one line in our own prompt (`position = signal.shift(1)`). That bug is the reason we added sanity checks, the luck test and finally the reviewer agent.
- **The same idea gave different answers:** +60% one day, −7% the next, because "buy" was interpreted differently each time. We pinned one execution convention, so the same idea now always gives the same number.
- **Reasoning tokens.** Nemotron Ultra sometimes used its whole default 8,192-token budget thinking and was cut off mid-script. Logging token usage found the problem in minutes, and raising the cap made first attempts succeed.
- **Free data has limits.** Yahoo sometimes returns empty data to cloud servers, crypto trades on weekends, and there is no free point-in-time data for fundamentals like EV/EBIT.

## Accomplishments that we're proud of

- An agent that is **honest by design**: it shows exactly why an idea fails instead of telling you what you want to hear.
- A reviewer agent that **caught a real bug in its colleague's code**, live in the demo.
- It is **fully autonomous**: every weekday morning it reads the news, tests a new idea and adds it to the leaderboard, with nobody pressing a button.

## What we learned

- Trading costs and luck kill far more strategies than bad ideas do.
- Code written by an AI needs the same checks as code written by a human: tests, sanity checks and a second pair of eyes.
- Picking the model by task, Ultra for code and Super for text and review, keeps quality high and cost low.

## What's next

- Point-in-time fundamentals and insider trades from SEC filings, so value ideas like "low EV/EBIT" can be tested properly.
- Running generated code in **Nebius Serverless Jobs** instead of a local process.
- Letting the agent combine its robust ideas into a portfolio.
