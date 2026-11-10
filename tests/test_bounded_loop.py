"""Pure iteration proposals and verdicts over original adopted result evidence."""

import asyncio
import importlib

import pytest

from relf_agent.errors import ValidationError
from relf_agent.planning import PlanningRequest
from relf_agent.workflow import (
    BranchCondition,
    StaticWorkflowCompiler,
    StaticWorkflowInterpreter,
    ValueRef,
)


def policy(**config):
    return importlib.import_module("relf_agent.bounded_loop").BoundedLoopPolicy(**config)


class NoCaller:
    async def call(self, *args, **kwargs):
        raise AssertionError("A loop policy must not execute a member or model")


def request(results=None, revision=0, *, task=None, members=("worker",), **fields):
    return PlanningRequest(task, members, [] if results is None else results, revision, **fields)


def result(value, call_id="opaque/accepted:雪", member="worker"):
    return {"id": call_id, "member": member, "result": value}


def propose(component, evidence):
    return asyncio.run(component.plan(evidence, NoCaller()))


def selected_input(proposal, task):
    plan = StaticWorkflowCompiler().compile(proposal.graph())
    return StaticWorkflowInterpreter().select(plan, task, {"iteration": {"state": "pending"}})


def test_first_iteration_runs_once_even_if_the_original_task_already_matches_until():
    component = policy()
    task = {"done": True, "task": "inspect"}
    proposal = propose(component, request(task=task))
    assert len(proposal.nodes) == 1
    assert proposal.nodes[0]["id"] == "iteration"
    assert proposal.nodes[0]["member"] == "worker"
    assert proposal.nodes[0]["depends_on"] == []
    selected = selected_input(proposal, task)
    assert selected.node_id == "iteration"
    assert selected.input == {"task": task, "previous": None, "iteration": 1}
    complete = StaticWorkflowInterpreter().select(
        StaticWorkflowCompiler().compile(proposal.graph()),
        task,
        {"iteration": {"state": "completed", "result": {"done": True, "answer": "kept"}}},
    )
    assert complete.done and complete.result == {"done": True, "answer": "kept"}


def test_next_iteration_carries_the_full_previous_adopted_result_in_original_bindings():
    previous = {"done": False, "state": {"remaining": 1}, "evidence": ["confirmed"]}
    task = {"remaining": 2}
    proposal = propose(policy(), request([result(previous)], 1, task=task))
    selected = selected_input(proposal, task)
    assert selected.input == {"task": task, "previous": previous, "iteration": 2}
    assert proposal.nodes[0]["input"]["kind"] == "object"
    assert proposal.nodes[0]["input"]["fields"]["previous"]["kind"] == "literal"


def test_unsatisfied_result_requests_the_original_bounded_replanning_protocol():
    verdict = policy().verify(request([result({"done": False})]))
    assert verdict.to_dict() == {"status": "replan", "result": None}


def test_success_returns_the_latest_original_result_including_business_evidence():
    evidence = {"done": True, "answer": 7, "receipt": {"key": "original"}}
    verdict = policy().verify(
        request([result({"done": False}, "first"), result(evidence, "second")], 1)
    )
    assert verdict.to_dict() == {"status": "succeeded", "result": evidence}


@pytest.mark.parametrize("maximum", [1, 3, 32])
def test_last_nonmatching_iteration_fails_with_evidence_instead_of_reporting_success(maximum):
    history = [result({"done": False, "n": i}, f"accepted-{i}") for i in range(maximum)]
    verdict = policy(max_iterations=maximum).verify(request(history, maximum - 1))
    assert verdict.to_dict() == {
        "status": "failed",
        "result": {
            "reason": "loop_iteration_limit",
            "iterations": maximum,
            "last_result": {"done": False, "n": maximum - 1},
        },
    }


def test_matching_last_iteration_succeeds_before_applying_the_policy_limit():
    verdict = policy(max_iterations=1).verify(request([result({"done": True})]))
    assert verdict.to_dict() == {"status": "succeeded", "result": {"done": True}}


def test_custom_worker_and_negated_nested_condition_use_existing_canonical_semantics():
    component = policy(
        worker="repair",
        until=BranchCondition(ValueRef(path=("check", "status")), "needs_work", negate=True),
    )
    first = result({"check": {"status": "needs_work"}}, member="repair")
    proposal = propose(component, request([first], 1, members=("repair",)))
    assert proposal.nodes[0]["member"] == "repair"
    final = result({"check": {"status": "complete"}}, "next", "repair")
    assert component.verify(request([first, final], 1, members=("repair",))).status == "succeeded"


