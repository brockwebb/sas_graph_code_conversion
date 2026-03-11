"""GraphStore: NetworkX in-memory graph + JSONL append-only event log.

Architecture (per NFR-002, NFR-003):
- NetworkX DiGraph is the working representation (fast queries)
- JSONL event log is the source of truth (append-only, replayable)
- All mutations go through _append_event → graph update
- save() flushes the in-memory event list to disk
- load() replays events from disk to reconstruct the graph
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Optional

import networkx as nx

from .models import (
    AnyNode, GraphEdge, NodeType, VariableState,
    VALID_STATE_TRANSITIONS, node_from_dict,
)


class GraphStore:
    """In-memory graph backed by a JSONL event log.

    Usage::

        store = GraphStore(log_path=Path("mygraph.jsonl"))
        store.add_node(VariableNode(id="var_age", name="age", ...))
        store.add_edge(GraphEdge(id="e1", edge_type="derived_from", source="var_age_group", target="var_age"))
        store.save(store.log_path)

        # Later:
        store2 = GraphStore.load(Path("mygraph.jsonl"))
    """

    def __init__(self, log_path: Optional[Path] = None):
        self._graph: nx.DiGraph = nx.DiGraph()
        self._events: list[dict] = []
        self.log_path = log_path

    # ------------------------------------------------------------------
    # Internal event machinery
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

    def _append_event(self, event_type: str, payload: dict) -> None:
        event = {
            "event_type": event_type,
            "timestamp": self._now(),
            "payload": payload,
        }
        self._events.append(event)
        if self.log_path:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(event) + "\n")

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_node(self, node: AnyNode) -> None:
        """Add a node to the graph. Raises if node ID already exists."""
        if self._graph.has_node(node.id):
            raise ValueError(f"Node {node.id!r} already exists")
        data = node.model_dump()
        self._graph.add_node(node.id, **data)
        self._append_event("node_created", data)

    def update_node(self, node_id: str, updates: dict[str, Any]) -> None:
        """Patch arbitrary attributes on an existing node."""
        if not self._graph.has_node(node_id):
            raise KeyError(f"Node {node_id!r} not found")
        self._graph.nodes[node_id].update(updates)
        self._append_event("node_updated", {"id": node_id, "updates": updates})

    def get_node(self, node_id: str) -> dict:
        """Return node attribute dict. Raises KeyError if not found."""
        if not self._graph.has_node(node_id):
            raise KeyError(f"Node {node_id!r} not found")
        return dict(self._graph.nodes[node_id])

    def has_node(self, node_id: str) -> bool:
        return self._graph.has_node(node_id)

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def add_edge(self, edge: GraphEdge) -> None:
        """Add a directed edge. Source and target nodes must exist."""
        if not self._graph.has_node(edge.source):
            raise KeyError(f"Source node {edge.source!r} not found")
        if not self._graph.has_node(edge.target):
            raise KeyError(f"Target node {edge.target!r} not found")
        data = edge.model_dump()
        self._graph.add_edge(edge.source, edge.target, **data)
        self._append_event("edge_created", data)

    def remove_edge(self, source: str, target: str, edge_id: str) -> None:
        if not self._graph.has_edge(source, target):
            raise KeyError(f"Edge {source!r} → {target!r} not found")
        self._graph.remove_edge(source, target)
        self._append_event("edge_removed", {"id": edge_id, "source": source, "target": target})

    # ------------------------------------------------------------------
    # Variable state machine
    # ------------------------------------------------------------------

    def transition_state(self, node_id: str, new_state: VariableState) -> None:
        """Advance a Variable node through the state machine.

        Raises ValueError on invalid transitions or wrong node type.
        """
        node_data = self.get_node(node_id)
        if node_data.get("node_type") != NodeType.VARIABLE.value:
            raise ValueError(f"Node {node_id!r} is not a Variable (got {node_data.get('node_type')!r})")
        current = VariableState(node_data["state"])
        allowed = VALID_STATE_TRANSITIONS[current]
        if new_state not in allowed:
            raise ValueError(
                f"Invalid state transition for {node_id!r}: "
                f"{current.value!r} → {new_state.value!r}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        self._graph.nodes[node_id]["state"] = new_state.value
        self._append_event("state_changed", {
            "id": node_id, "from": current.value, "to": new_state.value,
        })

    # ------------------------------------------------------------------
    # Query operations
    # ------------------------------------------------------------------

    def get_neighbors(self, node_id: str, direction: str = "both") -> list[str]:
        """Return neighbor node IDs. direction: 'in', 'out', or 'both'."""
        if not self._graph.has_node(node_id):
            raise KeyError(f"Node {node_id!r} not found")
        if direction == "out":
            return list(self._graph.successors(node_id))
        elif direction == "in":
            return list(self._graph.predecessors(node_id))
        else:
            return list(set(self._graph.successors(node_id)) | set(self._graph.predecessors(node_id)))

    def get_lineage(self, node_id: str) -> list[str]:
        """Return all ancestors of a node (transitive predecessors in the DAG)."""
        if not self._graph.has_node(node_id):
            raise KeyError(f"Node {node_id!r} not found")
        return list(nx.ancestors(self._graph, node_id))

    def get_edges(self, source: Optional[str] = None, target: Optional[str] = None) -> list[dict]:
        """Return edge attribute dicts, optionally filtered by source or target."""
        results = []
        for u, v, data in self._graph.edges(data=True):
            if source is not None and u != source:
                continue
            if target is not None and v != target:
                continue
            results.append(dict(data))
        return results

    def stats(self) -> dict:
        """Return node and edge counts by type."""
        node_counts: dict[str, int] = {}
        for _, d in self._graph.nodes(data=True):
            t = d.get("node_type", "unknown")
            node_counts[t] = node_counts.get(t, 0) + 1

        edge_counts: dict[str, int] = {}
        for _, _, d in self._graph.edges(data=True):
            t = d.get("edge_type", "unknown")
            edge_counts[t] = edge_counts.get(t, 0) + 1

        return {
            "total_nodes": self._graph.number_of_nodes(),
            "total_edges": self._graph.number_of_edges(),
            "nodes_by_type": node_counts,
            "edges_by_type": edge_counts,
        }

    # ------------------------------------------------------------------
    # Persistence: JSONL event log
    # ------------------------------------------------------------------

    def save(self, path: Path) -> None:
        """Write all in-memory events to a JSONL file (overwrites if exists)."""
        with open(path, "w") as f:
            for event in self._events:
                f.write(json.dumps(event) + "\n")

    @classmethod
    def load(cls, path: Path) -> "GraphStore":
        """Reconstruct a GraphStore by replaying events from a JSONL file."""
        store = cls(log_path=None)
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                store._events.append(event)
                cls._replay_event(store, event)
        store.log_path = path
        return store

    @staticmethod
    def _replay_event(store: "GraphStore", event: dict) -> None:
        etype = event["event_type"]
        p = event["payload"]
        if etype == "node_created":
            store._graph.add_node(p["id"], **p)
        elif etype == "node_updated":
            if store._graph.has_node(p["id"]):
                store._graph.nodes[p["id"]].update(p["updates"])
        elif etype == "edge_created":
            store._graph.add_edge(p["source"], p["target"], **p)
        elif etype == "edge_removed":
            if store._graph.has_edge(p["source"], p["target"]):
                store._graph.remove_edge(p["source"], p["target"])
        elif etype == "state_changed":
            if store._graph.has_node(p["id"]):
                store._graph.nodes[p["id"]]["state"] = p["to"]

    # ------------------------------------------------------------------
    # Persistence: JSON snapshot (for reference graph files)
    # ------------------------------------------------------------------

    def to_json(self) -> dict:
        """Export graph as a JSON snapshot (nodes + edges lists)."""
        nodes = [dict(self._graph.nodes[n]) for n in self._graph.nodes]
        edges = [dict(d) for _, _, d in self._graph.edges(data=True)]
        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

    @classmethod
    def from_json(cls, data: dict) -> "GraphStore":
        """Load a graph from a JSON snapshot (does not populate event log)."""
        store = cls()
        for node_data in data.get("nodes", []):
            store._graph.add_node(node_data["id"], **node_data)
        for edge_data in data.get("edges", []):
            store._graph.add_edge(edge_data["source"], edge_data["target"], **edge_data)
        return store

    @classmethod
    def from_json_file(cls, path: Path) -> "GraphStore":
        with open(path) as f:
            return cls.from_json(json.load(f))
