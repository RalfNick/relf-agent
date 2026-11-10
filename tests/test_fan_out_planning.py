"""Bounded batch proposals reuse existing DAG bindings without calling members."""

import asyncio
import importlib

import pytest

from relf_agent.errors import ValidationError
from relf_agent.planning import PlanningRequest
from relf_agent.workflow import StaticWorkflowCompiler, StaticWorkflowInterpreter


def planner(**config):
    return importlib.import_module("relf_agent.fan_out_planning").FanOutDAGPlanner(**config)


class NoCaller:
    async def call(self, *args, **kwargs):
        raise AssertionError("A fan-out planner must not call a member or model")


def propose(component, task, *, members=("worker", "join"), results=None, revision=0, **fields):
    request = PlanningRequest(task, members, [] if results is None else results, revision, **fields)
    return asyncio.run(component.plan(request, NoCaller()))


def test_batch_inputs_use_original_indices_and_final_mapping_ignores_completion_order():
    request = [{"n": 1}, None, False]
    proposal = propose(planner(), request)
    nodes = proposal.nodes
    assert [n["id"] for n in nodes] == ["map-0000", "map-0001", "map-0002"]
    assert [n["member"] for n in nodes] == ["worker", "worker", "worker"]
    assert all(n["depends_on"] == [] for n in nodes)
    assert [n["input"]["path"] for n in nodes] == [[0], [1], [2]]
    assert all(n["input"]["source"] == "input" for n in nodes)
    plan = StaticWorkflowCompiler().compile(proposal.graph())
    selected = StaticWorkflowInterpreter().select(
        plan, request, {n["id"]: {"state": "pending"} for n in nodes}
    )
    assert selected.node_id == "map-0000" and selected.input == {"n": 1}
    done = StaticWorkflowInterpreter().select(
        plan,
        request,
        {
            "map-0002": {"state": "completed", "result": False},
            "map-0000": {"state": "completed", "result": {"answer": 1}},
            "map-0001": {"state": "completed", "result": None},
        },
    )
    assert done.done and done.result == {
        "map-0000": {"answer": 1},
        "map-0001": None,
        "map-0002": False,
    }


def test_reducer_waits_for_all_workers_and_receives_only_their_confirmed_mapping():
    proposal = propose(planner(reducer="join"), ["a", "b"])
    assert [n["id"] for n in proposal.nodes] == ["map-0000", "map-0001", "reduce"]
    reducer = proposal.nodes[-1]
    assert reducer["member"] == "join"
    assert reducer["depends_on"] == ["map-0000", "map-0001"]
    plan = StaticWorkflowCompiler().compile(proposal.graph())
    states = {
        "map-0000": {"state": "completed", "result": {"v": 1}},
        "map-0001": {"state": "pending"},
        "reduce": {"state": "pending"},
    }
    assert StaticWorkflowInterpreter().select(plan, ["a", "b"], states).node_id == "map-0001"
    states["map-0001"] = {"state": "completed", "result": [2]}
    selected = StaticWorkflowInterpreter().select(plan, ["a", "b"], states)
    assert selected.node_id == "reduce"
    assert selected.input == {"map-0000": {"v": 1}, "map-0001": [2]}
    states["reduce"] = {"state": "completed", "result": "combined"}
    assert StaticWorkflowInterpreter().select(plan, ["a", "b"], states).result == "combined"


def test_nested_dictionary_and_list_path_is_preserved_in_worker_bindings():
    proposal = propose(
        planner(items_path=("batches", 1, "items")), {"batches": [{}, {"items": [7]}]}
    )
    assert proposal.nodes[0]["input"]["path"] == ["batches", 1, "items", 0]
    plan = StaticWorkflowCompiler().compile(proposal.graph())
    selected = StaticWorkflowInterpreter().select(
        plan, {"batches": [{}, {"items": [7]}]}, {"map-0000": {"state": "pending"}}
    )
    assert selected.input == 7


@pytest.mark.parametrize("reducer,count", [(None, 256), ("join", 255)])
def test_maximum_batch_size_fits_existing_256_node_dag_without_truncation(reducer, count):
    proposal = propose(planner(reducer=reducer, max_items=count), list(range(count)))
    assert len(proposal.nodes) == 256
    assert proposal.nodes[count - 1]["input"]["path"] == [count - 1]
    assert proposal.nodes[-1]["id"] == ("map-0255" if reducer is None else "reduce")


