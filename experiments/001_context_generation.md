# Experiment: Graph-Driven Context Generation

**Date:** 2026-03-10
**Purpose:** Test whether the project graph can generate a precisely-scoped CC task by querying itself — the foundational experiment for Seldon Phase C.

---

## Hypothesis

The reference pipeline graph (65 nodes, 91 edges) contains enough structured information to automatically generate a Claude Code task file for the next piece of implementation work, with the right context slice and no irrelevant information. If this works, the graph replaces human-authored task files as the source of CC work items.

## The Experiment

### Step 1: Query the graph for "what's next"

Write a Python script (`experiments/context_gen_v0.py`) that:

1. Loads the reference pipeline graph from `tests/reference_graphs/pilot_survey_pipeline.json`
2. Loads the SRS from `docs/requirements/srs.md`
3. Cross-references: which functional requirements (FR-XXX) are exercised by the reference graph but have no implementation yet in `src/`?
4. For the highest-priority unimplemented FR, extracts the relevant subgraph — only the nodes and edges that FR touches
5. Generates a CC task file from that subgraph context

### Step 2: Evaluate the generated task

- Is the context slice precise enough for CC to build from?
- Does it include irrelevant information?
- Does it miss critical dependencies?
- Would a human need to edit it before handing it to CC?

### Step 3: Feed the generated task to CC

- Run CC against the generated task
- Compare output quality to the hand-written task (Phase 0 task we already ran)
- Did CC ask questions it shouldn't have needed to? (indicates missing context)
- Did CC build something wrong? (indicates malformed context slice)

## What the Script Should Produce

```
$ python experiments/context_gen_v0.py --next-task

Analyzing project state...
  Graph: 65 nodes, 91 edges (reference pipeline loaded)
  SRS: 52 functional requirements parsed
  Implemented: FR-007 (graph serialization), FR-050-052 (CLI skeleton)
  Next on critical path: FR-001 (SAS DATA step parsing)

Context slice for FR-001:
  Nodes retrieved: 12 (5 DataStep nodes, 7 Variable nodes affected by DATA steps)
  Edges retrieved: 18 (SET, MERGE, RETAIN, assignment relationships)
  Related FRs: FR-004 (implicit variable creation), FR-006 (BY-group processing)

Generating CC task: cc_tasks/auto_2026-03-10_fr001_data_step_parser.md
```

## Implementation Notes

This is a v0 experiment — scrappy, not production. The point is to test the idea, not build a polished tool.

- Parse the SRS with regex or simple string matching (don't over-engineer the parser)
- "Implemented" detection: check if files exist in `src/` that reference the FR number, or check test coverage. Simple heuristic is fine.
- Subgraph extraction: NetworkX has `subgraph()` and `ego_graph()` — use them
- Task generation: template string with the subgraph context injected. Not LLM-generated — deterministic.

## Success Criteria

1. The script runs and produces a task file without human intervention
2. The context slice contains the right nodes (no false positives, no missing dependencies)
3. CC can build from the generated task with quality comparable to a hand-written task
4. The generated task is SMALLER (fewer tokens) than a hand-written task because it includes only what's needed

---

## What This Proves If It Works

The graph database can serve as the "persistent context store" that replaces the context window for cross-session state. Each CC invocation gets a precise slice, not a summary, not a compressed history. The graph query IS the retrieval, and the quality of that retrieval determines the quality of the agent's work.

This is the foundation for:
- `seldon context generate` — automatic CC task generation from graph state
- Multi-agent work where each agent gets a different subgraph slice
- Scaling to projects with thousands of artifacts without context window pressure
