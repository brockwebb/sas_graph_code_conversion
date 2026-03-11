# SAS Graph Code Conversion — Project Proposal

**Graph-Based SAS Code Conversion: Reproducible, Verifiable Statistical Pipeline Migration at Scale**

Heilmeier Catechism Format

Brock Webb — U.S. Census Bureau — March 2026 — DRAFT v0.2

---

## 1. What are you trying to do?

Build an AI-assisted system that converts legacy SAS statistical pipelines to R or Python through a language-agnostic intermediate representation, with full traceability and automated verification that the converted code produces identical results.

The system decomposes SAS code into a graph-based blueprint that captures every variable, transformation, dependency, and data flow in a machine-readable format. Target language code is then generated from this blueprint — not translated line-by-line from the source. Verification uses synthetic benchmark datasets processed through both the original SAS pipeline and the converted code, with trace-level comparison at every transformation step.

The goal is to make statistical code conversion reproducible, transparent, and verifiable at scale — eliminating the risk that official statistics are compromised by translation errors, while simultaneously producing system documentation and a variable ontology that the Bureau currently lacks.

---

## 2. How is it done today, and what are the limits of current practice?

SAS-to-R/Python conversion at Census and across the federal statistical system is done through one of three approaches, all with significant limitations:

**Manual rewrite by subject matter experts.** Domain statisticians rewrite code by hand, referencing the SAS source. This is slow (months per pipeline), expensive (senior staff time), error-prone (no systematic verification), and produces no formal specification of what the original code actually does. Knowledge lives in the heads of the people who wrote the original SAS, many of whom have retired.

**LLM-based line-by-line translation.** Emerging practice is to feed SAS code to an LLM and ask for Python/R output. This produces plausible-looking code that frequently contains subtle errors — wrong variable types, mishandled missing values, incorrect join semantics, off-by-one errors in survey weight calculations. Without systematic verification, these errors propagate silently into official statistics.

**Commercial migration tools.** Tools like SAS-to-Python converters produce syntactically correct but semantically unverified output. They handle simple cases well but fail on complex survey methodology — the exact code that matters most at Census.

The fundamental limitation across all approaches: **none of them produce a verifiable specification of what the pipeline does, independent of any programming language.** Without that specification, there is no ground truth to validate against. You are comparing code to code, not code to intent.

---

## 3. What is new in your approach and why do you think it will be successful?

The core innovation is the graph-based intermediate representation — a language-agnostic blueprint of the statistical pipeline that serves as both the conversion specification and the verification oracle.

### 3.1 The Graph Blueprint

Instead of translating SAS to Python directly, the system first extracts a directed acyclic graph (DAG) that captures:

- Every variable and its type, units, valid ranges, and missing value semantics
- Every transformation: merges, filters, aggregations, imputations, weight calculations
- Data flow dependencies: which inputs feed which transformations, in what order
- State transitions: how variables change through the pipeline (raw → cleaned → imputed → weighted → published)
- SAS macro resolution: which macro invocations expand to which concrete operations, preserving the mapping between parameterized and instantiated logic

This graph is the specification. It can be inspected, validated, and diffed independently of any programming language.

### 3.2 Addressing SAS Macro Complexity

SAS's macro language is a text substitution preprocessor that generates code at runtime. This is the primary reason existing conversion tools fail on real Census pipelines — they parse the source text, but the actual executed logic is assembled dynamically from macro expansions, conditional compilation, and parameterized templates.

The extraction approach handles this in two passes:

