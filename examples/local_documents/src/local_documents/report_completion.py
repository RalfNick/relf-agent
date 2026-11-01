"""Pure application completion rule using the SDK's committed tool receipts."""

import json

from relf_agent import CompletionVerdict


class ReportCompletion:
    identity = {"kind": "local-documents-report-completion", "version": "1"}

    def verify(self, request):
        path = request.task.get("report_path")
        if path is None:
            return CompletionVerdict("accept")
        if any(
            item["tool"] == "save_report" and item["arguments"].get("path") == path
            for item in request.receipts
        ):
            return CompletionVerdict("accept")
        output = json.loads(request.output) if isinstance(request.output, str) else request.output
        if output.get("grounded") is False:
            return CompletionVerdict("reject", "资料不足或模型未形成报告保存提案；报告没有保存。")
        return CompletionVerdict(
            "retry",
            f"这是报告保存任务，不是普通问答。你的文字回复尚未完成任务。请使用本任务已读取的来源 ID，"
            f"调用 save_report(path={path!r}, content=完整Markdown正文, citations=来源ID列表)，"
            "等待原审批流程。没有 save_report 的已完成回执，不得以文字说明代替报告提案。",
        )
