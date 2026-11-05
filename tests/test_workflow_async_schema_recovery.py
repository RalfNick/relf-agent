"""Referenced node schemas keep the original approval and recovery authority."""

import asyncio

from .test_workflow_async_nodes import Echo, engine, graph, registry


def test_reference_schemas_survive_approval_reopen_and_duplicate_commands(tmp_path):
    component = Echo()
    path = tmp_path / "referenced-node.sqlite"
    input_schema = {
        "$defs": {"amount": {"type": "integer", "minimum": 0}},
        "type": "object",
        "properties": {"amount": {"$ref": "#/$defs/amount"}},
        "required": ["amount"],
        "additionalProperties": False,
    }
    config_schema = {
        "$defs": {"warehouse": {"const": "local"}},
        "type": "object",
        "properties": {"warehouse": {"$ref": "#/$defs/warehouse"}},
        "required": ["warehouse"],
        "additionalProperties": False,
    }

    def nodes():
        return registry(
            component,
            effect="unqueryable_write",
            approval=True,
            input_schema=input_schema,
            config_schema=config_schema,
            output_schema=input_schema,
        )

    definition = graph(config={"warehouse": "local"})
    with engine(path, nodes()) as runtime:
        handle = runtime.submit(definition, {"amount": 2}, command_id="submit")
        waiting = asyncio.run(runtime.drive(handle.run_id))
        assert waiting.state == "waiting_approval"
        assert component.calls == []
        pending = waiting.pending[0]
        manifest = runtime.diagnostics(handle.run_id).manifest
    with engine(path, nodes()) as runtime:
        receipt = runtime.approve(
            handle.run_id, pending["action_id"], pending["digest"], command_id="approve"
        )
        assert asyncio.run(runtime.drive(handle.run_id)).result == {"amount": 2}
        assert runtime.diagnostics(handle.run_id).manifest == manifest
        action = runtime.store.run(handle.run_id)["actions"][0]
        effect_key = action["effect_key"]
        assert action["status"] == "completed"
    with engine(path, nodes()) as runtime:
        assert runtime.submit(definition, {"amount": 2}, command_id="submit") == handle
        assert (
            runtime.approve(
                handle.run_id, pending["action_id"], pending["digest"], command_id="approve"
            )
            == receipt
        )
        events = runtime.events(handle.run_id)
        assert asyncio.run(runtime.drive(handle.run_id)).result == {"amount": 2}
        assert runtime.events(handle.run_id) == events
        action = runtime.store.run(handle.run_id)["actions"][0]
        assert action["effect_key"] == effect_key
        assert runtime.diagnostics(handle.run_id).budget["spent"] == 1
    assert component.calls == [({"amount": 2}, {"warehouse": "local"}, effect_key)]
