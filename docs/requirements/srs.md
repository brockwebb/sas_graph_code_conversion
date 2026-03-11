# SAS Graph Code Conversion — System Requirements Specification

**Version:** 0.1 — DRAFT
**Date:** 2026-03-10
**Status:** Initial requirements capture

---

## 1. Purpose

This document specifies the requirements for a system that converts SAS statistical pipelines to R or Python through a graph-based intermediate representation with automated trace-level verification.

---

## 2. Scope

### 2.1 In Scope

- SAS DATA step parsing and graph extraction (variable creation, assignment, conditional logic, RETAIN, MERGE, SET, BY-group processing, FIRST./LAST.)
- SAS PROC parsing (initially: SORT, MEANS, FREQ, SURVEYMEANS, SQL, TRANSPOSE, FORMAT)
- SAS macro expansion handling (MPRINT/MLOGIC capture and/or static reconstruction)
- Graph-based intermediate representation (DAG) of variable lineage and transformations
- Code generation from graph to Python and R
- Trace capture: execution snapshots at every graph node
- Trace comparison: node-by-node equivalence checking with configurable tolerance
- Reference graph design and round-trip validation (graph→SAS→graph)
- CLI interface for all operations

### 2.2 Out of Scope (This Version)

- SAS/IML, SAS/GRAPH, SAS/STAT PROCs beyond those listed above
- ODS output parsing
- SAS formats library conversion (addressed as composite nodes, not full format engine)
- Real-time conversion (batch processing only)
- GUI or web interface
- Direct integration with SAS runtime (we work with source code and trace output, not SAS sessions)

---

## 3. Graph Schema Requirements

### 3.1 Node Types (Artifact Types)

| Node Type | Description | Key Attributes |
|-----------|-------------|----------------|
| `Variable` | A data variable at a specific pipeline stage | name, type (num/char), length, format, informat, label, missing_semantics, valid_range |
| `Dataset` | A SAS dataset (intermediate or output) | name, library, observation_count, variable_list |
| `Transform` | A single transformation operation | operation_type, source_code_ref, line_range, parameters |
| `Macro` | A SAS macro definition | name, parameters, expansion_template |
| `MacroInvocation` | A specific macro call with resolved parameters | macro_ref, actual_parameters, expanded_code_ref |
| `Proc` | A SAS PROC invocation | proc_type, options, by_variables, class_variables, output_datasets |
| `DataStep` | A SAS DATA step | input_datasets, output_dataset, where_clause |
| `Pipeline` | Top-level container for a complete SAS program/workflow | name, source_files, description |

### 3.2 Edge Types (Relationship Types)

| Edge Type | From → To | Description |
|-----------|-----------|-------------|
| `derived_from` | Variable → Variable | Variable B is computed from Variable A |
| `contains` | Dataset → Variable | Dataset includes this variable |
| `produces` | Transform → Variable | Transform creates or modifies this variable |
| `consumes` | Transform → Variable | Transform reads this variable as input |
| `outputs` | DataStep/Proc → Dataset | Step produces this dataset |
| `inputs` | DataStep/Proc → Dataset | Step reads this dataset |
| `expands_to` | MacroInvocation → Transform[] | Macro call resolves to these operations |
| `defined_by` | MacroInvocation → Macro | This invocation uses this macro definition |
| `sequenced_before` | Transform → Transform | Execution ordering dependency |
| `merged_with` | Dataset → Dataset | Datasets joined in a MERGE/SQL JOIN |
| `filtered_by` | Variable → Transform | Variable filtered by WHERE/IF condition |

### 3.3 Variable State Machine

Variables transition through states as they move through the pipeline:

```
raw → validated → cleaned → imputed → derived → weighted → aggregated → published
```

Not all variables pass through all states. The state machine is descriptive, not prescriptive — it captures what the SAS code actually does, not what it should do.

### 3.4 Transform Vocabulary

Minimum set of transform types the graph must represent:

| Transform Type | SAS Construct | Description |
|---------------|---------------|-------------|
| `assign` | Assignment statement | Direct variable assignment |
| `conditional_assign` | IF/THEN/ELSE | Conditional assignment |
| `retain` | RETAIN statement | Value carried across observations |
| `merge` | MERGE + BY | Dataset merge on key variables |
| `set` | SET statement | Dataset concatenation/interleave |
| `sort` | PROC SORT | Reorder observations |
| `aggregate` | PROC MEANS/SUMMARY | Statistical aggregation |
| `frequency` | PROC FREQ | Frequency/crosstab computation |
| `survey_stat` | PROC SURVEYMEANS etc. | Complex survey statistics |
| `sql_query` | PROC SQL | SQL-style operations |
| `transpose` | PROC TRANSPOSE | Reshape data |
| `format_apply` | FORMAT/PUT/INPUT | Format-driven value transformation |
| `array_op` | ARRAY + DO loop | Array-based iteration |
| `by_group` | BY statement | By-group processing (FIRST./LAST.) |
| `macro_expand` | %macro/%mend | Macro text substitution |
| `missing_propagate` | (implicit) | SAS missing value propagation rules |

---

## 4. Functional Requirements

### 4.1 Graph Extraction (SAS → Graph)

