"""User-declared Schemas are fixed data, not implicit I/O capabilities."""

import asyncio
import json
import sys
import warnings

import pytest

from relf_agent import AgentSpec, ToolCall, ToolDescriptor, ToolPolicy, ToolRegistry, ToolSpec
from relf_agent.decisions import final_output, validate_decision
from relf_agent.errors import ValidationError
from relf_agent.harness import DecisionProposal
from relf_agent.workflow import validate_output

from .test_tool_sources import Source, context
from .test_workflow_executors import registry_with

BOUNDARIES = [
    "workflow",
    "node-output",
    "model-output",
    "model-tool",
    "tool",
    "typed-tool",
    "tool-source",
    "cli-tool",
    "http-tool",
    "mcp-tool",
]


def validate_at(boundary, schema, value, root):
    if boundary == "workflow":
        return validate_output(value, schema)
    if boundary == "node-output":
        return registry_with(output_schema=schema).validate_output("__relf_node__:business", value)
    if boundary == "model-output":
        return final_output(value, schema)
    if boundary == "model-tool":
        return validate_decision(
            AgentSpec("agent", "Use allowed tools", tools=("read",)),
            DecisionProposal(tool_calls=(ToolCall("read", value, "call"),)),
            {"read": {"input_schema": schema}},
        )

    def read(arguments, ctx):
        return arguments

    registry = ToolRegistry()
    if boundary == "tool":
        registry.register(ToolSpec("read", "Read", schema), read)
        return registry.get("read").validate(value)
    if boundary == "typed-tool":

        def typed(value):
            return value

        registry.register_function(typed, effect="read_only", input_schema=schema)
        return registry.get("typed").handler(value, context())
    descriptor = ToolDescriptor("read", "Read", schema)
    if boundary == "tool-source":
        from relf_agent import register_tool_source

        source = Source([descriptor])
        asyncio.run(
            register_tool_source(
                registry,
                source,
                policies={"read": ToolPolicy(version="1", effect="read_only")},
            )
        )
        return asyncio.run(registry.get("read").handler(value, context()))

    async def call():
        if boundary == "cli-tool":
            from relf_agent import CLIToolSource

            remote = CLIToolSource(
                descriptor,
                [sys.executable, "-c", "print('{\"value\":7}')"],
                version="1",
                cwd=root,
            )
        elif boundary == "http-tool":
            from relf_agent import HTTPToolSource

            # Input must be refused before any business HTTP request.
            remote = HTTPToolSource(descriptor, "https://business.invalid/read", version="1")
        else:
            from relf_agent.mcp import MCPToolSource

            class Transport:
                identity = {"kind": "offline-mcp", "version": "1"}

                async def request(self, *args, **kwargs):
                    return {"content": []}

            remote = MCPToolSource(Transport())
        try:
            return await remote.call_tool(descriptor, value, context())
        finally:
            if boundary != "mcp-tool":
                await remote.aclose()

    return asyncio.run(call())


@pytest.mark.parametrize("boundary", BOUNDARIES)
@pytest.mark.parametrize("reference_key", ["$ref", "$dynamicRef"])
def test_unfixed_external_schema_is_rejected_without_retrieval(
    tmp_path,
    monkeypatch,
    boundary,
    reference_key,
):
    resource = tmp_path / "mutable-schema.json"
    resource.write_text('{"type":"object"}')
    schema = {
        "type": "object",
        "properties": {"value": {}},
        "additionalProperties": False,
        reference_key: resource.as_uri(),
    }
    retrieved = []

    def forbidden_retrieval(*args, **kwargs):
        retrieved.append(True)
        raise AssertionError("Schema validation must not retrieve a file or URL")

    monkeypatch.setattr("urllib.request.urlopen", forbidden_retrieval)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises(ValidationError):
            validate_at(boundary, schema, {"value": 7}, tmp_path)
    assert retrieved == []


@pytest.mark.parametrize("boundary", BOUNDARIES[:7])
def test_fixed_local_defs_are_validated_without_external_resources(tmp_path, boundary):
    schema = {
        "type": "object",
        "properties": {"value": {"$ref": "#/$defs/number"}},
        "required": ["value"],
        "additionalProperties": False,
        "$defs": {"number": {"type": "integer"}},
    }
    validate_at(boundary, schema, {"value": 7}, tmp_path)
    with pytest.raises(ValidationError):
        validate_at(boundary, schema, {"value": "wrong"}, tmp_path)


@pytest.mark.parametrize("boundary", BOUNDARIES[:7])
def test_schema_keywords_in_business_literals_remain_literal(tmp_path, boundary):
    value = {"value": {"$ref": "https://literal.invalid/business-value"}}
    schema = {
        "type": "object",
        "properties": {"value": {"const": value["value"]}},
        "required": ["value"],
        "additionalProperties": False,
    }
    validate_at(boundary, schema, json.loads(json.dumps(value)), tmp_path)


@pytest.mark.parametrize("boundary", BOUNDARIES[:7])
def test_embedded_named_resource_is_allowed_without_retrieval(tmp_path, boundary):
    schema = {
        "type": "object",
        "$defs": {"number": {"$id": "urn:example:fixed-number", "type": "integer"}},
        "properties": {"value": {"$ref": "urn:example:fixed-number"}},
        "required": ["value"],
        "additionalProperties": False,
    }
    validate_at(boundary, schema, {"value": 7}, tmp_path)
    with pytest.raises(ValidationError):
        validate_at(boundary, schema, {"value": False}, tmp_path)


@pytest.mark.parametrize("boundary", BOUNDARIES[:7])
@pytest.mark.parametrize("reference", ["#/$defs/missing", "#"])
def test_unresolvable_or_unbounded_schema_returns_public_error(tmp_path, boundary, reference):
    schema = {
        "type": "object",
        "properties": {"value": {}},
        "additionalProperties": False,
        "allOf": [{"$ref": reference}],
    }
    with pytest.raises(ValidationError):
        validate_at(boundary, schema, {"value": 7}, tmp_path)
