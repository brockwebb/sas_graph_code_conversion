"""Pydantic v2 models for all graph node types, edge types, and enumerations.

Node types and edge types are defined by the SRS (Section 3) and the reference
graph schema doc (Section 3). This module is the single source of truth for the
data model.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class NodeType(str, Enum):
    VARIABLE = "Variable"
    DATASET = "Dataset"
    TRANSFORM = "Transform"
    MACRO = "Macro"
    MACRO_INVOCATION = "MacroInvocation"
    PROC = "Proc"
    DATA_STEP = "DataStep"
    PIPELINE = "Pipeline"


class EdgeType(str, Enum):
    DERIVED_FROM = "derived_from"
    CONTAINS = "contains"
    PRODUCES = "produces"
    CONSUMES = "consumes"
    OUTPUTS = "outputs"
    INPUTS = "inputs"
    EXPANDS_TO = "expands_to"
    DEFINED_BY = "defined_by"
    SEQUENCED_BEFORE = "sequenced_before"
    MERGED_WITH = "merged_with"
    FILTERED_BY = "filtered_by"


class VariableState(str, Enum):
    RAW = "raw"
    VALIDATED = "validated"
    CLEANED = "cleaned"
    IMPUTED = "imputed"
    DERIVED = "derived"
    WEIGHTED = "weighted"
    AGGREGATED = "aggregated"
    PUBLISHED = "published"


class TransformType(str, Enum):
    ASSIGN = "assign"
    CONDITIONAL_ASSIGN = "conditional_assign"
    RETAIN = "retain"
    MERGE = "merge"
    SET = "set"
    SORT = "sort"
    AGGREGATE = "aggregate"
    FREQUENCY = "frequency"
    SURVEY_STAT = "survey_stat"
    SQL_QUERY = "sql_query"
    TRANSPOSE = "transpose"
    FORMAT_APPLY = "format_apply"
    ARRAY_OP = "array_op"
    BY_GROUP = "by_group"
    MACRO_EXPAND = "macro_expand"
    MISSING_PROPAGATE = "missing_propagate"


class DataType(str, Enum):
    NUMERIC = "numeric"
    CHARACTER = "character"


# ---------------------------------------------------------------------------
# Valid state transitions for Variable state machine
# raw → validated → cleaned → imputed → derived → weighted → aggregated → published
# Not prescriptive — captures what the SAS code actually does.
# ---------------------------------------------------------------------------

VALID_STATE_TRANSITIONS: dict[VariableState, list[VariableState]] = {
    VariableState.RAW: [
        VariableState.VALIDATED, VariableState.CLEANED, VariableState.DERIVED,
        VariableState.IMPUTED, VariableState.WEIGHTED, VariableState.AGGREGATED,
        VariableState.PUBLISHED,
    ],
    VariableState.VALIDATED: [
        VariableState.CLEANED, VariableState.DERIVED, VariableState.IMPUTED,
    ],
    VariableState.CLEANED: [
        VariableState.IMPUTED, VariableState.DERIVED, VariableState.WEIGHTED,
    ],
    VariableState.IMPUTED: [
        VariableState.DERIVED, VariableState.WEIGHTED, VariableState.AGGREGATED,
    ],
    VariableState.DERIVED: [
        VariableState.WEIGHTED, VariableState.AGGREGATED, VariableState.PUBLISHED,
    ],
    VariableState.WEIGHTED: [
        VariableState.AGGREGATED, VariableState.PUBLISHED,
    ],
    VariableState.AGGREGATED: [
        VariableState.PUBLISHED,
    ],
    VariableState.PUBLISHED: [],
}


# ---------------------------------------------------------------------------
# Common sub-models
# ---------------------------------------------------------------------------

class ValidRange(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None


class SASProvenance(BaseModel):
    """Optional SAS-specific metadata. Lives outside the core schema per design principle 3."""
    source_file: Optional[str] = None
    line_range: Optional[tuple[int, int]] = None
    sas_construct: Optional[str] = None
    library: Optional[str] = None
    sas_name: Optional[str] = None
    data_step: Optional[str] = None
    uses_retain: bool = False
    uses_by_group: bool = False


# ---------------------------------------------------------------------------
# Node models
# ---------------------------------------------------------------------------

class NodeBase(BaseModel):
    id: str
    node_type: NodeType
    sas_provenance: Optional[SASProvenance] = None

    model_config = {"use_enum_values": True}


class VariableNode(NodeBase):
    node_type: NodeType = NodeType.VARIABLE
    name: str
    data_type: DataType = DataType.NUMERIC
    length: Optional[int] = None
    label: Optional[str] = None
    missing_semantics: str = "SAS_numeric_missing"
    valid_range: Optional[ValidRange] = None
    state: VariableState = VariableState.RAW
    units: Optional[str] = None


class DatasetNode(NodeBase):
    node_type: NodeType = NodeType.DATASET
    name: str
    description: Optional[str] = None
    observation_unit: Optional[str] = None
    key_variables: list[str] = Field(default_factory=list)


class TransformNode(NodeBase):
    node_type: NodeType = NodeType.TRANSFORM
    operation: TransformType
    description: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class MacroNode(NodeBase):
    node_type: NodeType = NodeType.MACRO
    name: str
    parameters: list[str] = Field(default_factory=list)
    expansion_template: Optional[str] = None


class MacroInvocationNode(NodeBase):
    node_type: NodeType = NodeType.MACRO_INVOCATION
    macro_ref: str
    actual_parameters: dict[str, str] = Field(default_factory=dict)
    expanded_code_ref: Optional[str] = None


class ProcNode(NodeBase):
    node_type: NodeType = NodeType.PROC
    proc_type: str
    options: dict[str, Any] = Field(default_factory=dict)
    by_variables: list[str] = Field(default_factory=list)
    class_variables: list[str] = Field(default_factory=list)
    output_datasets: list[str] = Field(default_factory=list)


class DataStepNode(NodeBase):
    node_type: NodeType = NodeType.DATA_STEP
    input_datasets: list[str] = Field(default_factory=list)
    output_dataset: Optional[str] = None
    where_clause: Optional[str] = None


class PipelineNode(NodeBase):
    node_type: NodeType = NodeType.PIPELINE
    name: str
    source_files: list[str] = Field(default_factory=list)
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Edge model
# ---------------------------------------------------------------------------

class GraphEdge(BaseModel):
    id: str
    edge_type: EdgeType
    source: str
    target: str
    attributes: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}


# ---------------------------------------------------------------------------
# Union type for deserialization
# ---------------------------------------------------------------------------

AnyNode = Union[
    VariableNode, DatasetNode, TransformNode, MacroNode,
    MacroInvocationNode, ProcNode, DataStepNode, PipelineNode,
]

NODE_CLASS_MAP: dict[str, type] = {
    NodeType.VARIABLE.value: VariableNode,
    NodeType.DATASET.value: DatasetNode,
    NodeType.TRANSFORM.value: TransformNode,
    NodeType.MACRO.value: MacroNode,
    NodeType.MACRO_INVOCATION.value: MacroInvocationNode,
    NodeType.PROC.value: ProcNode,
    NodeType.DATA_STEP.value: DataStepNode,
    NodeType.PIPELINE.value: PipelineNode,
}


def node_from_dict(data: dict) -> AnyNode:
    """Deserialize a node dict (from JSON or event log) into the correct typed model."""
    node_type = data.get("node_type")
    cls = NODE_CLASS_MAP.get(node_type)
    if cls is None:
        raise ValueError(f"Unknown node_type: {node_type!r}")
    return cls(**data)
