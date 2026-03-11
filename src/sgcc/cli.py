"""SGCC command-line interface.

Entry point: sgcc
Command groups: graph
"""
from __future__ import annotations

import json
from pathlib import Path

import click

from .graph.store import GraphStore
from .graph.schema import DomainSchema


@click.group()
@click.version_option()
def sgcc() -> None:
    """SAS Graph Code Conversion — convert SAS pipelines to Python/R via graph IR."""


# ---------------------------------------------------------------------------
# graph command group
# ---------------------------------------------------------------------------

@sgcc.group()
def graph() -> None:
    """Graph operations: create, load, show, lineage, export."""


@graph.command("create")
@click.argument("name")
@click.option(
    "--config", default="config/research_domain.yaml", show_default=True,
    help="Path to domain YAML config file.",
)
@click.option("--output", "-o", default=None, help="Output JSONL path (default: <name>.jsonl).")
def graph_create(name: str, config: str, output: str | None) -> None:
    """Create a new empty graph with the given NAME and domain config."""
    schema = DomainSchema.load(Path(config))
    log_path = Path(output) if output else Path(f"{name}.jsonl")
    GraphStore(log_path=log_path)
    log_path.touch()
    click.echo(f"Created graph '{name}'")
    click.echo(f"Domain: {schema.name}")
    click.echo(f"Node types: {', '.join(schema.node_types)}")
    click.echo(f"Log: {log_path}")


@graph.command("load")
@click.argument("path")
def graph_load(path: str) -> None:
    """Load a graph from PATH (JSONL event log or JSON snapshot) and show stats."""
    store = _load_store(path)
    stats = store.stats()
    click.echo(f"Loaded: {path}")
    click.echo(f"  Nodes: {stats['total_nodes']}  Edges: {stats['total_edges']}")


@graph.command("show")
@click.argument("path")
def graph_show(path: str) -> None:
    """Display detailed statistics for the graph at PATH."""
    store = _load_store(path)
    stats = store.stats()
    click.echo(f"\nGraph: {path}")
    click.echo(f"  Total nodes : {stats['total_nodes']}")
    click.echo(f"  Total edges : {stats['total_edges']}")

    click.echo("\nNodes by type:")
    for t, count in sorted(stats["nodes_by_type"].items()):
        click.echo(f"  {t:20s}  {count}")

    click.echo("\nEdges by type:")
    for t, count in sorted(stats["edges_by_type"].items()):
        click.echo(f"  {t:24s}  {count}")


@graph.command("lineage")
@click.argument("path")
@click.argument("variable_name")
def graph_lineage(path: str, variable_name: str) -> None:
    """Trace VARIABLE_NAME back to all its ancestors in the graph at PATH."""
    store = _load_store(path)

    # Find node by id or by name attribute
    node_id = None
    if store.has_node(variable_name):
        node_id = variable_name
    else:
        for nid in store._graph.nodes:
            ndata = store.get_node(nid)
            if ndata.get("name") == variable_name:
                node_id = nid
                break

    if node_id is None:
        click.echo(f"Error: '{variable_name}' not found in graph.", err=True)
        raise SystemExit(1)

    ancestors = store.get_lineage(node_id)
    node_data = store.get_node(node_id)
    click.echo(f"\nLineage for '{variable_name}' (id={node_id}, type={node_data.get('node_type')})")

    if not ancestors:
        click.echo("  (no ancestors — root node)")
        return

    click.echo(f"  {len(ancestors)} ancestor(s):")
    for anc in sorted(ancestors):
        anc_data = store.get_node(anc)
        click.echo(f"  {anc:35s}  [{anc_data.get('node_type', '?')}]")


@graph.command("export")
@click.argument("path")
@click.option(
    "--format", "fmt", default="json", show_default=True,
    type=click.Choice(["json", "dot"]),
    help="Output format.",
)
@click.option("--output", "-o", default=None, help="Output file path.")
def graph_export(path: str, fmt: str, output: str | None) -> None:
    """Export graph at PATH to JSON snapshot or DOT format."""
    store = _load_store(path)
    stem = Path(path).stem
    out_path = Path(output) if output else Path(f"{stem}.{fmt}")

    if fmt == "json":
        with open(out_path, "w") as f:
            json.dump(store.to_json(), f, indent=2)
        click.echo(f"Exported JSON snapshot → {out_path}")

    elif fmt == "dot":
        try:
            import networkx as nx
            nx.drawing.nx_pydot.write_dot(store._graph, str(out_path))
            click.echo(f"Exported DOT → {out_path}")
        except ImportError:
            click.echo("Error: pydot or graphviz not installed. pip install pydot", err=True)
            raise SystemExit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_store(path: str) -> GraphStore:
    """Load a GraphStore from either a JSONL event log or JSON snapshot."""
    p = Path(path)
    if not p.exists():
        click.echo(f"Error: file not found: {path}", err=True)
        raise SystemExit(1)
    if p.suffix == ".json":
        return GraphStore.from_json_file(p)
    return GraphStore.load(p)


def main() -> None:
    sgcc()


if __name__ == "__main__":
    main()
