"""Seedance 2.0 (ByteDance) video generation via the Kie.ai jobs API.

The budget route to Seedance 2.0: Kie's per-second rates run well below the
fal.ai path (720p: ~$0.205/s text-only, ~$0.125/s with references, vs ~$0.30/s
on fal), with the same reference-to-video surface (9 images + 3 videos + 3
audio). Local files are auto-uploaded to Kie temp storage on the same key
(tools/_kie/client.upload_file), so a Kie-only keyframe->animate loop needs
no FAL_KEY. API contract cached in docs-cache/kie-seedance-2.md.
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

# Per-second estimates (text-only, with-ref). The docs advertise a
# with-reference discount, but observed billing (2026-07-07/08 acceptance run)
# was FLAT $0.205/s at 720p on both image_to_video and reference_to_video
# (410cr/10s) — assume no discount so budgets never understate. 4k is
# undocumented, extrapolated 2x 1080p. creditsConsumed is authoritative.
_RATES = {
    "480p": (0.095, 0.095),
    "720p": (0.205, 0.205),
    "1080p": (0.51, 0.51),
    "4k": (1.02, 1.02),
}

_DEFAULT_DURATION = 5


class _InputError(ValueError):
    """Invalid tool inputs — converted to ToolResult(success=False)."""


def _coerce_duration(value: Any) -> int:
    """Accept int, numeric string, or 'auto'/None (both -> default).

    The fal sibling (seedance_video) accepts duration='auto', and selectors
    forward inputs verbatim — this tool must not crash on the same inputs.
    """
    if value is None or value == "auto":
        return _DEFAULT_DURATION
    try:
        return int(value)
    except (TypeError, ValueError):
        raise _InputError(
            f"Invalid duration {value!r} — use an integer 4-15 (seconds) or 'auto'"
        ) from None


def _url_list(value: Any, field: str) -> list[str]:
    """Accept a list of URL strings or a single URL string (planner-friendly)."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(u) for u in value]
    raise _InputError(f"{field} must be an array of URLs, got {type(value).__name__}")


