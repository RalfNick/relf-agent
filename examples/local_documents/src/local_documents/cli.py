"""CLI observation and explicit controls over the original local execution."""

import argparse
import asyncio
import hashlib
import json
import math
import os
import shlex
import signal
import stat
import sys
import uuid
from types import SimpleNamespace

from relf_agent.errors import RalfError, SessionBusy, ValidationError
from relf_agent.types import digest

from .config import load_config
from .evidence import read_run, render_report, source_lines
from .runtime import Application, history, inspect_run


def emit(value, as_json=False):
    if as_json:
        print(json.dumps(value, ensure_ascii=False), flush=True)
        return
    if "run_id" in value:
        print(
            f"Run: {value['run_id']}  状态: {value.get('state', value.get('record_state', '已记录'))}"
        )
    if "command_id" in value:
        print(f"命令 ID: {value['command_id']}")
    if value.get("configuration_mismatch"):
        print(value["message"])
    if value.get("answer"):
        print("\n" + value["answer"])
        if value.get("sources"):
            print("\n来源（读取时快照）:\n" + "\n".join(source_lines(value["sources"])))
    for preview in value.get("pending", []):
        print(
            f"\n目标路径: {preview['path']}\nAction: {preview['action_id']}\n摘要: {preview['digest']}\n"
            f"--- 报告全文 ---\n{preview['content']}--- 报告结束 ---\n尚未写入；approve 记录决定，resume 执行。"
        )
    for turn in value.get("turns", []):
        print(f"{turn['turn_seq']}. {turn['run_id']} [{turn['state']}] {turn['question']}")
        if turn.get("answer_validation", {}).get("status") == "rejected":
            print("  原回答引用校验未通过，未作为可信回答展示；执行终态仍保留原事实。")
    if value.get("error"):
        print(f"错误: {value['error']} {value.get('message', '')}")
    if value.get("state") == "waiting_reconciliation":
        print(
            "请求或效果结果未知，未自动重发；保留原 Run，用 status 查询。需要新请求时先 cancel 停止，再使用新命令 ID。"
        )
    if value.get("state") == "cancelling":
        print("取消已记录，等待在途调用实际结束；取消不代表远端回滚。")
    if value.get("wait_reason") == "observation_timeout":
        print("等待到期仅结束观察，业务没有被取消；用 status 查询或 resume 继续原任务。")
    sys.stdout.flush()


async def read_line(prompt):
    # Avoid an input thread that cannot be stopped when the event loop closes.
    print(prompt, end="", file=sys.stderr, flush=True)
    fd = sys.stdin.fileno()
    if stat.S_ISREG(os.fstat(fd).st_mode):
        return sys.stdin.readline()
    loop, ready = asyncio.get_running_loop(), asyncio.get_running_loop().create_future()

    def receive():
        if not ready.done():
            ready.set_result(sys.stdin.readline())

    loop.add_reader(fd, receive)
    try:
        return await ready
    finally:
        loop.remove_reader(fd)


async def input_line(prompt, interrupted):
    reading = asyncio.create_task(read_line(prompt))
    stopping = asyncio.create_task(interrupted.wait())
    try:
        await asyncio.wait((reading, stopping), return_when=asyncio.FIRST_COMPLETED)
        if interrupted.is_set():
            interrupted.clear()
            print("\n输入已取消；/quit 退出。", file=sys.stderr)
            return "\n"
        return reading.result()
    finally:
        for task in (reading, stopping):
            if not task.done():
                task.cancel()
        await asyncio.gather(reading, stopping, return_exceptions=True)


