#!/usr/bin/env python3
"""context_gen_v0.py — Graph-driven CC task generation (Experiment 001).

Loads the reference pipeline graph, parses the SRS, detects implemented FRs,
extracts a context slice for the next unimplemented FR, and writes a CC task file.

Usage:
    python experiments/context_gen_v0.py --next-task
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

# Allow running from repo root or experiments/
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sgcc.graph.store import GraphStore

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
GRAPH_PATH = REPO_ROOT / "tests" / "reference_graphs" / "pilot_survey_pipeline.json"
SRS_PATH = REPO_ROOT / "docs" / "requirements" / "srs.md"
SRC_PATH = REPO_ROOT / "src" / "sgcc"
OUTPUT_DIR = REPO_ROOT / "cc_tasks"

# ---------------------------------------------------------------------------
# Hard-coded implementation status (v0 — heuristic, not reflection)
# FR-007: serializable graph → store.py exists with save/load
# FR-050-052: CLI → cli.py exists
# Everything else: not implemented
# ---------------------------------------------------------------------------
IMPLEMENTED_FRS = {
    "007": "GraphStore save/load (JSONL event log) in src/sgcc/graph/store.py",
    "050": "CLI entry point (sgcc) in src/sgcc/cli.py",
    "051": "CLI command groups: graph in src/sgcc/cli.py",
    "052": "pip-installable via pyproject.toml",
}

CRITICAL_PATH_NEXT = "001"  # Hard-coded for v0


# ---------------------------------------------------------------------------
# Step 1: Load graph
# ---------------------------------------------------------------------------

def load_graph() -> GraphStore:
    with open(GRAPH_PATH) as f:
        data = json.load(f)
    return GraphStore.from_json(data)


# ---------------------------------------------------------------------------
# Step 2: Parse SRS
# ---------------------------------------------------------------------------

def parse_srs() -> dict[str, str]:
    """Return {fr_number: description} for all FR-XXX in the SRS."""
    text = SRS_PATH.read_text()
    # Match lines like: - **FR-001**: The system SHALL parse ...
    # or: FR-001: description
    pattern = re.compile(r'FR-(\d{3})[:\*\s]+([^\n]+)')
    results = {}
    for m in pattern.finditer(text):
        num = m.group(1)
        desc = m.group(2).strip().rstrip(".")
        # Keep first occurrence of each FR number
        if num not in results:
            results[num] = desc
    return results


# ---------------------------------------------------------------------------
# Step 3: Detect implemented FRs
# ---------------------------------------------------------------------------

def detect_implemented() -> dict[str, str]:
    return IMPLEMENTED_FRS.copy()


# ---------------------------------------------------------------------------
# Step 4 + 5: Extract context slice for FR-001 (DATA step parsing)
# ---------------------------------------------------------------------------

def extract_fr001_context(store: GraphStore) -> dict:
    """Extract the subgraph relevant to FR-001: SAS DATA step parsing.

    Expansion strategy:
    1. Seed: all DataStep nodes
    2. Layer 1: Dataset nodes directly connected to DataSteps (inputs/outputs)
    3. Layer 2: Variable nodes contained in those Datasets (contains edges)
    4. Layer 3: Transform nodes that produce/consume those Variables
    5. Include all edges between nodes in the final set

    Returns a dict with:
        nodes: list of node attribute dicts
        edges: list of edge attribute dicts
        node_ids: set of node IDs in the slice
    """
    G = store._graph

    # Layer 1: DataStep nodes (seed)
    datastep_ids = {
        nid for nid, d in G.nodes(data=True)
        if d.get("node_type") == "DataStep"
    }

    # Layer 2: Dataset nodes directly connected to DataSteps
    dataset_ids: set[str] = set()
    for nid in datastep_ids:
        for adj in list(G.predecessors(nid)) + list(G.successors(nid)):
            if G.nodes[adj].get("node_type") == "Dataset":
                dataset_ids.add(adj)

    # Layer 3: Variable nodes contained in those Datasets (via 'contains' edges)
    variable_ids: set[str] = set()
    for nid in dataset_ids:
        for adj in G.successors(nid):
            if G.nodes[adj].get("node_type") == "Variable":
                variable_ids.add(adj)

    # Layer 4: Transform nodes that produce or consume those Variables
    transform_ids: set[str] = set()
    for nid in variable_ids:
        for adj in list(G.predecessors(nid)) + list(G.successors(nid)):
            if G.nodes[adj].get("node_type") == "Transform":
                transform_ids.add(adj)

    # Final node set
    slice_ids = datastep_ids | dataset_ids | variable_ids | transform_ids

    # Collect node data
    nodes = [dict(G.nodes[nid]) for nid in slice_ids if G.has_node(nid)]

    # Collect edges where BOTH endpoints are in the slice
    edges = []
    for u, v, data in G.edges(data=True):
        if u in slice_ids and v in slice_ids:
            edges.append(dict(data))

    return {
        "nodes": nodes,
        "edges": edges,
        "node_ids": slice_ids,
    }


# ---------------------------------------------------------------------------
# Step 6: Generate CC task file
# ---------------------------------------------------------------------------

def generate_task_file(
    fr_map: dict[str, str],
    implemented: dict[str, str],
    context: dict,
    store: GraphStore,
) -> Path:
    today = date.today().isoformat()
    out_path = OUTPUT_DIR / f"auto_{today}_fr001_data_step_parser.md"

    fr001_desc = fr_map.get("001", "Parse SAS DATA steps and extract variable lineage graph")
    fr004_desc = fr_map.get("004", "Identify implicit variable creation (SET, MERGE, RETAIN)")
    fr006_desc = fr_map.get("006", "Detect BY-group processing patterns (FIRST./LAST.)")

    # Summarize context slice by type
    type_counts: dict[str, int] = {}
    for n in context["nodes"]:
        t = n.get("node_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Rough token estimate: ~1.3 tokens per word, ~6 chars per word
    raw_chars = sum(len(json.dumps(n)) for n in context["nodes"]) + \
                sum(len(json.dumps(e)) for e in context["edges"])
    est_tokens = raw_chars // 4

    # Format context nodes for the task file
    def fmt_nodes(node_type: str) -> str:
        lines = []
        for n in sorted(context["nodes"], key=lambda x: x.get("id", "")):
            if n.get("node_type") == node_type:
                lines.append(f"  - `{n['id']}`")
                if node_type == "DataStep":
                    ins = n.get("input_datasets", [])
                    out = n.get("output_dataset", "")
                    lines.append(f"    - inputs: {ins}  →  output: `{out}`")
                elif node_type == "Variable":
                    lines.append(
                        f"    - name=`{n.get('name')}` type={n.get('data_type')} "
                        f"state={n.get('state')}"
                    )
                elif node_type == "Transform":
                    lines.append(f"    - op=`{n.get('operation')}` — {n.get('description', '')[:80]}")
                elif node_type == "Dataset":
                    lines.append(f"    - name=`{n.get('name')}` key={n.get('key_variables')}")
        return "\n".join(lines) if lines else "  (none)"

    def fmt_edges(edge_type: str) -> str:
        lines = []
        for e in context["edges"]:
            if e.get("edge_type") == edge_type:
                lines.append(f"  - `{e['source']}` → `{e['target']}`")
        return "\n".join(lines) if lines else "  (none)"

    unimplemented = {k: v for k, v in fr_map.items() if k not in implemented}

    task = f"""\
