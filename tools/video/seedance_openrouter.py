"""Seedance 2.0 (ByteDance) video generation via the OpenRouter videos API.

One-key convenience route: teams already routing LLM traffic through
OpenRouter can generate Seedance clips on the same account and named keys.
480p/720p only; input_references are visual guidance, frame_images are exact
frames. API contract cached in docs-cache/openrouter-video-api.md.
"""

from __future__ import annotations

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
from tools.video.seedance_kie import _InputError, _coerce_duration, _url_list

_CREATE_URL = "https://openrouter.ai/api/v1/videos"

# Doc-derived estimates ("from $0.06726/second", tokens scale with pixels);
# treat as approximate — OpenRouter bills by output tokens.
_RATES = {"480p": 0.068, "720p": 0.152}

# One transient poll blip must not abandon a job whose credits are already spent.
_MAX_CONSECUTIVE_POLL_FAILURES = 3


class SeedanceOpenRouter(BaseTool):
    name = "seedance_openrouter"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "seedance"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set OPENROUTER_API_KEY (or a named PERSONA_KEY_openrouter_<alias>).\n"
        "  Get one at https://openrouter.ai/keys"
    )
    agent_skills = ["seedance-2-0", "ai-video-gen", "seedance-kie"]

    capabilities = ["text_to_video", "image_to_video", "reference_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "multiple_reference_images": True,
        "reference_image": True,
        "native_audio": True,
        "cinematic_quality": True,
        "camera_direction": True,
        "multi_shot": True,
        "aspect_ratio": True,
        "seed": False,
    }
    best_for = [
        "Seedance 2.0 on an existing OpenRouter account/key",
        "billing video generation to per-client OpenRouter named keys",
        "quick 480p/720p clips without adding another provider account",
    ]
    not_good_for = [
        "1080p/4k output (OpenRouter video API caps at 720p)",
        "offline generation",
        "local file inputs (needs public URLs)",
    ]
    fallback_tools = ["seedance_kie", "seedance_video", "seedance_replicate"]
    quality_score = 0.95

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video"],
                "default": "text_to_video",
            },
            "model_variant": {
                "type": "string",
                "enum": ["standard", "fast"],
                "default": "standard",
                "description": "standard = bytedance/seedance-2.0, fast = bytedance/seedance-2.0-fast",
            },
            "duration": {
                "type": "integer",
                "minimum": 4,
                "maximum": 15,
                "default": 5,
                "description": "Video duration in seconds ('auto' also accepted -> 5)",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["1:1", "3:4", "9:16", "4:3", "16:9", "21:9", "9:21"],
                "default": "16:9",
            },
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p"],
                "default": "720p",
            },
            "generate_audio": {"type": "boolean", "default": True},
            "image_url": {
                "type": "string",
                "description": "Public image URL used as the first frame for image_to_video",
            },
            "end_image_url": {
                "type": "string",
                "description": "Optional public last-frame URL for image_to_video",
            },
            "reference_image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Public image URLs sent as input_references (visual guidance)",
            },
            "key_alias": {
                "type": "string",
                "description": (
                    "Named key alias to bill this call to (PERSONA_KEY_openrouter_<alias> "
                    "in .env, see lib/keyvault.py). Defaults to 'main', then OPENROUTER_API_KEY."
                ),
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = [
        "prompt", "operation", "model_variant", "duration", "resolution", "aspect_ratio",
        "generate_audio", "image_url", "end_image_url", "reference_image_urls",
    ]
    side_effects = ["writes video file to output_path", "calls OpenRouter API"]
    user_visible_verification = [
        "Watch generated clip for motion coherence, audio sync, and visual quality"
    ]

    def _get_api_key(self, key_alias: str | None = None) -> str | None:
        """Resolve the OpenRouter key via the named-key vault
        (PERSONA_KEY_openrouter_<alias>), falling back to OPENROUTER_API_KEY."""
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
        """Never raises — selectors call this unwrapped during ranking."""
        rate = _RATES.get(inputs.get("resolution", "720p"), _RATES["720p"])
        try:
            duration = _coerce_duration(inputs.get("duration"))
        except _InputError:
            duration = 5
        return round(rate * duration, 2)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 300.0

    def _build_body(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Shape and validate the OpenRouter request body. Raises _InputError."""
        if not inputs.get("prompt"):
            raise _InputError("'prompt' is required")
        operation = inputs.get("operation", "text_to_video")
        variant = inputs.get("model_variant", "standard")
        body: dict[str, Any] = {
            "model": "bytedance/seedance-2.0-fast" if variant == "fast" else "bytedance/seedance-2.0",
            "prompt": inputs["prompt"],
            "duration": _coerce_duration(inputs.get("duration")),
            "resolution": inputs.get("resolution", "720p"),
            "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
            "generate_audio": inputs.get("generate_audio", True),
        }

        if operation == "image_to_video":
            if not inputs.get("image_url"):
                raise _InputError("image_to_video requires 'image_url' (a public URL)")
            frames = [
                {
                    "type": "image_url",
                    "image_url": {"url": inputs["image_url"]},
                    "frame_type": "first_frame",
                }
            ]
            if inputs.get("end_image_url"):
                frames.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": inputs["end_image_url"]},
                        "frame_type": "last_frame",
                    }
                )
            body["frame_images"] = frames

        if operation == "reference_to_video":
            references = _url_list(inputs.get("reference_image_urls"), "reference_image_urls")
            if not references:
                raise _InputError("reference_to_video requires 'reference_image_urls'")
            body["input_references"] = [
                {"type": "image_url", "image_url": {"url": url}} for url in references
            ]
        return body

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

        try:
            body = self._build_body(inputs)
        except _InputError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=f"Invalid inputs: {exc}")

        import requests

        start = time.time()
        model = body["model"]
        cost_estimate = self.estimate_cost(inputs)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        job_id = None

        try:
            resp = requests.post(_CREATE_URL, headers=headers, json=body, timeout=30)
            resp.raise_for_status()
            job = resp.json()
            job_id = job.get("id")
            if not job_id:
                return ToolResult(
                    success=False,
                    error=f"OpenRouter video job not created: {job.get('error') or job}",
                )
            poll_url = job.get("polling_url") or f"{_CREATE_URL}/{job_id}"

            deadline = time.monotonic() + 900.0
            status = job.get("status", "pending")
            consecutive_failures = 0
            while status not in ("completed", "failed", "cancelled", "expired"):
                if time.monotonic() > deadline:
                    return ToolResult(
                        success=False,
                        error=(
                            f"OpenRouter video job {job_id} timed out after 900s — "
                            "it may still complete on the OpenRouter side"
                        ),
                    )
                time.sleep(15)
                try:
                    poll = requests.get(poll_url, headers=headers, timeout=15)
                    poll.raise_for_status()
                    job = poll.json()
                except (requests.RequestException, ValueError) as poll_exc:
                    consecutive_failures += 1
                    if consecutive_failures >= _MAX_CONSECUTIVE_POLL_FAILURES:
                        raise RuntimeError(
                            f"job {job_id}: polling failed {consecutive_failures}x in a row "
                            f"({poll_exc})"
                        ) from poll_exc
                    continue
                consecutive_failures = 0
                status = job.get("status", "pending")

            if status != "completed":
                return ToolResult(
                    success=False,
                    error=f"OpenRouter video job {job_id} {status}: {job.get('error')}",
                )

            output_path = Path(inputs.get("output_path", "seedance_openrouter_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            unsigned = job.get("unsigned_urls") or []
            if unsigned:
                video_resp = requests.get(unsigned[0], timeout=300)
            else:
                video_resp = requests.get(
                    f"{_CREATE_URL}/{job_id}/content", headers=headers,
                    params={"index": 0}, timeout=300,
                )
            video_resp.raise_for_status()
            output_path.write_bytes(video_resp.content)
        except Exception as e:
            return ToolResult(
                success=False,
                error=self._redact(
                    f"Seedance 2.0 (OpenRouter) generation failed: {e}", api_key
                ),
            )

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": "seedance",
                "backend": "openrouter",
                "model": model,
                "prompt": inputs["prompt"],
                "operation": inputs.get("operation", "text_to_video"),
                "variant": inputs.get("model_variant", "standard"),
                "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
                "resolution": inputs.get("resolution", "720p"),
                "generate_audio": inputs.get("generate_audio", True),
                "job_id": job_id,
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=cost_estimate,
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
