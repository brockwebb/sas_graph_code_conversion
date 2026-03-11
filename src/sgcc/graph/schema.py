"""DomainSchema: loads and validates the graph domain configuration from YAML.

The domain config defines what node types, edge types, and state transitions
are valid for a given project. This makes the graph model extensible without
code changes (per NFR-004: Seldon-compatible domain configuration).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml


class DomainSchema:
    """Validates nodes and edges against a domain YAML configuration."""

    def __init__(self, config: dict):
        self._config = config
        self._node_types: set[str] = set(config.get("node_types", []))
        self._edge_types: set[str] = set(config.get("edge_types", []))
        self._state_transitions: dict[str, list[str]] = config.get("state_transitions", {})
        self._transform_types: set[str] = set(config.get("transform_types", []))
        self._variable_states: set[str] = set(config.get("variable_states", []))

    @classmethod
    def load(cls, path: Path) -> "DomainSchema":
        """Load domain config from a YAML file."""
        with open(path) as f:
            config = yaml.safe_load(f)
        return cls(config)

    @classmethod
    def default(cls) -> "DomainSchema":
        """Load the bundled research_domain.yaml config."""
        default_path = Path(__file__).parent.parent.parent.parent / "config" / "research_domain.yaml"
        if not default_path.exists():
            # Fallback: try relative to cwd
            default_path = Path("config/research_domain.yaml")
        return cls.load(default_path)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_node_type(self, node_type: str) -> bool:
        return node_type in self._node_types

    def validate_edge_type(self, edge_type: str) -> bool:
        return edge_type in self._edge_types

    def validate_state_transition(self, from_state: str, to_state: str) -> bool:
        return to_state in self._state_transitions.get(from_state, [])

    def validate_transform_type(self, transform_type: str) -> bool:
        return transform_type in self._transform_types

    def assert_node_type(self, node_type: str) -> None:
        if not self.validate_node_type(node_type):
            raise ValueError(
                f"Invalid node type: {node_type!r}. "
                f"Valid types: {sorted(self._node_types)}"
            )

    def assert_edge_type(self, edge_type: str) -> None:
        if not self.validate_edge_type(edge_type):
            raise ValueError(
                f"Invalid edge type: {edge_type!r}. "
                f"Valid types: {sorted(self._edge_types)}"
            )

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def node_types(self) -> list[str]:
        return sorted(self._node_types)

    @property
    def edge_types(self) -> list[str]:
        return sorted(self._edge_types)

    @property
    def variable_states(self) -> list[str]:
        return list(self._config.get("variable_states", []))

    @property
    def transform_types(self) -> list[str]:
        return sorted(self._transform_types)

    @property
    def name(self) -> Optional[str]:
        return self._config.get("name")

    @property
    def description(self) -> Optional[str]:
        return self._config.get("description")
