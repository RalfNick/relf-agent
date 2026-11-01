"""Application contract: actual files and accepted read evidence, no model calls."""

import importlib
import sys
from pathlib import Path

import pytest

from relf_agent import FileSystemWorkspace, Scope
from relf_agent.errors import RalfError

APP = Path(__file__).resolve().parents[1] / "examples/local_documents/src"


def api(name):
    if APP.is_dir() and str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    return importlib.import_module("local_documents." + name)


def config_file(root, extra=""):
    (root / "docs").mkdir()
    path = root / "assistant.toml"
    path.write_text(
        '[paths]\ndocuments="docs"\noutput="reports"\nstate=".assistant"\n'
        '[model]\nadapter="deepseek"\nname="configured-model"\n'
        'base_url="https://api.deepseek.com"\napi_key_env="TEST_MODEL_KEY"\n' + extra
    )
    return path


def test_config_resolves_relative_to_its_file_without_creating_state(tmp_path):
    config = api("config").load_config(config_file(tmp_path))
    assert config.documents == tmp_path / "docs"
    assert config.output == tmp_path / "reports"
    assert config.database == tmp_path / ".assistant/runs.sqlite"
    assert config.api_key_env == "TEST_MODEL_KEY"
    assert not config.state.exists()


@pytest.mark.parametrize("extra", ['api_key="secret"\n', "timeout=nan\n", "timeout=true\n"])
def test_config_rejects_inline_key_or_invalid_timeout(tmp_path, extra):
    with pytest.raises(RalfError):
        api("config").load_config(config_file(tmp_path, extra))
    assert not (tmp_path / ".assistant").exists()


def test_config_rejects_data_and_output_overlap(tmp_path):
    path = config_file(tmp_path)
    path.write_text(path.read_text().replace('output="reports"', 'output="docs/reports"'))
    with pytest.raises(RalfError):
        api("config").load_config(path)


def test_read_uses_actual_path_line_numbers_and_full_file_digest(tmp_path):
    import hashlib

    text = "# 值班规则\n\n收到告警后15分钟内确认。\n负责人：李明。\n"
    (tmp_path / "rules.md").write_text(text)
    port = FileSystemWorkspace(tmp_path, version="test")
    try:
        library = api("documents").DocumentLibrary(port)
        result = library.read(Scope(), "rules.md", start_line=3, max_lines=2)
        (source,) = result["sources"]
        assert source["path"] == "rules.md"
        assert (source["start_line"], source["end_line"]) == (3, 4)
        assert source["text"] == "收到告警后15分钟内确认。\n负责人：李明。\n"
        assert source["sha256"] == hashlib.sha256(text.encode()).hexdigest()
        assert not source["truncated"]
        assert source["id"].startswith("src-")
    finally:
        port.close()


def test_search_bounds_snippets_and_reads_only_markdown_and_txt(tmp_path):
    (tmp_path / "rules.md").write_text("# 值班\n告警需要15分钟内确认。\n")
    (tmp_path / "other.txt").write_text("无关的花草种植记录。\n")
    (tmp_path / "image.bin").write_bytes(b"\x00\xff")
    port = FileSystemWorkspace(tmp_path, version="test")
    try:
        library = api("documents").DocumentLibrary(port, max_snippets=1)
        result = library.search(Scope(), "告警确认")
        assert result["scanned_files"] == 2
        assert len(result["sources"]) == 1
        assert result["sources"][0]["path"] == "rules.md"
        assert library.search(Scope(), "ZXQ_NONEXISTENT")["sources"] == []
    finally:
        port.close()


@pytest.mark.parametrize("path", ["../secret.txt", "/etc/passwd", "file.py"])
def test_read_refuses_escape_and_non_document_extensions(tmp_path, path):
    (tmp_path / "file.py").write_text("secret")
    port = FileSystemWorkspace(tmp_path, version="test")
    try:
        with pytest.raises(RalfError):
            api("documents").DocumentLibrary(port).read(Scope(), path)
    finally:
        port.close()


