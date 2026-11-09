"""Close diagnostics preserve responsibility without exposing original reports."""

import json

import pytest

from relf_agent.errors import CloseIncomplete


def test_legacy_report_stays_original_and_unknown_diagnostics_never_formats_it():
    class PrivateReport:
        def __str__(self):
            raise AssertionError("Report stringification must never run")

        __repr__ = __str__

    report = PrivateReport()
    error = CloseIncomplete(report)
    assert error.report is report
    assert error.code == "close_incomplete"
    assert getattr(error, "diagnostics", None) == {
        "schema_version": 1,
        "state": "incomplete",
        "authority": "unknown",
        "stage": "unknown",
        "ownership": "unknown",
        "blockers": [],
        "retry_action": "retain_original_instance_and_retry_close",
    }
    json.dumps(error.diagnostics, allow_nan=False)


def test_diagnostics_are_detached_from_inputs_and_returned_copies():
    from relf_agent.close_diagnostics import make_close_diagnostics

    counts = {"handler": 2, "end_ack": 1}
    details = make_close_diagnostics(
        authority="temporal", stage="end_ack", ownership="owned", blockers=counts
    )
    error = CloseIncomplete({"private": "secret-service-url"}, diagnostics=details)
    counts["handler"] = 99
    details["blockers"][0]["count"] = 88
    observed = error.diagnostics
    assert observed == {
        "schema_version": 1,
        "state": "incomplete",
        "authority": "temporal",
        "stage": "end_ack",
        "ownership": "owned",
        "blockers": [{"kind": "handler", "count": 2}, {"kind": "end_ack", "count": 1}],
        "retry_action": "retain_original_instance_and_retry_close",
    }
    observed["blockers"][0]["count"] = 77
    assert error.diagnostics["blockers"][0]["count"] == 2
    assert "secret-service-url" not in json.dumps(error.diagnostics)
    with pytest.raises(AttributeError):
        error.diagnostics = {}


@pytest.mark.parametrize("count", [True, -1, 1.5, float("nan"), object()])
def test_unknown_or_invalid_counts_are_not_certified_as_zero(count):
    from relf_agent.close_diagnostics import make_close_diagnostics

    error = CloseIncomplete(
        "private report",
        diagnostics=make_close_diagnostics(
            authority="local", stage="run_drain", ownership="borrowed", blockers={"run": count}
        ),
    )
    assert error.diagnostics["blockers"] == []
    assert error.diagnostics["ownership"] == "borrowed"


def test_untrusted_metadata_cannot_echo_free_text_or_arbitrary_objects():
    class PrivateValue:
        def __str__(self):
            raise AssertionError("Metadata stringification must never run")

        __repr__ = __str__

    error = CloseIncomplete(
        "private report",
        diagnostics={
            "authority": "secret-authority-url",
            "stage": PrivateValue(),
            "ownership": "secret-owner",
            "blockers": [
                {"kind": "private-token", "count": 1},
                {"kind": "handler", "count": True},
                {"kind": "end_ack", "count": 2, "secret": PrivateValue()},
            ],
            "unknown": PrivateValue(),
        },
    )
    assert error.diagnostics["authority"] == "unknown"
    assert error.diagnostics["stage"] == "unknown"
    assert error.diagnostics["ownership"] == "unknown"
    assert error.diagnostics["blockers"] == [{"kind": "end_ack", "count": 2}]
    assert "private" not in json.dumps(error.diagnostics)


def test_outer_close_phase_preserves_specific_inner_ack_and_original_report():
    from relf_agent.close_diagnostics import enrich_close_diagnostics, make_close_diagnostics

    report = {"private": "original-resource"}
    error = CloseIncomplete(
        report,
        diagnostics=make_close_diagnostics(stage="end_ack", blockers={"end_ack": 1}),
    )
    enriched = enrich_close_diagnostics(
        error,
        authority="temporal",
        stage="execution_drain",
        ownership="owned",
        blockers={"handler": 0, "end_ack": 3},
    )
    assert enriched is error and error.report is report
    assert error.diagnostics["stage"] == "end_ack"
    assert error.diagnostics["authority"] == "temporal"
    assert error.diagnostics["ownership"] == "owned"
    assert error.diagnostics["blockers"] == [
        {"kind": "end_ack", "count": 3},
        {"kind": "handler", "count": 0},
    ]


def test_impossible_integer_count_cannot_break_json_error_rendering():
    error = CloseIncomplete(
        "private report",
        diagnostics={"blockers": [{"kind": "handler", "count": 1 << 20000}]},
    )
    assert error.diagnostics["blockers"] == []
    json.dumps(error.diagnostics, allow_nan=False)
