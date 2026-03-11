"""Tests for context_gen_v0.py experiment.

Verifies:
- Graph loads without error
- SRS parsing finds ≥40 FRs
- Context slice extraction returns nodes and edges
- Slice is smaller than the full graph
- Generated task file exists, is non-empty, and contains FR-001 text
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Allow import from experiments/ and src/
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "experiments"))

import context_gen_v0 as cg


@pytest.fixture(scope="module")
def store():
    return cg.load_graph()


@pytest.fixture(scope="module")
def fr_map():
    return cg.parse_srs()


@pytest.fixture(scope="module")
def context(store):
    return cg.extract_fr001_context(store)


@pytest.fixture(scope="module")
def task_file(fr_map, context, store):
    implemented = cg.detect_implemented()
    path = cg.generate_task_file(fr_map, implemented, context, store)
    return path


# ---------------------------------------------------------------------------
# Graph loading
# ---------------------------------------------------------------------------

def test_graph_loads_without_error(store):
    assert store is not None
    assert store._graph.number_of_nodes() > 0


def test_graph_has_expected_node_count(store):
    # Reference pipeline has 65 nodes
    assert store._graph.number_of_nodes() == 65


# ---------------------------------------------------------------------------
# SRS parsing
# ---------------------------------------------------------------------------

def test_srs_parses_at_least_25_frs(fr_map):
    # SRS has 27 FRs with gaps in numbering (FR-001..007, 010..015, 020..024, 030..032, 040..042, 050..052)
    assert len(fr_map) >= 25, f"Only found {len(fr_map)} FRs in SRS"


def test_fr001_is_present(fr_map):
    assert "001" in fr_map
    assert "DATA step" in fr_map["001"] or "parse" in fr_map["001"].lower()


def test_fr007_is_present(fr_map):
    assert "007" in fr_map


def test_fr050_is_present(fr_map):
    assert "050" in fr_map


# ---------------------------------------------------------------------------
# Context slice extraction
# ---------------------------------------------------------------------------

def test_context_slice_has_nodes(context):
    assert len(context["nodes"]) > 0


def test_context_slice_has_edges(context):
    assert len(context["edges"]) > 0


def test_context_slice_is_smaller_than_full_graph(store, context):
    total_nodes = store._graph.number_of_nodes()
    slice_nodes = len(context["nodes"])
    assert slice_nodes < total_nodes, (
        f"Slice ({slice_nodes}) should be smaller than full graph ({total_nodes})"
    )


def test_context_slice_contains_datastep_nodes(context):
    datastep_nodes = [n for n in context["nodes"] if n.get("node_type") == "DataStep"]
    assert len(datastep_nodes) > 0


def test_context_slice_contains_variable_nodes(context):
    var_nodes = [n for n in context["nodes"] if n.get("node_type") == "Variable"]
    assert len(var_nodes) > 0


def test_context_slice_all_edge_endpoints_in_slice(context):
    """Every edge in the slice should have both endpoints in the slice."""
    node_ids = {n["id"] for n in context["nodes"]}
    for edge in context["edges"]:
        assert edge["source"] in node_ids, f"Edge source {edge['source']!r} not in slice"
        assert edge["target"] in node_ids, f"Edge target {edge['target']!r} not in slice"


# ---------------------------------------------------------------------------
# Generated task file
# ---------------------------------------------------------------------------

def test_task_file_exists(task_file):
    assert task_file.exists(), f"Task file not created: {task_file}"


def test_task_file_is_non_empty(task_file):
    assert task_file.stat().st_size > 0


def test_task_file_contains_fr001_text(task_file):
    content = task_file.read_text()
    assert "FR-001" in content


def test_task_file_contains_implementation_target(task_file):
    content = task_file.read_text()
    assert "data_step_parser.py" in content


def test_task_file_contains_acceptance_criteria(task_file):
    content = task_file.read_text()
    assert "Acceptance Criteria" in content


def test_task_file_contains_context_slice_stats(task_file):
    content = task_file.read_text()
    # Should mention node count
    assert "nodes" in content.lower()
    assert "edges" in content.lower()
