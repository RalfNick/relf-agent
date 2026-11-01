"""Bounded lexical document tools over the SDK's actual filesystem snapshots."""

import re
from pathlib import PurePosixPath

from relf_agent.errors import ValidationError
from relf_agent.types import digest


def document_path(path):
    if (
        type(path) is not str
        or "\\" in path
        or PurePosixPath(path).is_absolute()
        or ".." in PurePosixPath(path).parts
    ):
        raise ValidationError("资料路径必须在指定目录内")
    if PurePosixPath(path).suffix.lower() not in {".md", ".txt"}:
        raise ValidationError("仅支持 Markdown／TXT 资料")
    return path


def source_id(source):
    return "src-" + digest({key: val for key, val in source.items() if key != "id"})[:32]


def _terms(text):
    terms = set(re.findall(r"[a-z0-9]+", text.lower()))
    for word in re.findall(r"[\u4e00-\u9fff]+", text):
        terms.update(word)
        terms.update(word[i : i + 2] for i in range(len(word) - 1))
    return terms


class DocumentLibrary:
    def __init__(
        self,
        workspace,
        *,
        max_files=128,
        max_file_bytes=262144,
        max_snippets=4,
        max_excerpt_chars=1600,
    ):
        self.workspace = workspace
        self.max_files, self.max_file_bytes = max_files, max_file_bytes
        self.max_snippets, self.max_excerpt_chars = max_snippets, max_excerpt_chars

    def _files(self, scope):
        pending, visited, files = [("", 0)], 0, []
        while pending:
            directory, depth = pending.pop()
            if depth > 8:
                raise ValidationError("资料目录层级超过 8")
            view = self.workspace.list(scope, directory, max_entries=self.max_files)
            for item in view["entries"]:
                visited += 1
                if visited > self.max_files:
                    raise ValidationError("资料目录条目超过限额；请缩小目录")
                if item["kind"] == "directory":
                    pending.append((item["path"], depth + 1))
                elif PurePosixPath(item["path"]).suffix.lower() in {".md", ".txt"}:
                    files.append(item["path"])
        return sorted(files)

    def _excerpt(self, snapshot, start, count):
        lines = snapshot["text"].splitlines(keepends=True)
        selected = lines[start - 1 : start - 1 + count]
        if not selected:
            return None
        text, used = "", 0
        for line in selected:
            remaining = self.max_excerpt_chars - len(text)
            if remaining <= 0:
                break
            text += line[:remaining]
            used += 1
        source = {
            "path": snapshot["path"],
            "start_line": start,
            "end_line": start + used - 1,
            "text": text,
            "sha256": snapshot["sha256"],
            "truncated": text != "".join(selected),
        }
        return {"id": source_id(source), **source}

    def read(self, scope, path, *, start_line=1, max_lines=30):
        document_path(path)
        if (
            type(start_line) is not int
            or start_line < 1
            or type(max_lines) is not int
            or not 1 <= max_lines <= 40
        ):
            raise ValidationError("行号须为正整数，每次最多读取 40 行")
        snapshot = self.workspace.read_text(scope, path, max_bytes=self.max_file_bytes)
        source = self._excerpt(snapshot, start_line, max_lines)
        return {"sources": [] if source is None else [source]}

    def search(self, scope, query):
        if type(query) is not str or not query.strip() or len(query) > 500:
            raise ValidationError("搜索词须为 1–500 个字符")
        terms, found, paths = _terms(query), [], self._files(scope)
        for path in paths:
            snapshot = self.workspace.read_text(scope, path, max_bytes=self.max_file_bytes)
            for start in range(1, len(snapshot["text"].splitlines()) + 1, 20):
                source = self._excerpt(snapshot, start, 20)
                score = len(terms & _terms(source["text"] + " " + path))
                if score:
                    found.append((score, path, start, source))
        found.sort(key=lambda item: (-item[0], item[1], item[2]))
        return {
            "query": query,
            "scanned_files": len(paths),
            "sources": [item[3] for item in found[: self.max_snippets]],
        }
