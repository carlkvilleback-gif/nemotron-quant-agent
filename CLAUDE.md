## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- After modifying code, also run `C:\Users\Carla\.graphify\sync.cmd .` so the graph AND the Obsidian vault (Documents\Kunskapskarta) stay current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.

## Perplexity research

Rules:
- For any question that needs current information, web search, or research (market data, news, documentation, prices, events), always use the Perplexity skill/tools instead of the built-in WebSearch.
- Invoke the perplexity skill automatically whenever it is relevant — do not wait for the user to type /perplexity.
- Always present research results with source citations.
