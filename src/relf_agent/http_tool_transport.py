"""One fixed HTTP request lifetime, retained until its owned client closes."""

import time

import httpx

from .tool_json import decode_output
from .tool_sources import ToolSourceError


def execute(
    url,
    headers,
    payload,
    timeout,
    output_limit,
    stopped,
    *,
    method="POST",
    query=None,
    allow_empty_204=False,
):
    deadline = time.monotonic() + timeout

    def check():
        if stopped.is_set() or time.monotonic() >= deadline:
            raise ToolSourceError("HTTP tool request stopped or timed out")

    try:
        check()
        with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            if method in {"POST", "PUT", "PATCH"}:
                options = {
                    "content": payload,
                    "headers": {
                        **headers,
                        "Content-Type": "application/json",
                        "Accept-Encoding": "identity",
                    },
                }
            else:
                url = url + ("?" + query if query else "")
                options = {"headers": {**headers, "Accept-Encoding": "identity"}}
            with client.stream(
                method,
                url,
                **options,
            ) as response:
                check()
                if not 200 <= response.status_code < 300:
                    raise ToolSourceError("HTTP tool request returned an unsuccessful status")
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise ToolSourceError("HTTP tool response requires identity encoding")
                if response.status_code == 204:
                    length = response.headers.get("Content-Length")
                    if "Transfer-Encoding" in response.headers or (
                        length is not None
                        and (not length.isascii() or not length.isdecimal() or int(length) != 0)
                    ):
                        raise ToolSourceError("HTTP empty response has invalid framing")
                output = bytearray()
                for chunk in response.iter_raw():
                    check()
                    if len(output) + len(chunk) > output_limit:
                        raise ToolSourceError("HTTP tool response exceeds its byte limit")
                    output.extend(chunk)
                check()
                if response.status_code == 204:
                    if not allow_empty_204 or output:
                        raise ToolSourceError(
                            "HTTP empty response requires explicit empty acceptance"
                        )
                    return None
                return decode_output(output)
    except (httpx.HTTPError, httpx.InvalidURL, OSError, ValueError, RecursionError):
        raise ToolSourceError("HTTP tool transport or JSON response failed") from None