def test_unsafe_symlink_is_not_silently_omitted_from_search(tmp_path):
    (tmp_path / "link.md").symlink_to("/etc/passwd")
    port = FileSystemWorkspace(tmp_path, version="test")
    try:
        with pytest.raises(RalfError):
            api("documents").DocumentLibrary(port).search(Scope(), "password")
    finally:
        port.close()


def test_search_rejects_over_capacity_instead_of_silently_missing_files(tmp_path):
    for name in ("a.txt", "b.txt", "c.txt"):
        (tmp_path / name).write_text("find me")
    port = FileSystemWorkspace(tmp_path, version="test")
    try:
        with pytest.raises(RalfError):
            api("documents").DocumentLibrary(port, max_files=2).search(Scope(), "find")
    finally:
        port.close()


def test_read_rejects_oversized_or_invalid_utf8_files(tmp_path):
    (tmp_path / "large.txt").write_text("x" * 100)
    (tmp_path / "invalid.txt").write_bytes(b"\xff")
    port = FileSystemWorkspace(tmp_path, version="test")
    try:
        library = api("documents").DocumentLibrary(port, max_file_bytes=50)
        for name in ("large.txt", "invalid.txt"):
            with pytest.raises(RalfError):
                library.read(Scope(), name)
    finally:
        port.close()


def test_long_line_is_marked_as_truncated_with_original_digest(tmp_path):
    (tmp_path / "line.txt").write_text("x" * 100)
    port = FileSystemWorkspace(tmp_path, version="test")
    try:
        (source,) = (
            api("documents")
            .DocumentLibrary(port, max_excerpt_chars=30)
            .read(Scope(), "line.txt")["sources"]
        )
        assert len(source["text"]) == 30
        assert source["truncated"] and source["start_line"] == source["end_line"] == 1
    finally:
        port.close()


def evidence_run(tmp_path):
    (tmp_path / "policy.md").write_text("Policy: acknowledge within 15 minutes.\n")
    port = FileSystemWorkspace(tmp_path, version="test")
    try:
        result = api("documents").DocumentLibrary(port).read(Scope(), "policy.md")
    finally:
        port.close()
    return {
        "input": {"question": "summarize", "report_path": "summary.md"},
        "actions": [
            {"kind": "tool", "tool": "read_document", "status": "completed", "result": result}
        ],
    }, result["sources"][0]


def test_answer_only_accepts_sources_from_completed_read_actions(tmp_path):
    run, source = evidence_run(tmp_path)
    result = {"answer": "15 minutes", "grounded": True, "citations": [source["id"]]}
    verified = api("evidence").validate_answer(result, run)
    assert verified["sources"] == [source]
    with pytest.raises(RalfError):
        api("evidence").validate_answer({**result, "citations": ["invented"]}, run)
    run["actions"][0]["status"] = "executing"
    with pytest.raises(RalfError):
        api("evidence").validate_answer(result, run)


def test_no_evidence_answer_cannot_claim_grounded_or_attach_fake_sources():
    evidence = api("evidence")
    assert (
        evidence.validate_answer(
            {"answer": "资料未包含此信息", "grounded": False, "citations": []}, {"actions": []}
        )["sources"]
        == []
    )
    with pytest.raises(RalfError):
        evidence.validate_answer(
            {"answer": "guess", "grounded": True, "citations": []}, {"actions": []}
        )


def test_report_contains_real_sources_and_matches_requested_create_only_path(tmp_path):
    run, source = evidence_run(tmp_path)
    args = {"path": "summary.md", "content": "# Summary\n15 minutes.", "citations": [source["id"]]}
    path, text = api("evidence").render_report(args, run)
    assert path == "summary.md" and text.startswith(args["content"])
    assert "policy.md" in text and source["sha256"] in text and "L1-L1" in text
    for name in ("../escape.md", "other.md", "summary.txt", ".hidden.md"):
        with pytest.raises(RalfError):
            api("evidence").render_report({**args, "path": name}, run)
