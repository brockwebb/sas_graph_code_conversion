# SAS Graph Code Conversion

## What This Is

An AI-assisted system that converts legacy SAS statistical pipelines to R or Python through a graph-based intermediate representation, with full traceability and automated verification.

The system does NOT translate SAS to Python line-by-line. It extracts a directed acyclic graph (DAG) blueprint capturing every variable, transformation, dependency, and data flow — then generates target language code FROM the blueprint. Verification compares execution traces at every graph node between SAS and the generated code.

## Project Owner
- Brock Webb, U.S. Census Bureau

## Repository Structure
```
sas_graph_code_conversion/
├── CLAUDE.md              # This file — project context for AI assistants
├── docs/
│   ├── proposal.md        # Heilmeier catechism project proposal
│   ├── requirements/      # Requirements specifications
│   │   └── srs.md         # System Requirements Specification
│   └── design/            # Architecture and design decisions
│       └── reference_graph_schema.md
├── src/                   # Source code (Python)
│   ├── extractor/         # SAS → graph extraction engine
│   ├── generator/         # Graph → R/Python code generation
│   ├── tracer/            # Execution trace capture and comparison
│   └── graph/             # Graph data model and operations
├── tests/                 # Test suite
│   ├── reference_graphs/  # Known-ground-truth DAGs
│   ├── sas_programs/      # SAS code generated from reference graphs
│   └── validation/        # Trace comparison tests
├── cc_tasks/              # Claude Code task files (gitignored)
├── handoffs/              # Session handoff documents (gitignored)
└── tmp/                   # Temporary working files (gitignored)
```

## Core Workflow (4 Steps)

1. **Graph Extraction** — Parse SAS code into a DAG capturing every variable, transformation, and data flow dependency. The graph IS the specification.
2. **Code Generation** — Use the graph blueprint to generate R or Python code. AI assistance constrained by the graph, not freeform translation.
3. **Trace Validation** — Run synthetic benchmark data through both SAS and generated code. Compare values at every graph node. Divergence pinpoints exact transformation where conversion failed.
4. **Variable Ontology** — The accumulated graph data becomes a queryable ontology of Census variables from raw inputs through intermediates to published outputs. Cross-survey normalization becomes possible.

## Experimental Design: Self-Contained Validation

We control the entire experimental apparatus:
- Design the reference graph FIRST (the ground truth)
- Generate SAS code FROM the graph (proving graph→code works)
- Extract the graph back FROM the SAS (proving code→graph works)
- Round-trip test: reference graph → SAS → extracted graph should match
- No dependency on external SMEs for validation

## Relationship to Other Systems

| System | Relationship |
|--------|-------------|
| **Seldon** | This project's research support system. Seldon manages artifacts (SAS scripts, graphs, converted code, trace results), tracks state machines, enforces provenance chains. This project is Seldon's proof-of-concept use case. |
| **Wintermute** | Not directly related. Variable ontology output (Step 4) may eventually feed Wintermute's cross-domain knowledge graph. |
| **ANTS** | Historical predecessor to Seldon. Patterns carry forward through Seldon. |

## Key Technical Challenges

- **SAS macro expansion**: Text substitution generates code at runtime. Must handle pre- and post-expansion parsing.
- **Implicit variable creation**: SAS creates variables silently in DATA steps (SET, MERGE, RETAIN, FIRST./LAST.)
- **Missing value semantics**: SAS treats missing values differently than R/Python — propagation rules differ
- **PROC-specific semantics**: PROC SURVEYMEANS, PROC MIXED, etc. have complex behavior that resists simple decomposition
- **Format-informed logic**: SAS formats/informats affect computation, not just display

## Tech Stack

- **Language**: Python
- **Graph**: NetworkX + JSONL event log (consistent with Seldon architecture)
- **SAS Parsing**: TBD — likely LLM-assisted extraction (Gemini Flash) rather than grammar-based parser, given macro complexity
- **Code Generation**: LLM-assisted from graph blueprint (Claude Code / Gemini)
- **Validation**: Deterministic trace comparison framework
- **CLI**: Click or Typer (consistent with Seldon)
- **No infrastructure dependencies**: Runs on standard workstation with API access

## Autonomy Model

Target: Level 4 (Developer as Product Manager) with Seldon support.
- Specifications and graph schemas are the input
- Claude Code builds from specs
- Validation is automated via trace comparison
- Human reviews outcomes, not code

## Commands (Planned)

```bash
# Graph operations
sgcc graph create <name>          # Create reference graph from schema
sgcc graph extract <sas_file>     # Extract graph from SAS code
sgcc graph compare <g1> <g2>      # Compare two graphs (round-trip test)
sgcc graph export <format>        # Export graph (JSON, DOT, cypher)

# Code generation
sgcc generate sas <graph>         # Generate SAS from graph (test scaffold)
sgcc generate python <graph>      # Generate Python from graph
sgcc generate r <graph>           # Generate R from graph

# Validation
sgcc trace capture <code> <data>  # Run code, capture trace at every node
sgcc trace compare <t1> <t2>      # Compare two traces
sgcc trace report <comparison>    # Generate validation report

# Ontology
sgcc ontology build               # Build variable ontology from accumulated graphs
sgcc ontology query <variable>    # Trace a variable through all known pipelines
```
