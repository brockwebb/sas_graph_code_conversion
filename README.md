# sas_graph_code_conversion

Graph-based SAS code conversion to R/Python with trace-level verification.

Converts legacy SAS statistical pipelines through a language-agnostic intermediate representation (DAG), not line-by-line translation. Verification compares execution traces at every transformation node.

## Status

**Early development** — Design and specification phase.

## Documentation

- [CLAUDE.md](CLAUDE.md) — Project context for AI assistants
- [docs/proposal.md](docs/proposal.md) — Project proposal (Heilmeier catechism)
- [docs/requirements/srs.md](docs/requirements/srs.md) — System Requirements Specification
- [docs/design/reference_graph_schema.md](docs/design/reference_graph_schema.md) — Graph schema and reference pipeline design

## License

MIT
