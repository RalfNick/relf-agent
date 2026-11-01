"""Bounded lexical document tools over the SDK's actual filesystem snapshots."""

import re
from itertools import chain
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


def _matches(line, terms):
    """Yield real token positions without building a vocabulary for the file."""
    normalized = line.lower()
    positions = None
    if len(normalized) != len(line):
        # Unicode lowercase can expand a character; receipt columns refer to the original.
        positions = [index for index, char in enumerate(line) for _ in char.lower()]

    def bounds(start, end):
        if positions is not None:
            return positions[start], positions[end - 1] + 1
        return start, end

    for match in re.finditer(r"[a-z0-9]+|[\u4e00-\u9fff]+", normalized):
        word = match.group()
        if word.isascii():
            if word in terms:
                yield bounds(match.start(), match.end())
        else:
            for index, char in enumerate(word):
                if char in terms:
                    yield bounds(match.start() + index, match.start() + index + 1)
                if index + 1 < len(word) and word[index : index + 2] in terms:
                    yield bounds(match.start() + index, match.start() + index + 2)


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

    def _excerpt(self, snapshot, start, count, *, lines=None, start_column=1):
        if lines is None:
            lines = snapshot["text"].splitlines(keepends=True)
        selected = lines[start - 1 : start - 1 + count]
        if not selected:
            return None
        text, used = "", 0
        for index, line in enumerate(selected):
            if index == 0:
                line = line[start_column - 1 :]
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
            "truncated": start_column > 1 or len(text) != sum(map(len, selected)),
        }
        if start_column > 1:
            source["start_column"] = start_column
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
            lines = snapshot["text"].splitlines(keepends=True)
            offsets = [0]
            for line in lines:
                offsets.append(offsets[-1] + len(line))
            path_terms = terms & _terms(path)
            covered_end = 0
            for index, line in enumerate(lines):
                line_start = offsets[index]
                if offsets[index + 1] <= covered_end:
                    continue
                matches = _matches(line, terms)
                if path_terms:
                    # A path match retains the existing filename-search behavior.
                    matches = chain([(0, 0)], matches)
                for match_start, match_end in matches:
                    if line_start + match_end <= covered_end and match_end:
                        continue
                    start = line_start
                    if line_start + match_end > start + self.max_excerpt_chars:
                        start += match_start
                    end = min(start + self.max_excerpt_chars, offsets[min(index + 20, len(lines))])
                    if end <= covered_end:
                        continue
                    text = snapshot["text"][start:end]
                    score = len(path_terms | (terms & _terms(text)))
                    if score:
                        # Keep only bounded descriptors, and construct receipts after ranking.
                        found.append(
                            (-score, path, index + 1, start - line_start + 1, snapshot, lines)
                        )
                        found.sort(key=lambda item: item[:4])
                        del found[self.max_snippets :]
                    covered_end = end
        return {
            "query": query,
            "scanned_files": len(paths),
            "sources": [
                self._excerpt(snapshot, start, 20, lines=lines, start_column=column)
                for _, _, start, column, snapshot, lines in found
            ],
        }