def test_boolean_true_is_not_interchangeable_with_number_one():
    component = policy()
    assert component.verify(request([result({"done": 1})])).status == "replan"
    assert component.verify(request([result({"done": True})])).status == "succeeded"


def test_explicit_null_condition_and_null_results_remain_legal():
    component = policy(until=BranchCondition(ValueRef(), None))
    assert component.verify(request([result(None)])).to_dict() == {
        "status": "succeeded",
        "result": None,
    }
    other = policy(until=BranchCondition(ValueRef(), "stop"))
    proposal = propose(other, request([result(None)], 1, task="original"))
    assert selected_input(proposal, "original").input == {
        "task": "original",
        "previous": None,
        "iteration": 2,
    }


@pytest.mark.parametrize(
    "config",
    [
        {"worker": None},
        {"worker": ""},
        {"worker": "not an alias"},
        {"worker": "@planner"},
        {"max_iterations": True},
        {"max_iterations": False},
        {"max_iterations": None},
        {"max_iterations": 0},
        {"max_iterations": 33},
        {"max_iterations": 3.0},
        {"version": None},
        {"version": " "},
        {"until": {}},
        {"until": False},
        {"until": "done"},
        {"until": lambda value: True},
        {"until": BranchCondition(ValueRef("other"), True)},
        {"until": BranchCondition(ValueRef(required=False), True)},
    ],
)
def test_invalid_configuration_cannot_create_a_loop_policy(config):
    cls = importlib.import_module("relf_agent.bounded_loop").BoundedLoopPolicy
    with pytest.raises(ValidationError):
        cls(**config)


def test_condition_can_use_the_entire_existing_32_component_reference_path():
    value = True
    for _ in range(32):
        value = {"nested": value}
    component = policy(until=BranchCondition(ValueRef(path=("nested",) * 32), True))
    assert component.verify(request([result(value)])).status == "succeeded"


@pytest.mark.parametrize("operation", ["plan", "verify"])
@pytest.mark.parametrize("raw", [None, {}, object()])
def test_both_roles_require_the_original_planning_request(operation, raw):
    component = policy()
    with pytest.raises(ValidationError):
        propose(component, raw) if operation == "plan" else component.verify(raw)


@pytest.mark.parametrize("operation", ["plan", "verify"])
@pytest.mark.parametrize("revision", [False, True, -1, 3, 32, 0.0, "0", None])
def test_revision_is_a_strict_integer_within_the_configured_policy_limit(operation, revision):
    component = policy()
    raw = request(revision=revision)
    with pytest.raises(ValidationError):
        propose(component, raw) if operation == "plan" else component.verify(raw)


@pytest.mark.parametrize("operation", ["plan", "verify"])
@pytest.mark.parametrize("history", [None, {}, "results", False])
def test_history_requires_a_list_rather_than_an_implicit_empty_or_coerced_result(
    operation, history
):
    component = policy()
    raw = PlanningRequest(None, ["worker"], history, 0)
    with pytest.raises(ValidationError):
        propose(component, raw) if operation == "plan" else component.verify(raw)


@pytest.mark.parametrize(
    "operation,history,revision",
    [
        ("plan", [], 1),
        ("plan", [result({"done": False})], 0),
        ("plan", [result({"done": False}, "one"), result({"done": False}, "two")], 1),
        ("verify", [], 0),
        ("verify", [result({"done": False})], 1),
        ("verify", [result({"done": False}, "one"), result({"done": True}, "two")], 0),
    ],
)
def test_phase_result_count_rejects_missing_and_additional_iterations(operation, history, revision):
    component = policy()
    raw = request(history, revision)
    with pytest.raises(ValidationError):
        propose(component, raw) if operation == "plan" else component.verify(raw)


@pytest.mark.parametrize(
    "entry",
    [
        None,
        False,
        {},
        {"id": "one", "member": "worker"},
        {"id": "one", "result": {"done": False}},
        {"member": "worker", "result": {"done": False}},
        {"id": "one", "member": "worker", "result": {"done": False}, "extra": True},
        result({"done": False}, None),
        result({"done": False}, False),
        result({"done": False}, 1),
        result({"done": False}, ""),
        result({"done": False}, "x" * 1025),
        result({"done": False}, "\ud800"),
        result({"done": False}, member="another"),
    ],
)
def test_only_exact_adopted_worker_records_with_finite_opaque_ids_are_accepted(entry):
    component = policy()
    with pytest.raises(ValidationError):
        propose(component, request([entry], 1))