class SeedanceKie(BaseTool):
    name = "seedance_kie"
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
        "Set KIE_AI_API_KEY (or a named PERSONA_KEY_kie_<alias>) to your Kie.ai API key.\n"
        "  Get one at https://kie.ai/api-key"
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
        "lip_sync": True,
        "multi_shot": True,
        "aspect_ratio": True,
        "seed": False,  # Kie's Seedance input has no seed parameter
    }
    best_for = [
        "cheapest Seedance 2.0 route when KIE_AI_API_KEY is available",
        "reference-conditioned generation at discounted with-reference rates",
        "budget-conscious cinematic clips with native synchronized audio",
        "consistent character identity across shots (up to 9 reference images)",
    ]
    not_good_for = [
        "offline generation",
        "seed-reproducible outputs",
    ]
    fallback_tools = ["seedance_video", "seedance_openrouter", "seedance_replicate"]
    # Same model family as seedance_video (fal) — co-rank in the scoring engine.
    quality_score = 0.95

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "3-20,000 characters"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video"],
                "default": "text_to_video",
            },
            "model_variant": {
                "type": "string",
                "enum": ["standard", "fast"],
                "default": "standard",
                "description": "standard = bytedance/seedance-2, fast = bytedance/seedance-2-fast",
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
                "enum": ["16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive"],
                "default": "16:9",
            },
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p", "1080p", "4k"],
                "default": "720p",
            },
            "generate_audio": {
                "type": "boolean",
                "default": True,
                "description": "Generate synchronized audio (increases cost)",
            },
            "image_url": {
                "type": "string",
                "description": "Public start-frame URL for image_to_video (maps to first_frame_url)",
            },
            "image_path": {
                "type": "string",
                "description": (
                    "Local start-frame path — auto-uploaded to Kie temp storage with "
                    "the same key (no FAL_KEY needed)"
                ),
            },
            "end_image_url": {
                "type": "string",
                "description": "Optional public end-frame URL (maps to last_frame_url)",
            },
            "end_image_path": {
                "type": "string",
                "description": "Optional local end-frame path — auto-uploaded via Kie",
            },
            "reference_image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Up to 9 public reference image URLs for reference_to_video",
            },
            "reference_image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Local reference image paths — auto-uploaded via Kie",
            },
            "reference_video_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Up to 3 public reference video URLs (total length <= 15s)",
            },
            "reference_audio_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Up to 3 public reference audio URLs (total length <= 15s)",
            },
            "key_alias": {
                "type": "string",
                "description": (
                    "Named key alias to bill this call to (PERSONA_KEY_kie_<alias> "
                    "in .env, see lib/keyvault.py). Defaults to 'main', then KIE_AI_API_KEY."
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
        "generate_audio", "image_url", "image_path", "end_image_url", "end_image_path",
        "reference_image_urls", "reference_image_paths",
        "reference_video_urls", "reference_audio_urls",
    ]
    side_effects = ["writes video file to output_path", "calls Kie.ai API"]
    user_visible_verification = [
        "Watch generated clip for motion coherence, audio sync, and visual quality"
    ]

    def _get_api_key(self, key_alias: str | None = None) -> str | None:
        """Resolve the Kie key via the named-key vault (PERSONA_KEY_kie_<alias>),
        falling back to the conventional KIE_AI_API_KEY env var."""
        from lib.keyvault import get_vault

        try:
            return get_vault().resolve("kie", key_alias)
        except KeyError:
            return None

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def _has_references(self, inputs: dict[str, Any]) -> bool:
        return bool(
            inputs.get("reference_image_urls")
            or inputs.get("reference_video_urls")
            or inputs.get("reference_audio_urls")
            or inputs.get("image_url")
        )

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Never raises — selectors call this unwrapped during ranking."""
        resolution = inputs.get("resolution", "720p")
        rates = _RATES.get(resolution, _RATES["720p"]) if isinstance(resolution, str) else _RATES["720p"]
        rate = rates[1] if self._has_references(inputs) else rates[0]
        try:
            duration = _coerce_duration(inputs.get("duration"))
        except _InputError:
            duration = _DEFAULT_DURATION
        return round(rate * duration, 2)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 240.0 if inputs.get("model_variant") == "fast" else 300.0

    def _build_payload(self, inputs: dict[str, Any], upload) -> dict[str, Any]:
        """Shape and validate the Kie input payload. Raises _InputError on bad
        inputs; `upload` (path -> public URL) may raise network errors that the
        caller converts to a redacted ToolResult."""
        if not inputs.get("prompt"):
            raise _InputError("'prompt' is required")
        operation = inputs.get("operation", "text_to_video")

        payload: dict[str, Any] = {
            "prompt": inputs["prompt"],
            "duration": _coerce_duration(inputs.get("duration")),
        }
        if inputs.get("aspect_ratio"):
            payload["aspect_ratio"] = inputs["aspect_ratio"]
        if inputs.get("resolution"):
            payload["resolution"] = inputs["resolution"]
        if "generate_audio" in inputs:
            payload["generate_audio"] = inputs["generate_audio"]

        if operation == "image_to_video":
            if inputs.get("image_url"):
                payload["first_frame_url"] = inputs["image_url"]
            elif inputs.get("image_path"):
                payload["first_frame_url"] = upload(inputs["image_path"])
            else:
                raise _InputError(
                    "image_to_video requires 'image_url' (public URL) or 'image_path' (local file)"
                )
            if inputs.get("end_image_url"):
                payload["last_frame_url"] = inputs["end_image_url"]
            elif inputs.get("end_image_path"):
                payload["last_frame_url"] = upload(inputs["end_image_path"])

        if operation == "reference_to_video":
            ref_images = _url_list(inputs.get("reference_image_urls"), "reference_image_urls")
            for local_path in _url_list(inputs.get("reference_image_paths"), "reference_image_paths"):
                ref_images.append(upload(local_path))
            ref_videos = _url_list(inputs.get("reference_video_urls"), "reference_video_urls")
            ref_audio = _url_list(inputs.get("reference_audio_urls"), "reference_audio_urls")
            # Seedance 2.0 reference ceilings: 9 images + 3 videos + 3 audio.
            if len(ref_images) > 9:
                raise _InputError(
                    f"Seedance 2.0 accepts at most 9 reference images; got {len(ref_images)}"
                )
            if len(ref_videos) > 3:
                raise _InputError(
                    f"Seedance 2.0 accepts at most 3 reference videos; got {len(ref_videos)}"
                )
            if len(ref_audio) > 3:
                raise _InputError(
                    f"Seedance 2.0 accepts at most 3 reference audio clips; got {len(ref_audio)}"
                )
            if not (ref_images or ref_videos or ref_audio):
                raise _InputError(
                    "reference_to_video requires at least one reference_*_urls entry"
                )
            if ref_images:
                payload["reference_image_urls"] = ref_images
            if ref_videos:
                payload["reference_video_urls"] = ref_videos
            if ref_audio:
                payload["reference_audio_urls"] = ref_audio
        return payload

    @staticmethod
    def _redact(message: str, api_key: str) -> str:
        return message.replace(api_key, "[REDACTED]") if api_key else message

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        from lib.keyvault import get_vault

        try:
            api_key = get_vault().resolve("kie", inputs.get("key_alias"))
        except KeyError as exc:
            detail = exc.args[0] if exc.args else str(exc)
            return ToolResult(success=False, error=f"{detail} {self.install_instructions}")

        def _upload(path: str) -> str:
            from tools._kie.client import upload_file

            return upload_file(path, api_key)

        try:
            payload = self._build_payload(inputs, _upload)
        except _InputError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(
                success=False,
                error=self._redact(f"Input preparation failed: {exc}", api_key),
            )

        start = time.time()
        variant = inputs.get("model_variant", "standard")
        model = "bytedance/seedance-2-fast" if variant == "fast" else "bytedance/seedance-2"
        cost_estimate = self.estimate_cost(inputs)

        try:
            from tools._kie.client import download, run_job

            job = run_job(model, payload, api_key)
            result_urls = job["result"].get("resultUrls") or []
            if not result_urls:
                return ToolResult(
                    success=False,
                    error=f"Kie task {job['task_id']} succeeded but returned no resultUrls",
                )
            output_path = Path(inputs.get("output_path", "seedance_kie_output.mp4"))
            download(result_urls[0], output_path)
        except Exception as e:
            return ToolResult(
                success=False,
                error=self._redact(f"Seedance 2.0 (Kie) generation failed: {e}", api_key),
            )

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": "seedance",
                "backend": "kie",
                "model": model,
                "prompt": inputs["prompt"],
                "operation": inputs.get("operation", "text_to_video"),
                "variant": variant,
                "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
                "resolution": inputs.get("resolution", "720p"),
                "generate_audio": inputs.get("generate_audio", True),
                "task_id": job["task_id"],
                "credits_consumed": job["credits_consumed"],
                # Remote copies (expire ~24h) — handy for chaining
                "result_urls": result_urls,
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
