"""Real SDK activation imports for native/parent node History paths."""

import importlib
import warnings
from dataclasses import asdict

import pytest

from relf_agent import GraphNode, GraphWorkflowSpec, Scope
from relf_agent.types import submission_request

from .test_temporal_workflow_nodes_state import node_manifest

pytest.importorskip("temporalio")


@pytest.mark.parametrize(
    "workflow_module",
    [
        "relf_agent.temporal_workflow",
        "relf_agent.temporal_parent_workflow",
        "relf_agent.temporal_session_workflow",
    ],
)
def test_original_sdk_activation_loads_node_rules_without_dynamic_import_warning(workflow_module):
    from temporalio import workflow
    from temporalio.worker.workflow_sandbox._importer import Importer
    from temporalio.worker.workflow_sandbox._restrictions import RestrictionContext

    from relf_agent.temporal import _workflow_runner

    manifest = node_manifest()
    spec = GraphWorkflowSpec("nodes", [GraphNode("echo", executor="echo")])
    request = submission_request(spec, None, budget=2)
    importlib.import_module(workflow_module)
    context = RestrictionContext()
    importer = Importer(_workflow_runner().restrictions, context)
    with importer.applied():
        importlib.import_module(workflow_module)
        context.is_runtime = True
        context.in_activation = True
        try:
            with (
                warnings.catch_warnings(),
                workflow.unsafe.sandbox_import_notification_policy(
                    {workflow.SandboxImportNotificationPolicy.WARN_ON_DYNAMIC_IMPORT}
                ),
            ):
                warnings.simplefilter("error", UserWarning)
                # Use the SDK import hook that handles Workflow bytecode imports;
                # importlib's host cache can otherwise hide the activation path.
                protocol = importer._import(
                    "relf_agent.temporal_node_protocol", fromlist=("validate_protocol",)
                )
                importer._import("relf_agent.temporal_node_state", fromlist=("next_operation",))
                protocol.validate_protocol(manifest)
                parent_api = importlib.import_module("relf_agent.temporal_parent_state")
                native_api = importlib.import_module("relf_agent.temporal_state")
                parent = parent_api.TemporalParentState(
                    "parent",
                    asdict(Scope()),
                    "submit",
                    request,
                    manifest,
                    "parent-epoch",
                )
                (call,) = parent.next_calls()
                child = native_api.TemporalRunState(
                    call["run_id"],
                    parent.scope,
                    call["command_id"],
                    call["request"],
                    manifest,
                    "child-epoch",
                )
                action, envelope = child.next_operation()
                assert action["kind"] == "tool" and action["tool"] == "__relf_node__:echo"
                assert envelope["arguments"] == {"input": None, "config": {}}
                assert child.decisions == 0 and child.messages == []
                assert child.budget["reserved"] == parent.budget["reserved"] == 2
        finally:
            context.in_activation = False
            context.is_runtime = False
