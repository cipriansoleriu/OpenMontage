"""Identity-drift QC: score generated stills against a character's references.

Uses a vision model via OpenRouter as the judge (temperature 0, strict-JSON
rubric) instead of local face-embedding ML — this machine's policy is no
CPU-bound local ML, and CI is keyless/headless. Gates keyframes before
animation spends money, and clip frames after.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
# Verified against the live model list 2026-07-07 (vision-capable, cheap).
_DEFAULT_JUDGE = "google/gemini-3.5-flash"
_MAX_IMAGE_BYTES = 8 * 1024 * 1024

_RUBRIC = (
    "You are a strict identity-verification judge for film continuity. The first "
    "{n_refs} image(s) are REFERENCE photos of one person. Each remaining image is a "
    "CANDIDATE. For each candidate, judge whether it depicts the SAME person as the "
    "references: face structure, eye color, hair color/texture, skin tone, "
    "marks/freckles, build. Ignore clothing, pose, lighting, background, and art "
    "style unless they alter identity. Respond with STRICT JSON only:\n"
    '{{"candidates": [{{"index": 1, "same_person": true, "similarity": 0.93, '
    '"differences": ["…"]}}]}}\n'
    "similarity is 0.0-1.0 (1.0 = unmistakably the same person)."
)


def _to_data_url(path: Path) -> str:
    data = path.read_bytes()
    if len(data) > _MAX_IMAGE_BYTES:
        raise ValueError(f"{path} is {len(data)} bytes — max {_MAX_IMAGE_BYTES} for the judge")
    suffix = path.suffix.lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(suffix, "png")
    return f"data:image/{mime};base64,{base64.b64encode(data).decode()}"


class IdentityDrift(BaseTool):
    name = "identity_drift"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "analysis"
    provider = "openrouter"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED  # temperature 0; judge is near-deterministic
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set OPENROUTER_API_KEY (or a named PERSONA_KEY_openrouter_<alias>).\n"
        "  Get one at https://openrouter.ai/keys"
    )
    agent_skills = ["nano-banana-pro"]

    capabilities = ["identity_drift", "character_qc"]
    supports = {"images": True, "video": False}
    best_for = [
        "gating keyframes for identity match before animation spends money",
        "cross-scene consistency checks on generated character stills",
    ]
    not_good_for = [
        "video files (sample frames first with frame_sampler)",
        "offline QC (judge is an API vision model)",
    ]
    fallback_tools = []

    input_schema = {
        "type": "object",
        "required": ["candidate_paths"],
        "properties": {
            "character_id": {
                "type": "string",
                "description": "Registered character whose reference images to judge against",
            },
            "reference_image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Explicit reference images (overrides character_id refs)",
            },
            "candidate_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Generated stills to score against the references",
            },
            "threshold": {
                "type": "number",
                "default": 0.75,
                "description": "Minimum similarity (0-1) for a candidate to pass",
            },
            "judge_model": {
                "type": "string",
                "default": _DEFAULT_JUDGE,
                "description": "OpenRouter vision model id used as the judge",
            },
            "key_alias": {
                "type": "string",
                "description": (
                    "Named key alias to bill the judge call to (PERSONA_KEY_openrouter_"
                    "<alias> in .env, see lib/keyvault.py)"
                ),
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=10, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = [
        "character_id", "reference_image_paths", "candidate_paths", "threshold", "judge_model",
    ]
    side_effects = ["calls OpenRouter API"]
    user_visible_verification = [
        "Spot-check flagged candidates by eye — the judge is advisory, not infallible"
    ]

    def _get_api_key(self, key_alias: str | None = None) -> str | None:
        from lib.keyvault import get_vault

        try:
            return get_vault().resolve("openrouter", key_alias)
        except KeyError:
            return None

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        candidates = inputs.get("candidate_paths") or []
        n = len(candidates) if isinstance(candidates, (list, tuple)) else 1
        return round(0.01 * max(n, 1), 2)  # flash-tier vision tokens; generous ceiling

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 30.0

    @staticmethod
    def _redact(message: str, api_key: str) -> str:
        return message.replace(api_key, "[REDACTED]") if api_key else message

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        from lib.keyvault import get_vault

        try:
            api_key = get_vault().resolve("openrouter", inputs.get("key_alias"))
        except KeyError as exc:
            detail = exc.args[0] if exc.args else str(exc)
            return ToolResult(success=False, error=f"{detail} {self.install_instructions}")
        api_key = api_key.strip()

        candidates_in = inputs.get("candidate_paths")
        if isinstance(candidates_in, str):
            candidates_in = [candidates_in]
        if not isinstance(candidates_in, (list, tuple)) or not candidates_in or not all(
            isinstance(p, (str, Path)) for p in candidates_in
        ):
            return ToolResult(
                success=False, error="'candidate_paths' must be a non-empty array of path strings"
            )

        refs_in = inputs.get("reference_image_paths")
        if isinstance(refs_in, str):
            refs_in = [refs_in]
        if refs_in is not None and (
            not isinstance(refs_in, (list, tuple))
            or not all(isinstance(p, (str, Path)) for p in refs_in)
        ):
            return ToolResult(
                success=False, error="'reference_image_paths' must be an array of path strings"
            )
        if not refs_in:
            char_id = inputs.get("character_id")
            if not char_id:
                return ToolResult(
                    success=False,
                    error="Provide 'reference_image_paths' or a registered 'character_id'",
                )
            from lib.character_registry import CharacterNotFound, CharacterRegistry

            try:
                refs_in = [str(p) for p in CharacterRegistry().reference_paths(char_id)]
            except CharacterNotFound as exc:
                return ToolResult(success=False, error=str(exc))
            except Exception as exc:
                return ToolResult(
                    success=False,
                    error=f"Character registry read failed for '{char_id}': {exc}",
                )
        if not refs_in:
            return ToolResult(success=False, error="No reference images available to judge against")

        refs = [Path(p) for p in refs_in][:4]  # cap prompt size
        candidates = [Path(p) for p in candidates_in]
        missing = [str(p) for p in [*refs, *candidates] if not p.is_file()]
        if missing:
            return ToolResult(success=False, error=f"Images not found: {missing}")

        threshold_in = inputs.get("threshold")
        try:
            threshold = 0.75 if threshold_in is None else float(threshold_in)
        except (TypeError, ValueError):
            return ToolResult(
                success=False, error=f"'threshold' must be a number 0-1, got {threshold_in!r}"
            )
        judge_model = inputs.get("judge_model") or _DEFAULT_JUDGE
        start = time.time()

        try:
            content: list[dict[str, Any]] = [
                {"type": "text", "text": _RUBRIC.format(n_refs=len(refs))}
            ]
            for p in [*refs, *candidates]:
                content.append(
                    {"type": "image_url", "image_url": {"url": _to_data_url(p)}}
                )

            import requests

            resp = requests.post(
                _CHAT_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": judge_model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": content}],
                },
                timeout=120,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            verdict = json.loads(raw)
            judged = verdict.get("candidates") or []
            if len(judged) != len(candidates):
                return ToolResult(
                    success=False,
                    error=(
                        f"Judge returned {len(judged)} verdicts for {len(candidates)} "
                        f"candidates — raw: {raw[:400]}"
                    ),
                )
            # The judge is an LLM returning untrusted JSON — parse inside the
            # guard so type surprises fail closed instead of crashing the gate.
            results = []
            for path, j in zip(candidates, judged):
                if not isinstance(j, dict):
                    raise ValueError(f"judge verdict entry is not an object: {j!r}")
                similarity = float(j.get("similarity") or 0.0)
                results.append(
                    {
                        "candidate": str(path),
                        "similarity": similarity,
                        "drift": round(1.0 - similarity, 3),
                        "same_person": bool(j.get("same_person")),
                        "passed": similarity >= threshold and bool(j.get("same_person")),
                        "differences": j.get("differences") or [],
                    }
                )
        except Exception as e:
            return ToolResult(
                success=False,
                error=self._redact(f"Identity drift judging failed: {e}", api_key),
            )

        all_passed = all(r["passed"] for r in results)
        return ToolResult(
            success=True,
            data={
                "passed": all_passed,
                "threshold": threshold,
                "judge_model": judge_model,
                "reference_count": len(refs),
                "results": results,
            },
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=judge_model,
        )
