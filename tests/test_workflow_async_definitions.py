"""Public executor declarations compile purely into the original managed Tool IR."""

import json

import pytest

from relf_agent.errors import ValidationError
from relf_agent.types import AgentSpec, canonical, digest
from relf_agent.workflow import (
    ExecutionPlan,
    GraphNode,
    GraphWorkflowSpec,
    InputMap,
    Literal,
    StaticWorkflowCompiler,
    StaticWorkflowInterpreter,
    ValueRef,
    decode_binding,
    encode_binding,
)


@pytest.mark.parametrize(
    "kind,concurrency,definition_digest,plan_digest",
    [
        (
            "agent",
            1,
            "4605b12e2506ca6e1715e1b4ffb91261070461f175891e9e4f7f23d75e7d8867",
            "ab6e201fe265790f135452ed5f2d65075e1a34e5b3556bf1695ca5e3f70a7eeb",
        ),
        (
            "agent",
            2,
            "3f8e1b428e162c55353320dd9515519b9e0429c32b9b7d12c103b8a1419ef2bf",
            "27361b9053895ca3a6b72ae3b0eb6947a732d9c66a666c6259d0f536ebe11b7f",
        ),
        (
            "transform",
            1,
            "8e8fbf79a21f686df0db4de436025bd35e43de74f5acea65a31e12d923ce9ab9",
            "b86c1096a6c397cf64845b7aa1ef403716af422c23b161d93bee71332f126e2d",
        ),
        (
            "tool",
            1,
            "63708c1e093cccdab34d79ac1fd485ea2cfe6b3ba149d960be45fd02c47eab40",
            "b014d059de98a5edb45badae3006b8d408541988089230fb99494165d10be88b",
        ),
        (
            "transform",
            2,
            "5bea8e1479b598fa77ed4d321275347bb6c1c2378ab41227121575b7540b1c1f",
            "65c2e109a41fd2e043327db77593c5ec5ebdeaa2de0ef6e405aa03cbe88e8f08",
        ),
        (
            "tool",
            2,
            "f91d9adadff8fdaceb8f390643c7567d24ea040499053b271df1e263cde98edb",
            "4b5c060c0dc2967fc70c0ae14c8b860437ad1329058bfae45233237547e1164e",
        ),
    ],
)
def test_unused_executor_keeps_original_definition_and_plan_bytes(
    kind, concurrency, definition_digest, plan_digest
):
    registered = AgentSpec("legacy-agent", "Answer") if kind == "agent" else "identity"
    graph = GraphWorkflowSpec(
        "legacy", [GraphNode("old", **{kind: registered})], max_concurrency=concurrency
    )
    plan = StaticWorkflowCompiler().compile(graph)
    assert digest(graph.to_dict()) == definition_digest
    assert digest(plan.to_dict()) == plan_digest
    assert "executor" not in graph.to_dict()["nodes"][0]
    assert "executor" not in plan.to_dict()["nodes"][0]


@pytest.mark.parametrize("input", [None, True, 7, "all", [1, {"x": None}], {"x": 1}])
@pytest.mark.parametrize("concurrency", [1, 2])
def test_executor_json_declaration_lowers_complete_input_and_separate_config(input, concurrency):
    declaration = {
        "kind": "graph",
        "name": "business",
        "nodes": [
            {
                "id": "enrich",
                "executor": "enrich",
                "input": {"kind": "literal", "value": input},
                "config": {"mode": "full"},
                "output_schema": {"type": "object"},
            }
        ],
        **({"max_concurrency": concurrency} if concurrency > 1 else {}),
    }
    graph = GraphWorkflowSpec.from_dict(json.loads(json.dumps(declaration)))
    public_node = graph.to_dict()["nodes"][0]
    assert public_node["executor"] == "enrich" and "tool" not in public_node
    assert public_node["input"] == {"kind": "literal", "value": input}
    assert public_node["config"] == {"mode": "full"}
    plan = StaticWorkflowCompiler().compile(graph)
    assert plan.to_dict()["schema_version"] == (2 if concurrency == 1 else 3)
    node = plan.to_dict()["nodes"][0]
    assert node["tool"] == "__relf_node__:enrich" and "executor" not in node
    assert node["config"] == {} and node["output_schema"] == {"type": "object"}
    assert node["input"] == {
        "kind": "object",
        "fields": {
            "input": {"kind": "literal", "value": input},
            "config": {"kind": "literal", "value": {"mode": "full"}},
        },
    }
    selection = StaticWorkflowInterpreter().select(plan, {}, {"enrich": {"state": "pending"}})
    assert selection.input == {"input": input, "config": {"mode": "full"}}
    assert GraphWorkflowSpec.from_dict(graph.to_dict()).to_dict() == graph.to_dict()
    recompiled = StaticWorkflowCompiler().compile(GraphWorkflowSpec.from_plan(plan))
    assert canonical(recompiled.to_dict()) == canonical(plan.to_dict())


def test_lowering_keeps_nested_input_references_and_literal_config_distinct():
    graph = GraphWorkflowSpec(
        "nested",
        [
            GraphNode("first", transform="identity"),
            GraphNode(
                "next",
                executor="enrich",
                depends_on=("first",),
                input=InputMap(
                    {
                        "source": InputMap({"value": ValueRef("first", ("value",))}),
                        "literal": Literal({"kind": "ref", "source": "not-a-reference"}),
                    }
                ),
                config={"kind": "ref", "source": "also-literal"},
            ),
        ],
    )
    plan = StaticWorkflowCompiler().compile(graph)
    selected = StaticWorkflowInterpreter().select(
        plan,
        {},
        {"first": {"state": "completed", "result": {"value": 5}}, "next": {"state": "pending"}},
    )
    assert selected.node_id == "next"
    assert selected.input == {
        "input": {
            "source": {"value": 5},
            "literal": {"kind": "ref", "source": "not-a-reference"},
        },
        "config": {"kind": "ref", "source": "also-literal"},
    }