# CC Task: Implement FR-001 — SAS DATA Step Parser
*Auto-generated by context_gen_v0.py on {today}*

---

## What This Task Is

Implement `src/sgcc/extractor/data_step_parser.py` — the SAS DATA step parser that
extracts graph nodes and edges from a SAS DATA step.

This is the first extraction component (FR-001). It is the critical path item because
all downstream graph extraction (FR-002 through FR-006) depends on DATA step parsing.

---

## Functional Requirements

**FR-001:** {fr001_desc}

**FR-004:** {fr004_desc}

**FR-006:** {fr006_desc}

Related (out of scope for this task but adjacent):
- FR-002: PROC step parsing
- FR-003: Macro expansion handling
- FR-005: SAS missing value semantics

---

## Implementation Target

Create: `src/sgcc/extractor/data_step_parser.py`

The parser receives a SAS DATA step as a string (or list of lines) and returns:
- A list of `VariableNode` objects created or modified by the step
- A list of `TransformNode` objects representing operations within the step
- A list of `DatasetNode` objects (input/output datasets)
- A list of `DataStepNode` for the step itself
- A list of `GraphEdge` objects connecting all of the above

The caller adds these to a `GraphStore` instance.

---

## Context Slice from Reference Graph

The following subgraph is the subset of the reference pipeline relevant to DATA step
parsing. It contains {len(context['nodes'])} nodes and {len(context['edges'])} edges
(~{est_tokens} tokens of context).

**Node counts by type:** {json.dumps(type_counts, indent=None)}

### DataStep Nodes (ground truth for what a parsed DATA step should produce)

{fmt_nodes('DataStep')}

### Dataset Nodes (inputs and outputs of DataSteps)

{fmt_nodes('Dataset')}

### Variable Nodes (variables produced/consumed by DataSteps)

{fmt_nodes('Variable')}

### Transform Nodes (operations within DataSteps)

{fmt_nodes('Transform')}

### Relevant Edges

**inputs / outputs (DataStep ↔ Dataset):**
{fmt_edges('inputs')}
{fmt_edges('outputs')}

**produces / consumes (Transform ↔ Variable):**
{fmt_edges('produces')}
{fmt_edges('consumes')}

**sequenced_before (Transform ordering):**
{fmt_edges('sequenced_before')}

---

## Acceptance Criteria

Parse this SAS DATA step fragment and produce graph nodes that match the reference:

```sas
data work.survey_clean;
  set work.survey_raw;
  /* Range validation */
  if income < 0 or income > 9999999 then income_clean = .;
  else income_clean = income;
  /* Age group recode */
  if age < 18 then age_group = 1;
  else if age < 35 then age_group = 2;
  else if age < 55 then age_group = 3;
  else if age < 65 then age_group = 4;
  else if age < 75 then age_group = 5;
  else age_group = 6;
run;
```

The parser **must** produce:
- [ ] A `DataStepNode` with `input_datasets=["work.survey_raw"]`, `output_dataset="work.survey_clean"`
- [ ] A `TransformNode` with `operation=TransformType.SET`
- [ ] A `TransformNode` with `operation=TransformType.CONDITIONAL_ASSIGN` for income_clean
- [ ] A `TransformNode` with `operation=TransformType.CONDITIONAL_ASSIGN` for age_group
- [ ] `VariableNode` for `income` (state=raw), `income_clean` (state=cleaned), `age` (state=raw), `age_group` (state=derived)
- [ ] `GraphEdge(edge_type=CONSUMES)` from income_clean transform to income
- [ ] `GraphEdge(edge_type=PRODUCES)` from income_clean transform to income_clean
- [ ] `GraphEdge(edge_type=DERIVED_FROM)` from income_clean to income

---

## Test File

Create: `tests/test_data_step_parser.py`

Tests must cover:
- Parse SET statement → correct DataStepNode and Dataset inputs
- Parse IF/THEN/ELSE → correct TransformNode(CONDITIONAL_ASSIGN) and Variable edges
- Parse RETAIN statement → TransformNode(RETAIN)
- Parsed nodes load into GraphStore without errors
- Parsed subgraph is structurally equivalent to the reference DataStep nodes

---

## What NOT to Build

- Do NOT build a full SAS grammar parser (LLM-assisted extraction is fine)
- Do NOT handle macro expansion (FR-003, separate task)
- Do NOT handle PROC steps (FR-002, separate task)
- Do NOT handle BY-group FIRST./LAST. yet (FR-006, can be stubbed)

---

## Project Context

Read `CLAUDE.md` and `docs/requirements/srs.md` before implementing.
The graph schema is in `docs/design/reference_graph_schema.md`.
All node and edge types are in `src/sgcc/graph/models.py`.
The `GraphStore` API is in `src/sgcc/graph/store.py`.

When done, run `/closeout`.
"""

    out_path.write_text(task)
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Graph-driven CC task generator (v0)")
    parser.add_argument("--next-task", action="store_true",
                        help="Generate the next CC task from graph state")
    args = parser.parse_args()

    if not args.next_task:
        parser.print_help()
        sys.exit(0)

    print("Analyzing project state...")

    # Step 1: Load graph
    store = load_graph()
    stats = store.stats()
    print(f"  Graph: {stats['total_nodes']} nodes, {stats['total_edges']} edges "
          f"(reference pipeline loaded)")

    # Step 2: Parse SRS
    fr_map = parse_srs()
    print(f"  SRS: {len(fr_map)} functional requirements parsed")

    # Step 3: Detect implemented
    implemented = detect_implemented()
    impl_list = ", ".join(f"FR-{k}" for k in sorted(implemented))
    print(f"  Implemented: {impl_list}")

    # Step 4: Identify next
    unimplemented = sorted(k for k in fr_map if k not in implemented)
    next_fr = CRITICAL_PATH_NEXT
    next_desc = fr_map.get(next_fr, "(not found in SRS)")
    print(f"  Next on critical path: FR-{next_fr} ({next_desc[:60]})")
    print(f"  Remaining unimplemented: {len(unimplemented)} FRs")

    # Step 5: Extract context slice
    print(f"\nContext slice for FR-{next_fr}:")
    context = extract_fr001_context(store)

    type_counts: dict[str, int] = {}
    for n in context["nodes"]:
        t = n.get("node_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    print(f"  Nodes retrieved: {len(context['nodes'])} "
          f"({', '.join(f'{v} {k}' for k, v in sorted(type_counts.items()))})")
    print(f"  Edges retrieved: {len(context['edges'])}")

    raw_chars = sum(len(json.dumps(n)) for n in context["nodes"]) + \
                sum(len(json.dumps(e)) for e in context["edges"])
    est_tokens = raw_chars // 4
    full_chars = sum(len(json.dumps(dict(store._graph.nodes[n]))) for n in store._graph.nodes)
    print(f"  Estimated tokens: ~{est_tokens:,} "
          f"(vs ~{full_chars // 4:,} for full graph — "
          f"{100 * len(context['nodes']) // stats['total_nodes']}% of nodes)")

    # Step 6: Generate task file
    out_path = generate_task_file(fr_map, implemented, context, store)
    print(f"\nGenerating CC task: {out_path.relative_to(REPO_ROOT)}")

    # Step 7: Print the generated file
    print("\n" + "=" * 70)
    print("GENERATED TASK FILE:")
    print("=" * 70)
    print(out_path.read_text())


if __name__ == "__main__":
    main()
