"""Display the actual position of bounded search excerpts inside long lines."""

from tests.test_local_documents_files import api


def test_source_lines_displays_optional_search_column_without_changing_old_citations():
    old = {"path": "notes.md", "start_line": 2, "end_line": 2, "sha256": "a" * 64}
    render = api("evidence").source_lines
    assert render([old]) == [f"- notes.md (L2-L2; sha256={'a' * 64})"]
    assert render([{**old, "start_column": 1801}]) == [
        f"- notes.md (L2-L2; start_column=1801; sha256={'a' * 64})"
    ]
