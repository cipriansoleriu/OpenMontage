"""Shared Kie.ai jobs-API client (createTask -> recordInfo polling).

Used by the Persona fork's Kie-backed tools (seedance_kie, nano_banana_pro).
API contract cached in docs-cache/kie-jobs-api.md. Not a tool — the registry
walks this package but finds no BaseTool subclasses here.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

CREATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
RECORD_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"

# Transient recordInfo failures (gateway blips, timeouts) must not abandon a
# paid, still-running task — tolerate a few in a row before giving up.
_MAX_CONSECUTIVE_POLL_FAILURES = 3


class KieJobError(RuntimeError):
    """Kie task submission, generation, or polling failure."""


def run_job(
    model: str,
    input_payload: dict[str, Any],
    api_key: str,
    *,
    timeout_seconds: float = 900.0,
    poll_seconds: float = 3.0,
    max_poll_seconds: float = 15.0,
) -> dict[str, Any]:
    """Submit a Kie job and poll to completion.

    Returns {"task_id", "result" (parsed resultJson dict), "credits_consumed"}.
    Raises KieJobError on non-200 create, task failure, repeated poll errors,
    or timeout — always naming the task_id once one exists, so a paid in-flight
    job can be recovered from https://kie.ai/logs before its URLs expire (24h).
    """
    import requests

    # A stray trailing newline in a key (CRLF .env, keys.json) would make
    # requests raise InvalidHeader with the full secret repr'd into the message.
    api_key = (api_key or "").strip()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    resp = requests.post(
        CREATE_URL, headers=headers, json={"model": model, "input": input_payload}, timeout=30
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 200:
        raise KieJobError(f"Kie createTask failed: code={body.get('code')} msg={body.get('msg')}")
    task_id = (body.get("data") or {}).get("taskId")
    if not task_id:
        raise KieJobError(f"Kie createTask returned no taskId (code={body.get('code')})")

    deadline = time.monotonic() + timeout_seconds
    interval = poll_seconds
    consecutive_failures = 0
    while time.monotonic() < deadline:
        time.sleep(interval)
        interval = min(interval * 1.3, max_poll_seconds)
        try:
            poll = requests.get(RECORD_URL, headers=headers, params={"taskId": task_id}, timeout=15)
            poll.raise_for_status()
            data = poll.json().get("data") or {}
        except (requests.RequestException, ValueError) as exc:
            consecutive_failures += 1
            if consecutive_failures >= _MAX_CONSECUTIVE_POLL_FAILURES:
                raise KieJobError(
                    f"Kie task {task_id}: polling failed {consecutive_failures}x in a row "
                    f"({exc}). The task may still complete — check https://kie.ai/logs"
                ) from exc
            continue
        consecutive_failures = 0
        state = data.get("state")
        if state == "success":
            result = data.get("resultJson")
            if isinstance(result, str):
                result = json.loads(result) if result.strip() else {}
            return {
                "task_id": task_id,
                "result": result or {},
                "credits_consumed": data.get("creditsConsumed"),
            }
        if state == "fail":
            raise KieJobError(
                f"Kie task {task_id} failed: {data.get('failCode')} {data.get('failMsg')}"
            )
    raise KieJobError(
        f"Kie task {task_id} timed out after {int(timeout_seconds)}s. "
        f"It may still complete — check https://kie.ai/logs"
    )


def download(url: str, output_path: str | Path, *, timeout: int = 300) -> Path:
    """Stream a result URL (they expire after 24h) to output_path atomically."""
    import requests

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_suffix(out.suffix + ".part")
    with requests.get(url, timeout=timeout, stream=True) as resp:
        resp.raise_for_status()
        with open(part, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    part.replace(out)
    return out
