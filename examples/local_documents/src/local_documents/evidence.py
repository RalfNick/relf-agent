"""Presentation checks over accepted SDK receipts; never a scheduler or journal."""

import json
import re
from pathlib import PurePosixPath

from relf_agent import SQLiteStore
from relf_agent.errors import ValidationError

from .documents import source_id


def read_run(database, run_id):
    store = SQLiteStore(database, readonly=True)
    try:
        return store.run(run_id)
    finally:
        store.close()


def collect_sources(run):
    sources = {}
    for action in run["actions"]:
        if (
            action.get("kind") != "tool"
            or action.get("status") != "completed"
            or action.get("tool") not in {"search_documents", "read_document"}
        ):
            continue
        for item in action["result"]["sources"]:
            if item.get("id") != source_id(item):
                raise ValidationError("读取回执中的来源身份不一致")
            sources[item["id"]] = item
    return sources


def _cited(citations, run):
    available = collect_sources(run)
    if (
        type(citations) is not list
        or any(type(item) is not str for item in citations)
        or len(set(citations)) != len(citations)
    ):
        raise ValidationError("引用必须为不重复的来源 ID 列表")
    if any(item not in available for item in citations):
        raise ValidationError("引用未出现在本任务实际读取的资料中")
    return [available[item] for item in citations]


def validate_answer(value, run):
    if type(value) is str:
        try:
            value = json.loads(value)
        except ValueError as error:
            raise ValidationError("模型最终回答不是要求的 JSON") from error
    if (
        type(value) is not dict
        or set(value) != {"answer", "grounded", "citations"}
        or type(value["answer"]) is not str
        or not value["answer"].strip()
        or type(value["grounded"]) is not bool
    ):
        raise ValidationError("模型回答格式不完整")
    sources = _cited(value["citations"], run)
    if bool(sources) != value["grounded"]:
        raise ValidationError("回答的依据声明与实际引用不一致")
    return {**value, "sources": sources}


def report_path(path):
    if (
        type(path) is not str
        or len(path) > 120
        or path.startswith(".")
        or PurePosixPath(path).name != path
        or re.fullmatch(r"[\w .-]+\.md", path) is None
    ):
        raise ValidationError("报告必须为输出目录内的普通 .md 文件名，不支持子目录或覆盖")
    return path


def source_lines(sources):
    return [
        f"- {item['path']} (L{item['start_line']}-L{item['end_line']}; "
        + (f"start_column={item['start_column']}; " if "start_column" in item else "")
        + f"sha256={item['sha256']})"
        for item in sources
    ]


def render_report(arguments, run):
    path = report_path(arguments["path"])
    if path != run["input"].get("report_path"):
        raise ValidationError("报告路径与原请求不同；请取消此提案后重新请求")
    content = arguments["content"]
    if type(content) is not str or not content.strip() or "\x00" in content:
        raise ValidationError("报告正文必须为非空文本")
    sources = _cited(arguments["citations"], run)
    if not sources:
        raise ValidationError("报告必须引用本任务实际读取的资料")
    text = (
        content.rstrip()
        + "\n\n## 资料来源（读取时快照）\n\n"
        + "\n".join(source_lines(sources))
        + "\n"
    )
    if len(text.encode("utf-8")) > 131072:
        raise ValidationError("报告超过 128 KiB")
    return path, text
