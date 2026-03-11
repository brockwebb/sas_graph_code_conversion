# Reference Graph Schema Design

**Version:** 0.1 — DRAFT
**Date:** 2026-03-10
**Purpose:** Define the graph schema for the intermediate representation and design the reference test pipeline.

---

## 1. Design Principles

1. **The graph is the specification, not the code.** The graph captures what the pipeline DOES, not how SAS expresses it.
2. **Language-agnostic nodes.** Node attributes describe semantics (what type, what range, what missing means), not syntax (SAS format names, PROC options).
3. **SAS-specific metadata lives in annotations, not core attributes.** The graph has a clean core schema with optional SAS-provenance annotations.
4. **Round-trip testable.** The schema must be precise enough that graph→SAS→graph produces an equivalent graph.
5. **Seldon-compatible.** Node types map to Seldon artifact types. Edge types map to Seldon relationship types. This graph schema IS a Seldon domain configuration.

---

## 2. Reference Test Pipeline Design

The reference pipeline exercises the SAS features that Census pipelines actually use. It's deliberately compact but semantically rich.

### 2.1 Scenario

A simplified survey data processing pipeline:

1. **Ingest**: Read raw survey responses and a geographic lookup table
2. **Clean**: Validate ranges, recode out-of-range values to missing
3. **Merge**: Join survey data with geography lookup on FIPS code
4. **Impute**: Hot-deck imputation for missing income values within geographic strata
5. **Derive**: Compute derived variables (poverty ratio, income-to-threshold)
6. **Weight**: Apply survey weights with replicate weight adjustment
7. **Aggregate**: Produce summary statistics by geography and demographic group
8. **Output**: Write final analytic file and summary tables

### 2.2 SAS Features Exercised

| Feature | Where in Pipeline | Why It Matters |
|---------|------------------|----------------|
| DATA step SET | Ingest | Basic dataset reading |
| DATA step MERGE + BY | Merge | Many-to-one join, match-merge semantics |
| IF/THEN/ELSE | Clean | Conditional logic, range checking |
| RETAIN | Impute | Carry values across observations |
| FIRST./LAST. by-group | Impute, Aggregate | By-group processing |
| ARRAY + DO loop | Clean, Derive | Iterative variable processing |
| Missing value propagation | Throughout | SAS-specific . semantics |
| FORMAT/PUT/INPUT | Derive | Format-driven value mapping |
| PROC SORT | Pre-merge, pre-aggregate | Ordering requirement for BY |
| PROC MEANS/SUMMARY | Aggregate | Statistical aggregation |
| PROC FREQ | Aggregate | Frequency/crosstab |
| PROC SURVEYMEANS | Weight + Aggregate | Complex survey statistics |
| PROC SQL | Derive (alternative path) | SQL-style joins and calculations |
| %MACRO/%MEND | Throughout | Parameterized reusable logic |
| %LET, &var resolution | Throughout | Macro variable substitution |
| CALL SYMPUT/SYMGET | Derive | Dynamic macro variable from data |

### 2.3 Variables (Target: ~30-40)

**Raw input variables:**
- `person_id` (char) — unique respondent identifier
- `fips_code` (char) — state+county FIPS
- `age` (num) — reported age
- `sex` (num) — 1=male, 2=female
- `race` (num) — race code (1-6)
- `income` (num) — reported income (can be missing)
- `housing_cost` (num) — monthly housing cost
- `survey_weight` (num) — base weight
- `rep_weight_1` through `rep_weight_10` (num) — replicate weights

**Geography lookup variables:**
- `fips_code` (char) — key
- `state_name` (char)
- `county_name` (char)
- `region` (num) — Census region code
- `poverty_threshold` (num) — poverty threshold for area

**Derived/intermediate variables:**
- `age_group` (num) — recoded from age
- `income_clean` (num) — after range validation
- `income_imputed` (num) — after imputation
- `poverty_ratio` (num) — income_imputed / poverty_threshold
- `in_poverty` (num) — binary indicator
- `weighted_income` (num) — income * survey_weight

**Aggregate output variables:**
- `mean_income` (num) — by geography/demographic group
- `se_income` (num) — standard error (survey-adjusted)
- `poverty_rate` (num) — proportion in poverty
- `n_respondents` (num) — unweighted count

---

## 3. Graph Node Schema (Detail)

### 3.1 Variable Node

