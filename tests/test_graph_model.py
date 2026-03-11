"""Tests for the SGCC graph data model, store, and schema.

Coverage:
- Node creation for all 8 types with attribute validation
- Edge creation with type validation (reject invalid types)
- Variable state machine: valid transitions succeed, invalid raise errors
- GraphStore: JSONL serialize → reload → graph equivalence
- Reference pipeline: load from JSON, verify node/edge counts, lineage queries
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from sgcc.graph.models import (
    DatasetNode, DataStepNode, DataType, EdgeType, GraphEdge,
    MacroInvocationNode, MacroNode, NodeType, PipelineNode, ProcNode,
    TransformNode, TransformType, VariableNode, VariableState,
    VALID_STATE_TRANSITIONS, node_from_dict,
)
from sgcc.graph.store import GraphStore
from sgcc.graph.schema import DomainSchema

REFERENCE_GRAPH_PATH = Path(__file__).parent / "reference_graphs" / "pilot_survey_pipeline.json"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "research_domain.yaml"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_store() -> GraphStore:
    return GraphStore()


@pytest.fixture
def populated_store() -> GraphStore:
    """A small store with a few nodes and edges for reuse."""
    store = GraphStore()
    store.add_node(VariableNode(id="var_age", name="age", data_type=DataType.NUMERIC,
                                label="Age in years", state=VariableState.RAW))
    store.add_node(VariableNode(id="var_age_group", name="age_group", data_type=DataType.NUMERIC,
                                label="Age group code", state=VariableState.DERIVED))
    store.add_node(TransformNode(id="xfm_recode_age", operation=TransformType.CONDITIONAL_ASSIGN,
                                 description="Recode age into age_group"))
    store.add_edge(GraphEdge(id="e1", edge_type=EdgeType.DERIVED_FROM,
                             source="var_age_group", target="var_age"))
    store.add_edge(GraphEdge(id="e2", edge_type=EdgeType.CONSUMES,
                             source="xfm_recode_age", target="var_age"))
    store.add_edge(GraphEdge(id="e3", edge_type=EdgeType.PRODUCES,
                             source="xfm_recode_age", target="var_age_group"))
    return store


@pytest.fixture
def reference_store() -> GraphStore:
    with open(REFERENCE_GRAPH_PATH) as f:
        data = json.load(f)
    return GraphStore.from_json(data)


# ---------------------------------------------------------------------------
# Node creation — all 8 types
# ---------------------------------------------------------------------------

class TestNodeCreation:

    def test_variable_node(self):
        node = VariableNode(
            id="var_income", name="income", data_type=DataType.NUMERIC,
            length=8, label="Annual income", state=VariableState.RAW,
            units="USD_annual",
        )
        assert node.id == "var_income"
        assert node.node_type == NodeType.VARIABLE
        assert node.data_type == DataType.NUMERIC
        assert node.state == VariableState.RAW

    def test_variable_node_character(self):
        node = VariableNode(id="var_pid", name="person_id", data_type=DataType.CHARACTER, length=12)
        assert node.data_type == DataType.CHARACTER
        assert node.missing_semantics == "SAS_numeric_missing"  # default — tests SRS section 3.3

    def test_dataset_node(self):
        node = DatasetNode(id="ds_raw", name="raw_survey",
                           description="Raw survey", observation_unit="person",
                           key_variables=["person_id"])
        assert node.node_type == NodeType.DATASET
        assert "person_id" in node.key_variables

    def test_transform_node(self):
        node = TransformNode(id="xfm_sort", operation=TransformType.SORT,
                             description="Sort by fips_code",
                             parameters={"by": ["fips_code"]})
        assert node.node_type == NodeType.TRANSFORM
        assert node.operation == TransformType.SORT
        assert node.parameters["by"] == ["fips_code"]

    def test_macro_node(self):
        node = MacroNode(id="mac_clean", name="clean_var",
                         parameters=["varname", "min_val", "max_val"])
        assert node.node_type == NodeType.MACRO
        assert len(node.parameters) == 3

    def test_macro_invocation_node(self):
        node = MacroInvocationNode(id="mac_inv_1", macro_ref="mac_clean",
                                   actual_parameters={"varname": "income", "min_val": "0", "max_val": "9999999"})
        assert node.node_type == NodeType.MACRO_INVOCATION
        assert node.actual_parameters["varname"] == "income"

    def test_proc_node(self):
        node = ProcNode(id="proc_sort_1", proc_type="SORT",
                        by_variables=["fips_code"],
                        output_datasets=["work.survey_sorted"])
        assert node.node_type == NodeType.PROC
        assert node.proc_type == "SORT"

    def test_data_step_node(self):
        node = DataStepNode(id="step_clean",
                            input_datasets=["work.raw"], output_dataset="work.clean")
        assert node.node_type == NodeType.DATA_STEP
        assert node.output_dataset == "work.clean"

    def test_pipeline_node(self):
        node = PipelineNode(id="pipe_main", name="Main Pipeline",
                            source_files=["01_ingest.sas", "02_clean.sas"])
        assert node.node_type == NodeType.PIPELINE
        assert len(node.source_files) == 2

    def test_node_serialization_roundtrip(self):
        node = VariableNode(id="var_x", name="x", data_type=DataType.NUMERIC,
                            state=VariableState.CLEANED, label="Test var")
        data = node.model_dump()
        recovered = node_from_dict(data)
        assert recovered.id == node.id
        assert recovered.state == node.state

    def test_node_from_dict_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown node_type"):
            node_from_dict({"id": "x", "node_type": "Banana"})


# ---------------------------------------------------------------------------
# Edge creation and type validation
# ---------------------------------------------------------------------------

class TestEdgeCreation:

    def test_valid_edge_types(self, empty_store):
        empty_store.add_node(VariableNode(id="a", name="a"))
        empty_store.add_node(VariableNode(id="b", name="b"))
        for etype in EdgeType:
            edge = GraphEdge(id=f"e_{etype.value}", edge_type=etype, source="a", target="b")
            assert edge.edge_type == etype.value

    def test_invalid_edge_type_raises(self):
        with pytest.raises(ValueError):
            GraphEdge(id="e_bad", edge_type="not_a_real_edge_type", source="a", target="b")

    def test_add_edge_missing_source_raises(self, empty_store):
        empty_store.add_node(VariableNode(id="b", name="b"))
        with pytest.raises(KeyError, match="Source node"):
            empty_store.add_edge(GraphEdge(id="e1", edge_type=EdgeType.DERIVED_FROM,
                                           source="nonexistent", target="b"))

    def test_add_edge_missing_target_raises(self, empty_store):
        empty_store.add_node(VariableNode(id="a", name="a"))
        with pytest.raises(KeyError, match="Target node"):
            empty_store.add_edge(GraphEdge(id="e1", edge_type=EdgeType.DERIVED_FROM,
                                           source="a", target="nonexistent"))

    def test_duplicate_node_raises(self, empty_store):
        empty_store.add_node(VariableNode(id="dup", name="dup"))
        with pytest.raises(ValueError, match="already exists"):
            empty_store.add_node(VariableNode(id="dup", name="dup"))

    def test_edge_attributes(self, empty_store):
        empty_store.add_node(DatasetNode(id="ds_a", name="a"))
        empty_store.add_node(DatasetNode(id="ds_b", name="b"))
        edge = GraphEdge(id="e_merge", edge_type=EdgeType.MERGED_WITH,
                         source="ds_a", target="ds_b",
                         attributes={"join_key": "fips_code"})
        empty_store.add_edge(edge)
        edges = empty_store.get_edges(source="ds_a")
        assert len(edges) == 1
        assert edges[0]["attributes"]["join_key"] == "fips_code"


# ---------------------------------------------------------------------------
# Variable state machine
# ---------------------------------------------------------------------------

class TestStateMachine:

    def test_valid_transitions(self, empty_store):
        empty_store.add_node(VariableNode(id="v", name="v", state=VariableState.RAW))
        # raw → cleaned → imputed → derived → aggregated → published
        for from_state, to_state in [
            (VariableState.RAW,       VariableState.CLEANED),
            (VariableState.CLEANED,   VariableState.IMPUTED),
            (VariableState.IMPUTED,   VariableState.DERIVED),
            (VariableState.DERIVED,   VariableState.AGGREGATED),
            (VariableState.AGGREGATED, VariableState.PUBLISHED),
        ]:
            node_data = empty_store.get_node("v")
            # Manually set state so we can test each leg of the chain
            empty_store._graph.nodes["v"]["state"] = from_state.value
            empty_store.transition_state("v", to_state)
            assert empty_store.get_node("v")["state"] == to_state.value

    def test_invalid_transition_raises(self, empty_store):
        empty_store.add_node(VariableNode(id="v2", name="v2", state=VariableState.PUBLISHED))
        with pytest.raises(ValueError, match="Invalid state transition"):
            empty_store.transition_state("v2", VariableState.RAW)

    def test_transition_on_non_variable_raises(self, empty_store):
        empty_store.add_node(DatasetNode(id="ds_x", name="x"))
        with pytest.raises(ValueError, match="not a Variable"):
            empty_store.transition_state("ds_x", VariableState.CLEANED)

    def test_all_valid_transitions_defined(self):
        for state in VariableState:
            assert state in VALID_STATE_TRANSITIONS, f"Missing transitions for {state}"

    def test_published_has_no_outgoing_transitions(self):
        assert VALID_STATE_TRANSITIONS[VariableState.PUBLISHED] == []

    def test_transition_recorded_in_events(self, empty_store):
        empty_store.add_node(VariableNode(id="ev", name="ev", state=VariableState.RAW))
        empty_store.transition_state("ev", VariableState.VALIDATED)
        state_events = [e for e in empty_store._events if e["event_type"] == "state_changed"]
        assert len(state_events) == 1
        assert state_events[0]["payload"]["from"] == "raw"
        assert state_events[0]["payload"]["to"] == "validated"


# ---------------------------------------------------------------------------
# GraphStore: JSONL serialize / reload
# ---------------------------------------------------------------------------

class TestJSONLRoundtrip:

    def test_save_and_load(self, populated_store):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_graph.jsonl"
            populated_store.save(path)

            loaded = GraphStore.load(path)

            assert loaded._graph.number_of_nodes() == populated_store._graph.number_of_nodes()
            assert loaded._graph.number_of_edges() == populated_store._graph.number_of_edges()

    def test_node_attributes_preserved(self, populated_store):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_graph.jsonl"
            populated_store.save(path)
            loaded = GraphStore.load(path)

            orig = populated_store.get_node("var_age")
            reloaded = loaded.get_node("var_age")
            assert orig["name"] == reloaded["name"]
            assert orig["state"] == reloaded["state"]
            assert orig["label"] == reloaded["label"]

    def test_edge_types_preserved(self, populated_store):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_graph.jsonl"
            populated_store.save(path)
            loaded = GraphStore.load(path)

            edges = loaded.get_edges(source="var_age_group", target="var_age")
            assert len(edges) == 1
            assert edges[0]["edge_type"] == EdgeType.DERIVED_FROM.value

    def test_event_count_preserved(self, populated_store):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_graph.jsonl"
            populated_store.save(path)
            loaded = GraphStore.load(path)
            assert len(loaded._events) == len(populated_store._events)

    def test_state_change_replayed(self):
        store = GraphStore()
        store.add_node(VariableNode(id="v_sc", name="v_sc", state=VariableState.RAW))
        store.transition_state("v_sc", VariableState.VALIDATED)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state_test.jsonl"
            store.save(path)
            loaded = GraphStore.load(path)
            assert loaded.get_node("v_sc")["state"] == VariableState.VALIDATED.value


# ---------------------------------------------------------------------------
# Reference pipeline: load, count, lineage
# ---------------------------------------------------------------------------

class TestReferencePipeline:

    def test_loads_without_error(self, reference_store):
        assert reference_store._graph.number_of_nodes() > 0

    def test_node_count(self, reference_store):
        stats = reference_store.stats()
        # Reference pipeline has 33 variable nodes
        assert stats["nodes_by_type"].get("Variable", 0) >= 30
        # At least 7 datasets
        assert stats["nodes_by_type"].get("Dataset", 0) >= 7
        # At least 10 transforms
        assert stats["nodes_by_type"].get("Transform", 0) >= 10

    def test_edge_count(self, reference_store):
        stats = reference_store.stats()
        assert stats["total_edges"] >= 50
        # Should have all major edge types
        assert "contains" in stats["edges_by_type"]
        assert "derived_from" in stats["edges_by_type"]
        assert "produces" in stats["edges_by_type"]
        assert "consumes" in stats["edges_by_type"]
        assert "sequenced_before" in stats["edges_by_type"]

    def test_variable_lineage_poverty_ratio(self, reference_store):
        """poverty_ratio lineage includes the transform that produces it and its upstream chain.

        Note: derived_from edges point child→parent (opposite of data flow), so the full
        ancestor set contains transforms reachable via the mixed-direction graph.
        """
        ancestors = reference_store.get_lineage("var_poverty_ratio")
        # The transform that produces poverty_ratio must be an ancestor
        assert "xfm_derive_poverty_ratio" in ancestors
        # The hotdeck transform is upstream via sequenced_before chain
        assert "xfm_hotdeck_income" in ancestors

    def test_variable_lineage_income_imputed(self, reference_store):
        """income_imputed should trace back through income_clean to income."""
        ancestors = reference_store.get_lineage("var_income_imputed")
        assert "var_income_clean" in ancestors
        assert "var_income" in ancestors

    def test_variable_lineage_root_has_no_ancestors(self, reference_store):
        """A true root node (no incoming edges) has an empty ancestor set."""
        # The Pipeline node has no incoming edges — it is a true root in the graph
        ancestors = reference_store.get_lineage("pipeline_pilot")
        assert len(ancestors) == 0

    def test_neighbors_income_imputed(self, reference_store):
        """income_imputed should have outgoing neighbors (nodes that consume it)."""
        out_neighbors = reference_store.get_neighbors("var_income_imputed", direction="out")
        # poverty_ratio derives from income_imputed
        assert len(out_neighbors) > 0

    def test_get_node_returns_correct_type(self, reference_store):
        node = reference_store.get_node("var_income")
        assert node["node_type"] == NodeType.VARIABLE.value
        assert node["name"] == "income"

    def test_get_dataset_node(self, reference_store):
        node = reference_store.get_node("ds_raw_survey")
        assert node["node_type"] == NodeType.DATASET.value

    def test_get_transform_node(self, reference_store):
        node = reference_store.get_node("xfm_hotdeck_income")
        assert node["node_type"] == NodeType.TRANSFORM.value
        assert node["operation"] == TransformType.RETAIN.value

    def test_missing_node_raises(self, reference_store):
        with pytest.raises(KeyError):
            reference_store.get_node("nonexistent_node_xyz")

    def test_json_snapshot_roundtrip(self, reference_store):
        snapshot = reference_store.to_json()
        recovered = GraphStore.from_json(snapshot)
        assert recovered._graph.number_of_nodes() == reference_store._graph.number_of_nodes()
        assert recovered._graph.number_of_edges() == reference_store._graph.number_of_edges()


# ---------------------------------------------------------------------------
# DomainSchema
# ---------------------------------------------------------------------------

class TestDomainSchema:

    @pytest.fixture
    def schema(self):
        return DomainSchema.load(CONFIG_PATH)

    def test_loads(self, schema):
        assert schema.name == "sas_graph_code_conversion"

    def test_all_node_types_present(self, schema):
        for node_type in NodeType:
            assert schema.validate_node_type(node_type.value), \
                f"Node type {node_type.value!r} missing from schema"

    def test_all_edge_types_present(self, schema):
        for edge_type in EdgeType:
            assert schema.validate_edge_type(edge_type.value), \
                f"Edge type {edge_type.value!r} missing from schema"

    def test_invalid_node_type(self, schema):
        assert not schema.validate_node_type("Banana")

    def test_invalid_edge_type(self, schema):
        assert not schema.validate_edge_type("banana_relationship")

    def test_state_transitions_valid(self, schema):
        assert schema.validate_state_transition("raw", "cleaned")
        assert schema.validate_state_transition("cleaned", "imputed")
        assert schema.validate_state_transition("imputed", "derived")

    def test_state_transitions_invalid(self, schema):
        assert not schema.validate_state_transition("published", "raw")
        assert not schema.validate_state_transition("aggregated", "raw")

    def test_assert_invalid_node_type_raises(self, schema):
        with pytest.raises(ValueError, match="Invalid node type"):
            schema.assert_node_type("NotAType")

    def test_assert_invalid_edge_type_raises(self, schema):
        with pytest.raises(ValueError, match="Invalid edge type"):
            schema.assert_edge_type("not_an_edge")