def test_duplicate_opaque_call_identity_is_not_a_second_adopted_iteration():
    component = policy()
    history = [result({"done": False}, "same"), result({"done": True}, "same")]
    with pytest.raises(ValidationError):
        component.verify(request(history, 1))


def test_ids_are_opaque_and_do_not_require_an_internal_backend_spelling():
    component = policy()
    first = result({"done": False}, "雪" * 1024)
    second = result({"done": True}, "a third party backend's accepted call")
    assert propose(component, request([first], 1)).nodes[0]["id"] == "iteration"
    assert component.verify(request([first, second], 1)).status == "succeeded"


@pytest.mark.parametrize("operation", ["plan", "verify"])
def test_configured_worker_must_be_registered_even_for_pure_result_verification(operation):
    component = policy()
    raw = request([] if operation == "plan" else [result({"done": True})], members=("other",))
    with pytest.raises(ValidationError):
        propose(component, raw) if operation == "plan" else component.verify(raw)


def test_a_matching_historical_result_prevents_further_iteration_or_append_after_completion():
    component = policy()
    first = result({"done": True}, "already-done")
    with pytest.raises(ValidationError):
        propose(component, request([first], 1))
    with pytest.raises(ValidationError):
        component.verify(request([first, result({"done": False}, "unexpected")], 1))


@pytest.mark.parametrize("operation", ["plan", "verify"])
def test_missing_condition_evidence_does_not_become_an_unsatisfied_condition(operation):
    component = policy()
    raw = request([result({"status": "missing-done"})], 1 if operation == "plan" else 0)
    with pytest.raises(ValidationError):
        propose(component, raw) if operation == "plan" else component.verify(raw)


@pytest.mark.parametrize("field", ["remaining_steps", "max_nodes", "remaining_revisions"])
@pytest.mark.parametrize("value", [False, True, None, -1, 0, 1.0, "1"])
def test_proposal_requires_one_original_step_and_revision_allowance(field, value):
    component = policy()
    with pytest.raises(ValidationError):
        propose(component, request(constraints={field: value}))


def test_proposal_needs_only_one_remaining_slot_not_the_entire_possible_iteration_count():
    component = policy(max_iterations=32)
    proposal = propose(
        component,
        request(constraints={"remaining_steps": 1, "max_nodes": 1, "remaining_revisions": 1}),
    )
    assert selected_input(proposal, None).input == {"task": None, "previous": None, "iteration": 1}


def test_final_verification_does_not_need_a_new_step_or_revision_reservation():
    component = policy()
    verdict = component.verify(
        request(
            [result({"done": True})],
            constraints={"remaining_steps": 0, "max_nodes": 0, "remaining_revisions": 0},
        )
    )
    assert verdict.status == "succeeded"


def test_condition_configuration_and_returned_identity_are_deeply_detached():
    condition = BranchCondition(ValueRef(path=("answer",)), {"values": [1]})
    component = policy(until=condition, version="business-v1")
    condition.equals["values"][0] = 2
    descriptor = component.identity
    descriptor["until"]["value"]["path"].clear()
    descriptor["until"]["equals"]["values"].clear()
    assert component.verify(request([result({"answer": {"values": [1]}})])).status == "succeeded"
    assert component.identity["until"] == {
        "value": {
            "kind": "ref",
            "source": "input",
            "path": ["answer"],
            "required": True,
            "default": None,
        },
        "equals": {"values": [1]},
        "negate": False,
    }
    assert component.identity["version"] == "business-v1"
    with pytest.raises(AttributeError):
        component.max_iterations = 1


def test_received_evidence_and_returned_proposals_or_verdicts_keep_their_original_values():
    previous = {"done": False, "records": [{"n": 1}]}
    raw = request([result(previous)], 1, task={"original": [1]})
    previous["records"][0]["n"] = 9
    proposal = propose(policy(), raw)
    mutable = proposal.to_dict()
    mutable["nodes"][0]["input"]["fields"]["previous"]["value"]["records"].clear()
    assert selected_input(proposal, {"original": [1]}).input["previous"] == {
        "done": False,
        "records": [{"n": 1}],
    }
    final = policy().verify(request([result({"done": True, "records": [1]})]))
    final.to_dict()["result"]["records"].clear()
    assert final.result == {"done": True, "records": [1]}