@pytest.mark.parametrize(
    "options",
    [
        {"executor": "enrich", "tool": "public"},
        {"executor": "enrich", "transform": "identity"},
        {"executor": "enrich", "agent": AgentSpec("a", "Answer")},
        {"executor": ""},
        {"executor": "bad:name"},
        {"executor": "x" * 65},
        {"executor": "enrich", "config": []},
        {"tool": "public", "config": {"hidden": True}},
        {"agent": AgentSpec("a", "Answer"), "config": {"hidden": True}},
    ],
)
def test_executor_rejects_ambiguous_or_invalid_node_configuration(options):
    with pytest.raises(ValidationError):
        GraphNode.from_dict({"id": "bad", **options})


@pytest.mark.parametrize("new_field", ["executor", "unexpected"])
@pytest.mark.parametrize("schema_version", [1, 2, 3])
def test_execution_plan_rejects_unlowered_executor_and_unknown_fields(new_field, schema_version):
    plan = (
        StaticWorkflowCompiler()
        .compile(
            GraphWorkflowSpec(
                "raw",
                [GraphNode("n", tool="public")],
                max_concurrency=2 if schema_version == 3 else 1,
            )
        )
        .to_dict()
    )
    plan["schema_version"] = schema_version
    node = plan["nodes"][0]
    if new_field == "executor":
        node.pop("tool")
    node[new_field] = "enrich"
    with pytest.raises(ValidationError):
        ExecutionPlan(plan)


def test_execution_plan_rejects_even_an_unused_public_executor_field():
    plan = (
        StaticWorkflowCompiler()
        .compile(GraphWorkflowSpec("raw", [GraphNode("n", transform="identity")]))
        .to_dict()
    )
    plan["nodes"][0]["executor"] = None
    with pytest.raises(ValidationError):
        ExecutionPlan(plan)


def nested_binding(depth):
    value = {"kind": "literal", "value": "leaf"}
    for _ in range(depth):
        value = {"kind": "object", "fields": {"child": value}}
    return value


def test_nested_binding_roundtrips_through_the_32_map_boundary():
    encoded = nested_binding(32)
    assert encode_binding(decode_binding(encoded)) == encoded
    with pytest.raises(ValidationError):
        decode_binding(nested_binding(33))
    typed = decode_binding(nested_binding(31))
    encode_binding(InputMap({"child": typed}))
    with pytest.raises(ValidationError):
        InputMap({"child": InputMap({"child": typed})})


def test_executor_wrapper_is_counted_in_the_bounded_binding_tree():
    GraphWorkflowSpec(
        "bounded", [GraphNode("n", executor="identity", input=decode_binding(nested_binding(31)))]
    )
    with pytest.raises(ValidationError):
        GraphWorkflowSpec(
            "too-deep",
            [GraphNode("n", executor="identity", input=decode_binding(nested_binding(32)))],
        )


@pytest.mark.parametrize("operation", ["encode", "construct", "graph"])
def test_cyclic_typed_bindings_raise_validation_error(operation):
    value = InputMap({})
    node = GraphNode("cycle", transform="identity", input=value)
    value.fields["self"] = value
    if operation == "graph":
        node.input.fields["self"] = node.input
    with pytest.raises(ValidationError):
        if operation == "encode":
            encode_binding(value)
        elif operation == "construct":
            InputMap({"value": value})
        else:
            GraphWorkflowSpec("cycle", [node])


def test_cyclic_encoded_binding_raises_validation_error():
    value = {"kind": "object", "fields": {}}
    value["fields"]["self"] = value
    with pytest.raises(ValidationError):
        decode_binding(value)


@pytest.mark.parametrize("entry", ["binding", "node", "graph"])
def test_very_deep_encoded_binding_is_rejected_as_a_typed_error(entry):
    binding = nested_binding(1500)
    node = {"id": "deep", "executor": "identity", "input": binding}
    with pytest.raises(ValidationError):
        if entry == "binding":
            decode_binding(binding)
        elif entry == "node":
            GraphNode.from_dict(node)
        else:
            GraphWorkflowSpec.from_dict({"name": "deep", "nodes": [node]})


@pytest.mark.parametrize("input", [float("nan"), float("inf"), object()])
def test_executor_input_and_config_require_finite_json(input):
    with pytest.raises(ValidationError):
        GraphNode("invalid", executor="identity", input=Literal(input))
    with pytest.raises(ValidationError):
        GraphNode("invalid", executor="identity", config={"value": input})


def test_nested_map_references_still_require_an_ancestor():
    with pytest.raises(ValidationError):
        GraphWorkflowSpec(
            "invalid",
            [
                GraphNode(
                    "n",
                    executor="identity",
                    input=InputMap({"nest": InputMap({"value": ValueRef("other")})}),
                )
            ],
        )


def test_graph_node_keeps_existing_positional_tool_slot():
    node = GraphNode("n", None, None, (), ValueRef(), None, False, {}, None, "public")
    assert node.tool == "public" and node.executor is None