def test_31_part_path_leaves_one_original_binding_slot_for_the_item_index():
    task = [9]
    for _ in range(31):
        task = {"items": task}
    proposal = propose(planner(items_path=("items",) * 31), task)
    assert len(proposal.nodes[0]["input"]["path"]) == 32


@pytest.mark.parametrize(
    "config",
    [
        {"worker": None},
        {"worker": "not an alias"},
        {"reducer": ""},
        {"reducer": []},
        {"max_items": True},
        {"max_items": 3.0},
        {"max_items": 0},
        {"max_items": 257},
        {"reducer": "join", "max_items": 256},
        {"items_path": "items"},
        {"items_path": (False,)},
        {"items_path": (-1,)},
        {"items_path": ("items",) * 32},
        {"version": None},
        {"version": " "},
    ],
)
def test_invalid_configuration_is_rejected_before_a_plan_can_be_proposed(config):
    cls = importlib.import_module("relf_agent.fan_out_planning").FanOutDAGPlanner
    with pytest.raises(ValidationError):
        cls(**config)


@pytest.mark.parametrize("task", [None, {}, [], "items", [1] * 33])
def test_invalid_or_excessive_root_batches_never_become_successful_proposals(task):
    component = planner()
    with pytest.raises(ValidationError):
        propose(component, task)


@pytest.mark.parametrize("task", [{}, {"items": None}, {"items": {}}, {"items": []}])
def test_missing_or_non_list_nested_batches_are_rejected(task):
    component = planner(items_path=("items",))
    with pytest.raises(ValidationError):
        propose(component, task)


@pytest.mark.parametrize("config,members", [({}, ["join"]), ({"reducer": "join"}, ["worker"])])
def test_worker_and_reducer_must_be_registered_request_members(config, members):
    component = planner(**config)
    with pytest.raises(ValidationError):
        propose(component, [1], members=members)


@pytest.mark.parametrize("revision", [False, True, -1, 1, 0.0])
def test_revision_must_be_exactly_initial_integer_zero(revision):
    component = planner()
    with pytest.raises(ValidationError):
        propose(component, [1], revision=revision)


@pytest.mark.parametrize("results", [{}, "", [False], [{"id": "old", "result": 1}]])
def test_existing_or_malformed_results_cannot_trigger_a_second_batch(results):
    component = planner()
    with pytest.raises(ValidationError):
        propose(component, [1], results=results)


@pytest.mark.parametrize("field", ["remaining_steps", "max_nodes"])
@pytest.mark.parametrize("value", [False, None, -1, 2.0, "9", 0, 2])
def test_constraints_are_strict_and_include_the_reducer_node(field, value):
    component = planner(reducer="join")
    with pytest.raises(ValidationError):
        propose(component, [1, 2], constraints={field: value})


def test_both_original_constraint_allowances_are_respected_without_changing_them():
    allowances = {"remaining_steps": 3, "max_nodes": 3, "unrelated": "preserved"}
    proposal = propose(planner(reducer="join"), [1, 2], constraints=allowances)
    assert len(proposal.nodes) == 3
    assert allowances == {"remaining_steps": 3, "max_nodes": 3, "unrelated": "preserved"}


def test_configuration_and_returned_descriptors_are_detached_from_mutable_inputs():
    path = ["items"]
    component = planner(items_path=path, version="configured-v1")
    path[0] = "changed"
    identity = component.identity
    identity["items_path"][0] = "changed"
    identity["max_items"] = 1
    with pytest.raises(AttributeError):
        component.max_items = 1
    request_input = {"items": [{"n": 7}, 8]}
    request = PlanningRequest(request_input, ["worker"], [], 0)
    request_input["items"].clear()
    proposal = asyncio.run(component.plan(request, NoCaller()))
    descriptor = proposal.to_dict()
    descriptor["nodes"][0]["input"]["path"].clear()
    assert len(proposal.nodes) == 2
    assert proposal.nodes[0]["input"]["path"] == ["items", 0]
    assert component.identity["items_path"] == ["items"]
    assert component.identity["max_items"] == 32
    assert component.identity["version"] == "configured-v1"


@pytest.mark.parametrize("raw", [None, {}, object()])
def test_planner_requires_the_original_structured_planning_request(raw):
    component = planner()
    with pytest.raises(ValidationError):
        asyncio.run(component.plan(raw, NoCaller()))


def test_absent_result_evidence_is_not_treated_as_an_empty_previous_batch():
    component = planner()
    request = PlanningRequest([1], ["worker"], None, 0)
    with pytest.raises(ValidationError):
        asyncio.run(component.plan(request, NoCaller()))