async def observe(app, handle, args, interrupted):
    print(f"Run: {handle.ref.run_id}", file=sys.stderr, flush=True)
    watching = asyncio.create_task(app.observe(handle, wait_timeout=args.wait_timeout))
    stopping = asyncio.create_task(interrupted.wait())
    try:
        await asyncio.wait((watching, stopping), return_when=asyncio.FIRST_COMPLETED)
        if not interrupted.is_set():
            return watching.result()
        interrupted.clear()
        print("记录业务取消，等待在途调用结束与资源关闭…", file=sys.stderr, flush=True)
        await app.cancel(handle.ref.run_id)
        done = await handle.wait(wait_timeout=args.wait_timeout, terminal_only=True)
        return {
            **inspect_run(app.config, handle.ref.run_id),
            "wait_reason": done.wait_reason,
            "interrupted": True,
        }
    finally:
        for task in (watching, stopping):
            if not task.done():
                task.cancel()
        await asyncio.gather(watching, stopping, return_exceptions=True)


def approval_preview(config, run_id, action_id=None, target_digest=None):
    run = read_run(config.database, run_id)
    actions = [
        item
        for item in run["actions"]
        if item.get("tool") == "save_report"
        and (item["id"] == action_id if action_id else item["status"] == "waiting_approval")
    ]
    if len(actions) != 1:
        raise ValidationError("请从 status 选择原报告，传入 --action 和 --digest")
    (action,) = actions
    if target_digest is not None and target_digest != action["digest"]:
        raise ValidationError("摘要与原报告不同")
    path, text = render_report(action["arguments"], run)
    return {
        "action_id": action["id"],
        "digest": action["digest"],
        "path": str(config.output / path),
        "content": text,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


async def perform(app, args, interrupted):
    if args.command in {"ask", "report"}:
        command_id = args.command_id or "turn-" + uuid.uuid4().hex
        handle = await app.submit(
            args.question,
            session_id=args.session,
            command_id=command_id,
            report_path=args.output if args.command == "report" else None,
        )
        return {**await observe(app, handle, args, interrupted), "command_id": command_id}
    if args.command == "resume":
        return await observe(app, await app.resume(args.run_id), args, interrupted)
    if args.command == "cancel":
        receipt = await app.cancel(args.run_id)
        handle = app.runtime.attach(app.runtime.reference(args.run_id))
        return {**await observe(app, handle, args, interrupted), "cancel_receipt": receipt}
    preview = approval_preview(app.config, args.run_id, args.action, args.digest)
    if not args.yes:
        if not sys.stdin.isatty():
            raise ValidationError(
                "尚未记录决定；先用 status 查看原报告，非交互确认须显式使用 --yes"
            )
        emit({"run_id": args.run_id, "state": "waiting_approval", "pending": [preview]})
        prompt = "确认拒绝此报告？" if args.reject else "确认批准此报告？"
        answer = await input_line(prompt + " 输入 yes；其他输入不提交决定: ", interrupted)
        if answer.strip() != "yes":
            return {"run_id": args.run_id, "state": "waiting_approval", "decision_recorded": False}
    approved = not args.reject
    command_id = args.command_id or "approval:" + digest(
        [args.run_id, preview["action_id"], preview["digest"], approved]
    )
    return app.approve(
        args.run_id,
        preview["action_id"],
        preview["digest"],
        command_id=command_id,
        approved=approved,
    )


HELP = """输入问题查询；/report summary.md 主题 提出报告保存。
/status RUN_ID  /approve RUN_ID  /reject RUN_ID  /resume RUN_ID  /cancel RUN_ID
/history 查看本会话，/help 帮助，/quit 退出。每次请求显示 Run 和命令 ID。
状态与文件保存在本地；显式模型 API 会接收当前问题、必要历史和资料摘录。
"""


async def chat(app, args, interrupted):
    print(HELP, file=sys.stderr)
    while True:
        line = await input_line(f"[{args.session}] > ", interrupted)
        if not line or line.strip() == "/quit":
            return {"session_id": args.session, "closed": True}
        if not line.strip():
            continue
        try:
            command = SimpleNamespace(**vars(args), command_id=None)
            text = line.strip()
            if text == "/help":
                print(HELP, file=sys.stderr)
                continue
            if text == "/history":
                emit(history(app.config, args.session), args.json)
                continue
            if not text.startswith("/"):
                command.command, command.question = "ask", text
            else:
                parts = shlex.split(text)
                name = parts[0][1:]
                if name == "report" and len(parts) >= 3:
                    command.command, command.output, command.question = (
                        name,
                        parts[1],
                        " ".join(parts[2:]),
                    )
                elif (
                    name in {"status", "approve", "reject", "resume", "cancel"} and len(parts) == 2
                ):
                    command.command, command.run_id = name, parts[1]
                    if name == "status":
                        emit(inspect_run(app.config, command.run_id), args.json)
                        continue
                    if name in {"approve", "reject"}:
                        command.command, command.reject, command.yes = (
                            "approve",
                            name == "reject",
                            False,
                        )
                        command.action = command.digest = None
                else:
                    raise ValidationError("命令格式不正确；/help 查看用法")
            result = await perform(app, command, interrupted)
            emit(result, args.json)
            if result.get("interrupted"):
                return result
            if command.command == "approve" and result.get("record_state") == "durably_recorded":
                emit(
                    await observe(app, await app.resume(command.run_id), args, interrupted),
                    args.json,
                )
        except RalfError as error:
            message = str(error)
            if isinstance(error, SessionBusy):
                message += f"；请先处理原 Run {error.run_ref.run_id}"
            emit({"error": error.code, "message": message}, args.json)


async def execute(config, args):
    loop, interrupted = asyncio.get_running_loop(), asyncio.Event()
    previous = signal.getsignal(signal.SIGINT)
    loop.add_signal_handler(signal.SIGINT, interrupted.set)
    try:
        async with Application(config) as app:
            return (
                await chat(app, args, interrupted)
                if args.command == "chat"
                else await perform(app, args, interrupted)
            )
    finally:
        loop.remove_signal_handler(signal.SIGINT)
        signal.signal(signal.SIGINT, previous)


def parser():
    root = argparse.ArgumentParser(description="本地 Markdown/TXT 资料助手（显式模型 API）")
    root.add_argument("--config", default="assistant.toml")
    root.add_argument("--session", default="main")
    root.add_argument("--wait-timeout", type=float, default=90)
    root.add_argument("--json", action="store_true")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("chat")
    for name in ("ask", "report"):
        item = commands.add_parser(name)
        item.add_argument("question")
        item.add_argument("--command-id")
        if name == "report":
            item.add_argument("--output", required=True)
    for name in ("status", "resume", "cancel"):
        commands.add_parser(name).add_argument("run_id")
    commands.add_parser("history")
    item = commands.add_parser("approve")
    item.add_argument("run_id")
    item.add_argument("--action")
    item.add_argument("--digest")
    item.add_argument("--command-id")
    item.add_argument("--yes", action="store_true")
    item.add_argument("--reject", action="store_true")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    os.umask(0o077)
    try:
        if not math.isfinite(args.wait_timeout) or not 0 <= args.wait_timeout <= 300:
            raise ValidationError("--wait-timeout 必须在 0–300 秒之间")
        config = load_config(args.config)
        if args.command == "status":
            result = inspect_run(config, args.run_id)
        elif args.command == "history":
            result = history(config, args.session)
        else:
            result = asyncio.run(execute(config, args))
        emit(result, args.json)
        if result.get("interrupted"):
            return 130
        return (
            2
            if args.command not in {"status", "history"}
            and result.get("state") in {"failed", "waiting_reconciliation"}
            else 0
        )
    except RalfError as error:
        message = str(error)
        if isinstance(error, SessionBusy):
            message += f"；请先处理原 Run {error.run_ref.run_id}，新尝试使用新命令 ID"
        emit({"error": error.code, "message": message}, args.json)
        return 2
    except (OSError, ValueError):
        emit(
            {
                "error": "local_io_error",
                "message": "请检查本地路径、权限与配置；原任务仍保存在 SQLite",
            },
            args.json,
        )
        return 2
    except KeyboardInterrupt:
        emit({"error": "interrupted", "message": "操作已中断；用 status 核对原任务"}, args.json)
        return 130
