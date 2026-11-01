"""Explicit non-secret configuration; paths are relative to this TOML file."""

import json
import math
import os
import re
import tempfile
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit

from relf_agent.errors import DefinitionMismatch, ValidationError
from relf_agent.types import canonical


@dataclass(frozen=True)
class Config:
    documents: Path
    output: Path
    state: Path
    adapter: str
    model: str
    base_url: str
    api_key_env: str
    timeout: float = 45
    max_output_tokens: int = 2048

    @property
    def database(self):
        return self.state / "runs.sqlite"

    @property
    def public(self):
        return {
            key: str(value) if isinstance(value, Path) else value
            for key, value in asdict(self).items()
        }


def load_config(path):
    path = Path(path).expanduser().resolve()
    try:
        with path.open("rb") as stream:
            value = tomllib.load(stream)
    except (OSError, ValueError) as error:
        raise ValidationError("无法读取 TOML 配置；请检查 --config 文件") from error
    if set(value) != {"paths", "model"}:
        raise ValidationError("配置仅支持 [paths] 与 [model]")
    paths, model = value["paths"], value["model"]
    required = {"adapter", "name", "base_url", "api_key_env"}
    if (
        type(paths) is not dict
        or set(paths) != {"documents", "output", "state"}
        or type(model) is not dict
        or not required <= set(model)
        or set(model) - required - {"timeout", "max_output_tokens"}
    ):
        raise ValidationError("配置字段不完整或包含未知字段；密钥只能通过环境变量传入")
    for item in (*paths.values(), *(model[key] for key in required)):
        if type(item) is not str or not item.strip() or any(ord(c) < 32 for c in item):
            raise ValidationError("配置名称和路径必须为非空文本")
    resolved = {key: (path.parent / Path(val).expanduser()).resolve() for key, val in paths.items()}
    if not resolved["documents"].is_dir():
        raise ValidationError("资料目录必须已经存在")
    for key, directory in resolved.items():
        for other, target in resolved.items():
            if key != other and (directory == target or directory in target.parents):
                raise ValidationError("资料、报告、状态目录必须相互分离")
    url = urlsplit(model["base_url"])
    if (
        url.scheme not in {"https", "http"}
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise ValidationError("模型地址必须是不含凭据的 HTTP(S) URL")
    if model["adapter"] not in {"deepseek", "chat-completions"}:
        raise ValidationError("adapter 支持 deepseek 或 chat-completions")
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", model["api_key_env"]) is None:
        raise ValidationError("api_key_env 必须为环境变量名，不能填写密钥值")
    timeout = model.get("timeout", 45)
    tokens = model.get("max_output_tokens", 2048)
    if type(timeout) not in {int, float} or not 1 <= timeout <= 120 or not math.isfinite(timeout):
        raise ValidationError("模型 timeout 必须在 1–120 秒之间")
    if type(tokens) is not int or not 128 <= tokens <= 4096:
        raise ValidationError("max_output_tokens 必须在 128–4096 之间")
    return Config(
        **resolved,
        adapter=model["adapter"],
        model=model["name"],
        base_url=model["base_url"].rstrip("/"),
        api_key_env=model["api_key_env"],
        timeout=timeout,
        max_output_tokens=tokens,
    )


def pin_config(config):
    """Create-only identity note; the SDK remains the execution authority."""
    config.state.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = config.state / "config.json"
    expected = {"application": "local-documents-v1", "config": config.public}
    fd, temporary = tempfile.mkstemp(prefix=".config-", dir=config.state)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(canonical(expected))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            try:
                existing = json.loads(target.read_text())
            except (OSError, ValueError) as error:
                raise DefinitionMismatch("原应用配置记录不可读；请保留原状态目录") from error
            if existing != expected:
                raise DefinitionMismatch(
                    "配置与原任务不一致；恢复原配置，或为新配置使用新状态目录"
                ) from None
    finally:
        Path(temporary).unlink(missing_ok=True)