1. **Macro-expanded extraction**: Process the SAS code through macro expansion (using SAS's own MPRINT/MLOGIC output or equivalent reconstruction), then extract the graph from the fully expanded code. This captures what actually executes.
2. **Template-level extraction**: Parse the unexpanded macro definitions to capture the parameterized logic patterns. This preserves the reusable structure for generating equivalent parameterized functions in the target language.

Both representations link to the same graph nodes — the expanded graph says "this is what happens," the template graph says "this is the pattern that generates what happens."

### 3.3 Trace-Based Verification

A synthetic benchmark dataset is processed through the original SAS pipeline, and the value of every variable at every transformation step is captured as a trace on the graph. The same benchmark is then processed through the generated target code, producing a second trace. Verification is a graph comparison: at every node in the DAG, do the SAS trace and the Python/R trace produce identical values (within floating-point tolerance)?

If they diverge, the exact transformation step where the divergence occurs is identified and reported. No ambiguity, no "it looks about right" — either the traces match or they don't, and you know exactly where they don't.

### 3.4 Self-Contained Experimental Design

Rather than depending on access to production SAS pipelines and subject matter expert validation, the proof of concept controls the entire experimental apparatus:

1. Design a reference graph that deliberately exercises the hard SAS features (DATA step variable creation, MERGE BY, RETAIN, FIRST./LAST., macro expansion, PROC SURVEYMEANS, missing value propagation, format-informed logic)
2. Generate SAS code FROM the reference graph — proving graph→code generation works
3. Extract the graph back FROM the generated SAS — proving code→graph extraction works
4. Round-trip validation: the extracted graph must match the reference graph
5. Generate R/Python from the extracted graph, validate via trace comparison

This is a compiler test suite strategy: the test harness exists before the compiler. Ground truth is the reference graph, not a human reviewer's opinion.

### 3.5 Why This Will Succeed

- The approach decomposes an intractable problem (verify entire pipeline equivalence) into tractable sub-problems (verify each transformation node independently)
- AI/LLM assistance is used where it excels — code generation from a well-specified blueprint — rather than where it fails (unsupervised translation of complex legacy code)
- The verification mechanism is deterministic and auditable, not probabilistic
- The intermediate representation is reusable: convert once to the graph, generate for any target language
- The self-contained experimental design eliminates institutional dependencies from the proof of concept

---

## 4. Who cares? If you succeed, what difference will it make?

### 4.1 Census Bureau

- Survey programs can migrate from SAS (expensive commercial license) to open-source R/Python with confidence that results are identical
- New hires (who increasingly know Python, not SAS) can work with converted code immediately rather than learning a legacy language
- Conversion risk — the fear that migration will break official statistics — is eliminated through verifiable traces

### 4.2 Federal Statistical System

- Every federal statistical agency running legacy SAS faces the same conversion problem: BLS, BEA, NCHS, NASS, EIA, and others
- A proven, verifiable conversion methodology developed at Census becomes a shared asset across the federal statistical system
- OMB and OSTP initiatives on open-source and reproducibility are directly supported

### 4.3 The Field

- Reproducibility crisis in survey methodology is partially attributable to opaque proprietary code that cannot be independently verified
- The graph blueprint makes statistical pipelines transparent and auditable by default
- Publishable methodology for AI-assisted code conversion with deterministic verification — a contribution to FCSM, JSM, and the broader research community

### 4.4 Variable Ontology — The Strategic Payoff

The accumulated graph data from converted pipelines produces a queryable ontology of Census variables: which raw inputs feed which transformations to produce which intermediate and published outputs, across surveys. Cross-survey variable mapping — understanding that ACS variable X and CPS variable Y measure the same concept through different pipelines — enables impact analysis, quality control, and data integration that is currently impossible at scale. Even a small fraction of Census pipelines converted this way produces a variable ontology more comprehensive than anything that exists today.

---

## 5. What are the costs? What is the schedule?

### 5.1 Schedule

| Phase | Timeline | Deliverable |
|-------|----------|-------------|
| Phase 0: Reference Graph Design | Week 1 | Design a reference DAG exercising key SAS features. Define graph schema, variable types, transformation vocabulary. |
| Phase 1: Graph↔SAS Round Trip | Weeks 1-2 | Generate SAS from reference graph. Build SAS→graph extractor. Validate round-trip graph equivalence. |
| Phase 2: Trace Framework | Weeks 2-3 | Build trace capture for SAS execution. Establish verification oracle with synthetic benchmark data. |
| Phase 3: Code Generation + Validation | Weeks 3-4 | Generate Python/R from graph. Capture traces. Compare against SAS traces. Iterate until full trace match. |
| Phase 4: Scale Assessment | Weeks 4-6 | Apply to a second, more complex pipeline. Identify what generalizes. Begin variable ontology construction. |
| Phase 5: Documentation + Publication | Weeks 6-8 | Methodology report. FCSM/JSM submission. Conversion playbook. |

Build velocity assumes AI-assisted development (Claude Code operating from specifications at Level 3-4 autonomy). The constraint is specification quality and validation review, not implementation time.

**What may extend the timeline**: Access to production SAS pipelines for Phase 4+ (institutional gates, not technical). The proof of concept (Phases 0-3) has zero institutional dependencies.

### 5.2 Resources Required

- AI lead (Brock Webb) as architect, specification author, and validation reviewer
- Compute: standard Census workstation + API access (Claude for code generation, Gemini Flash for structured extraction)
- No new infrastructure procurement — the system runs on existing hardware using open-source tools (Python, NetworkX, Git)
- Research support system (Seldon) for artifact tracking, provenance chains, and session state management — this project is Seldon's proof-of-concept use case

---

## 6. What are the risks? What are the mid-course corrections?

### 6.1 Technical Risks

**SAS semantics are underdocumented.** Some SAS behaviors (implicit type conversions, missing value propagation, PROC-specific edge cases) are poorly documented. Mid-course correction: the trace comparison surfaces these discrepancies empirically. When SAS and Python disagree, the graph blueprint provides the framework to investigate and resolve.

**SAS macro expansion may resist static analysis.** Macros that use dynamic variable names, CALL SYMPUT/SYMGET chains, or conditional compilation may require SAS-side MPRINT output rather than pure static parsing. Mid-course correction: the two-pass approach (Section 3.2) handles this — use SAS's own expansion output when static analysis is insufficient.

**Complex survey procedures may resist decomposition.** Certain SAS PROCs (e.g., PROC SURVEYMEANS with complex replicate weight specifications) may be difficult to represent as clean graph nodes. Mid-course correction: start with simpler pipelines, build vocabulary incrementally, treat complex PROCs as composite nodes refined later.

**Floating-point divergence.** Numerical precision differences between SAS and Python/R are expected. Mid-course correction: define tolerance thresholds per variable type and flag divergences that exceed tolerance rather than requiring bit-exact match.

### 6.2 Organizational Risks

**Survey program buy-in for production pipelines.** Programs may resist having their pipelines examined. Mid-course correction: the self-contained proof of concept requires zero organizational buy-in. Production pipeline access is Phase 4+, by which point the methodology is proven.

**Bus factor.** Single implementer. Mid-course correction: Seldon maintains project state (artifact graph, open tasks, provenance chains) across session interruptions. All specifications and design decisions are captured in the repository, not in the implementer's head. Any qualified engineer can resume from the specification.

---

## 7. How will you measure success? What are the deliverables?

### 7.1 Success Criteria

- Reference graph round-trip: graph→SAS→graph produces equivalent graphs
- Pilot pipeline: 100% trace match (within defined tolerance) between SAS and generated Python/R on synthetic benchmark data
- At least one previously unknown discrepancy or edge case discovered through trace analysis
- Second pipeline conversion demonstrates methodology generalizability

### 7.2 Deliverables

| Deliverable | Purpose |
|-------------|---------|
| Graph extraction engine (Python CLI) | Reusable tool for converting SAS pipelines to graph blueprints |
| Trace comparison framework | Verification infrastructure for any pipeline conversion |
| Pilot pipeline: graph + converted code + validation report | Proof of concept demonstrating the full methodology |
| Variable ontology (graph database) | Cross-survey variable mapping and documentation asset |
| Methodology paper (FCSM/JSM submission) | Peer-reviewed contribution to the federal statistical community |
| Conversion playbook | Repeatable process documentation for subsequent conversions |

---

## 8. What are the positive externalities?

The conversion process produces valuable assets beyond the converted code itself:

**System documentation.** The graph blueprint IS the system specification. For pipelines where documentation has been lost, is outdated, or never existed, the conversion process reconstructs it as a verifiable, machine-readable artifact.

**Bug discovery.** Trace-level comparison frequently reveals discrepancies in the original SAS code — edge cases, off-by-one errors, incorrect missing value handling — that have been silently producing slightly wrong results for years. Fixing these improves the quality of official statistics.

**Variable ontology.** The graph database of variables, their states, units, transformations, and relationships across pipelines becomes a queryable asset. Cross-survey variable mapping enables impact analysis, quality control, and data integration that is currently impossible at scale.

**AI-assisted development methodology.** The project establishes a pattern for how AI coding tools can be used within Census: specification-driven code generation with deterministic verification. This pattern is directly applicable to other modernization efforts.

**Institutional knowledge preservation.** Senior SAS programmers retiring take implicit knowledge of pipeline behavior with them. The graph blueprint captures that knowledge in a form that persists, is searchable, and is language-independent.