- **FR-001**: The system SHALL parse SAS DATA steps and extract all variable assignments, conditional logic, and data flow dependencies as graph nodes and edges.
- **FR-002**: The system SHALL parse SAS PROC steps (SORT, MEANS, FREQ, SURVEYMEANS, SQL, TRANSPOSE, FORMAT) and represent their operations as graph nodes.
- **FR-003**: The system SHALL handle SAS macro expansion through either static analysis or MPRINT/MLOGIC output parsing, linking macro invocations to their expanded operations.
- **FR-004**: The system SHALL identify implicit variable creation (SET, MERGE, RETAIN) and represent these as explicit graph nodes.
- **FR-005**: The system SHALL capture SAS missing value semantics (. = missing for numeric, '' = missing for character, special missing .A-.Z) as variable attributes.
- **FR-006**: The system SHALL detect BY-group processing patterns (FIRST./LAST. variables) and represent them as conditional transform nodes.
- **FR-007**: The system SHALL produce a serializable graph representation (JSON + JSONL event log, consistent with Seldon architecture).

### 4.2 Code Generation (Graph → Target Language)

- **FR-010**: The system SHALL generate syntactically valid Python code from a graph blueprint.
- **FR-011**: The system SHALL generate syntactically valid R code from a graph blueprint.
- **FR-012**: Generated code SHALL preserve variable names, labels, and types from the graph.
- **FR-013**: Generated code SHALL implement equivalent missing value handling for the target language.
- **FR-014**: Generated code SHALL include trace instrumentation (value capture at each transform node) by default.
- **FR-015**: Generated code SHALL map SAS macro patterns to equivalent parameterized functions in the target language.

### 4.3 Trace Capture and Comparison

- **FR-020**: The system SHALL capture the value of every variable at every transformation step when executing a pipeline against benchmark data (the "trace").
- **FR-021**: The system SHALL compare two traces (SAS vs. target language) node-by-node and report matches, mismatches, and missing nodes.
- **FR-022**: Trace comparison SHALL support configurable floating-point tolerance per variable type.
- **FR-023**: Trace comparison SHALL report the FIRST divergence point in the DAG — the earliest transformation node where outputs differ.
- **FR-024**: The system SHALL produce a structured validation report from trace comparison results.

### 4.4 Round-Trip Validation

- **FR-030**: The system SHALL generate SAS code from a reference graph (graph→SAS).
- **FR-031**: The system SHALL extract a graph from generated SAS code (SAS→graph).
- **FR-032**: The system SHALL compare two graphs (reference vs. extracted) for structural equivalence — same nodes, same edges, same attributes within tolerance.

### 4.5 Variable Ontology

- **FR-040**: The system SHALL accumulate variable metadata across multiple converted pipelines into a queryable graph.
- **FR-041**: The system SHALL support querying a variable's full lineage: from raw input through all intermediates to published output.
- **FR-042**: The system SHALL support cross-pipeline variable mapping: identifying variables across different pipelines that represent the same concept.

### 4.6 CLI Interface

- **FR-050**: All operations SHALL be accessible via a Python CLI (`sgcc` command).
- **FR-051**: The CLI SHALL support the command groups: `graph`, `generate`, `trace`, `ontology`.
- **FR-052**: The CLI SHALL be pip-installable.

---

## 5. Non-Functional Requirements

- **NFR-001**: Zero infrastructure dependency. Runs on a standard workstation with Python 3.10+ and API access. No database servers, no Docker requirement for basic operation.
- **NFR-002**: Graph storage uses NetworkX + JSONL event log (consistent with Seldon architecture, per AD-004).
- **NFR-003**: All graph mutations are event-sourced (append-only log as source of truth).
- **NFR-004**: Seldon-compatible artifact types and relationship types — the graph schema must be representable as a Seldon domain configuration.
- **NFR-005**: LLM-assisted extraction and generation use Gemini Flash for structured extraction and Claude for code generation. Model selection is configurable, not hardcoded.
- **NFR-006**: The system SHALL process a reference pipeline (≤50 variables, ≤20 transforms) in under 5 minutes end-to-end (extraction + generation + trace comparison).

---

## 6. Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Seldon core engine | Not yet built | This project is Seldon's proof-of-concept. Can proceed with standalone graph implementation, later integrate when Seldon exists. |
| SAS runtime access | Available at Census | Needed for trace capture on SAS side. Not needed for graph extraction or code generation. |
| Gemini Flash API | Available | For LLM-assisted extraction. |
| Claude Code | Available | For implementation from specifications. |
| NetworkX | Available | pip install. |

---

## 7. Open Design Questions

1. **SAS parsing approach**: Full grammar parser (tree-sitter with SAS grammar) vs. LLM-assisted extraction (send SAS code to Gemini Flash, get structured graph back) vs. hybrid? LLM extraction is faster to build but less deterministic. Grammar parser is more reliable but SAS grammar is complex and poorly specified.

2. **Graph serialization format**: JSONL event log (Seldon-compatible) vs. JSON snapshot vs. both? Event log is better for provenance but adds complexity.

3. **Trace capture on SAS side**: Instrument the SAS code with PUT statements to capture intermediate values? Use MPRINT output? Run SAS interactively and capture workspace state? Each has different access requirements.

4. **Floating-point tolerance strategy**: Per-variable-type defaults? Per-transform-type? User-configurable per comparison? Need to handle the SAS vs. IEEE 754 precision differences.

5. **Composite PROC handling**: PROC SURVEYMEANS with 15 options is one SAS statement but potentially dozens of graph operations. Represent as single composite node with internal subgraph, or flatten to individual operations?

---

*This SRS will evolve as the reference graph design (Phase 0) reveals what the schema actually needs to express.*