```json
{
  "id": "var_income_imputed",
  "type": "Variable",
  "attributes": {
    "name": "income_imputed",
    "data_type": "numeric",
    "length": 8,
    "label": "Income after hot-deck imputation",
    "missing_semantics": "SAS_numeric_missing",
    "valid_range": {"min": 0, "max": 9999999},
    "state": "imputed",
    "units": "USD_annual"
  },
  "sas_provenance": {
    "source_file": "03_impute.sas",
    "line_range": [45, 78],
    "data_step": "data work.survey_imputed"
  }
}
```

### 3.2 Transform Node

```json
{
  "id": "xfm_hotdeck_income",
  "type": "Transform",
  "attributes": {
    "operation": "impute_hotdeck",
    "description": "Hot-deck imputation of income within FIPS strata",
    "parameters": {
      "strata_variable": "fips_code",
      "sort_variable": "age",
      "donor_requirement": "non_missing_income"
    }
  },
  "sas_provenance": {
    "source_file": "03_impute.sas",
    "line_range": [45, 78],
    "sas_construct": "DATA_STEP",
    "uses_retain": true,
    "uses_by_group": true
  }
}
```

### 3.3 Dataset Node

```json
{
  "id": "ds_survey_imputed",
  "type": "Dataset",
  "attributes": {
    "name": "survey_imputed",
    "description": "Survey responses after imputation",
    "observation_unit": "person",
    "key_variables": ["person_id"]
  },
  "sas_provenance": {
    "library": "WORK",
    "sas_name": "work.survey_imputed"
  }
}
```

---

## 4. Trace Schema

A trace captures the value of every variable at every transform node for a given benchmark dataset run.

```json
{
  "trace_id": "trace_sas_pilot_v1",
  "pipeline": "pilot_survey_processing",
  "language": "SAS",
  "benchmark_data": "benchmark_v1.csv",
  "benchmark_hash": "sha256:abc123...",
  "captured_at": "2026-03-15T10:30:00Z",
  "snapshots": [
    {
      "node_id": "xfm_hotdeck_income",
      "observation": 1,
      "values": {
        "income": 45000,
        "income_imputed": 45000,
        "fips_code": "24003",
        "imputation_flag": 0
      }
    },
    {
      "node_id": "xfm_hotdeck_income",
      "observation": 2,
      "values": {
        "income": null,
        "income_imputed": 42000,
        "fips_code": "24003",
        "imputation_flag": 1
      }
    }
  ]
}
```

### 4.1 Trace Comparison Output

```json
{
  "comparison_id": "cmp_sas_vs_python_pilot_v1",
  "trace_a": "trace_sas_pilot_v1",
  "trace_b": "trace_python_pilot_v1",
  "result": "DIVERGENCE",
  "first_divergence": {
    "node_id": "xfm_poverty_ratio",
    "observation": 47,
    "variable": "poverty_ratio",
    "value_a": 1.2345678,
    "value_b": 1.2345679,
    "difference": 0.0000001,
    "tolerance": 0.00001,
    "within_tolerance": true
  },
  "summary": {
    "nodes_compared": 142,
    "nodes_match": 142,
    "nodes_diverge_within_tolerance": 3,
    "nodes_diverge_beyond_tolerance": 0,
    "nodes_missing_in_a": 0,
    "nodes_missing_in_b": 0
  }
}
```

---

## 5. Seldon Domain Configuration Mapping

This graph schema maps to Seldon as a domain configuration:

| SGCC Concept | Seldon Artifact Type | Notes |
|--------------|---------------------|-------|
| Variable | `Variable` (new) | Extends Seldon's type system |
| Dataset | `DataFile` (existing) | Already in research config |
| Transform | `Transform` (new) | Operation node |
| Pipeline | `Pipeline` (new) | Top-level container |
| Macro | `Macro` (new) | SAS-specific but generalizable to "template" |
| Trace | `Result` (existing) | A trace IS a result with provenance |
| Comparison | `ValidationReport` (new) | Structured comparison output |

| SGCC Relationship | Seldon Relationship Type | Notes |
|-------------------|-------------------------|-------|
| derived_from | `derived_from` (new) | Variable lineage |
| contains | `contains` (existing from ANTS) | Dataset→Variable |
| produces/consumes | `produced_by`/`consumed_by` | Transform↔Variable |
| outputs/inputs | `outputs`/`inputs` | Step↔Dataset |
| expands_to | `expands_to` (new) | Macro→Transform |

---

*This document drives T0-1 (schema design) for both this project and Seldon's domain configuration extensibility.*
