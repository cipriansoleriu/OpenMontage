"""Nano Banana Pro (Gemini 3.0 Pro Image) identity-locked stills via Kie.ai.

The consistent-character workhorse: up to 8 reference images lock identity,
wardrobe, product, and setting across generations — pass the real photos, never
text-only descriptions of branded objects. Strong text rendering and material
detail. API contract cached in docs-cache/kie-nano-banana-pro.md.
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

_MODEL = "nano-banana-pro"
# ~24 credits ≈ $0.12 at 1K/2K, ~$0.24 at 4K (docs-cache/kie-nano-banana-pro.md);
# recordInfo.creditsConsumed is the authoritative spend.
_COST = {"1K": 0.12, "2K": 0.12, "4K": 0.24}


class NanoBananaPro(BaseTool):
    name = "nano_banana_pro"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "nano_banana"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set KIE_AI_API_KEY (or a named PERSONA_KEY_kie_<alias>) to your Kie.ai API key.\n"
        "  Get one at https://kie.ai/api-key"
    )
    agent_skills = ["nano-banana-pro"]

    capabilities = ["text_to_image", "image_to_image", "reference_conditioned_image"]
    supports = {
        "text_to_image": True,
        "image_to_image": True,
        # Selector-recognized keys: image_selector's edit filter and the
        # scoring boost look for image_edit / multiple_reference_images.
        "image_edit": True,
        "multiple_reference_images": True,
        "reference_images": True,
        "identity_lock": True,
        "text_rendering": True,
        "aspect_ratio": True,
        "high_resolution": True,
        "seed": False,
    }
    best_for = [
        "identity-locked character stills from reference photos (up to 8 references)",
        "branded/product imagery anchored to real product photos",
        "keyframes that must keep the same face/wardrobe/setting across scenes",
        "images containing readable rendered text",
    ]
    not_good_for = [
        "offline generation",
        "local file inputs (Kie needs public URLs)",
        "seed-reproducible outputs",
    ]
    fallback_tools = ["flux_image", "google_imagen", "openai_image"]
    quality_score = 0.95

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Up to 10,000 characters"},
            "image_input": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Up to 8 public reference image URLs (JPEG/PNG/WebP, <=30MB each) — "
                    "identity/wardrobe/product/setting anchors"
                ),
            },
            "image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Selector-canonical alias for image_input — merged into it, "
                    "so image_selector edit-mode calls reach this tool intact"
                ),
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto"],
                "default": "1:1",
            },
            "resolution": {
                "type": "string",
                "enum": ["1K", "2K", "4K"],
                "default": "1K",
            },
            "output_format": {
                "type": "string",
                "enum": ["png", "jpg"],
                "default": "png",
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
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = [
        "prompt", "resolution", "aspect_ratio", "output_format", "image_input", "image_urls",
    ]
    side_effects = ["writes image file to output_path", "calls Kie.ai API"]
    user_visible_verification = [
        "Inspect generated image for identity match with references and prompt fidelity"
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

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return _COST.get(inputs.get("resolution", "1K"), _COST["1K"])

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 60.0

    @staticmethod
    def _redact(message: str, api_key: str) -> str:
        return message.replace(api_key, "[REDACTED]") if api_key else message

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        from lib.keyvault import get_vault
        from tools.video.seedance_kie import _InputError, _url_list

        try:
            api_key = get_vault().resolve("kie", inputs.get("key_alias"))
        except KeyError as exc:
            detail = exc.args[0] if exc.args else str(exc)
            return ToolResult(success=False, error=f"{detail} {self.install_instructions}")

        if not inputs.get("prompt"):
            return ToolResult(success=False, error="'prompt' is required")

        try:
            # image_urls is the selector-canonical alias; merge, preserve order,
            # drop duplicates. A lone string URL is wrapped, not iterated.
            references = _url_list(inputs.get("image_input"), "image_input")
            for url in _url_list(inputs.get("image_urls"), "image_urls"):
                if url not in references:
                    references.append(url)
        except _InputError as exc:
            return ToolResult(success=False, error=str(exc))
        if len(references) > 8:
            return ToolResult(
                success=False,
                error=f"Nano Banana Pro accepts at most 8 reference images; got {len(references)}",
            )

        start = time.time()
        payload: dict[str, Any] = {"prompt": inputs["prompt"]}
        if references:
            payload["image_input"] = references
        if inputs.get("aspect_ratio"):
            payload["aspect_ratio"] = inputs["aspect_ratio"]
        if inputs.get("resolution"):
            payload["resolution"] = inputs["resolution"]
        if inputs.get("output_format"):
            payload["output_format"] = inputs["output_format"]

        ext = inputs.get("output_format", "png")
        try:
            from tools._kie.client import download, run_job

            job = run_job(_MODEL, payload, api_key, timeout_seconds=600.0)
            result_urls = job["result"].get("resultUrls") or []
            if not result_urls:
                return ToolResult(
                    success=False,
                    error=f"Kie task {job['task_id']} succeeded but returned no resultUrls",
                )
            output_path = Path(inputs.get("output_path", f"nano_banana_pro_output.{ext}"))
            download(result_urls[0], output_path)
        except Exception as e:
            return ToolResult(
                success=False,
                error=self._redact(f"Nano Banana Pro generation failed: {e}", api_key),
            )

        return ToolResult(
            success=True,
            data={
                "provider": "nano_banana",
                "backend": "kie",
                "model": _MODEL,
                "prompt": inputs["prompt"],
                "reference_count": len(references),
                "aspect_ratio": inputs.get("aspect_ratio", "1:1"),
                "resolution": inputs.get("resolution", "1K"),
                "task_id": job["task_id"],
                "credits_consumed": job["credits_consumed"],
                "output": str(output_path),
                "output_path": str(output_path),
                "format": ext,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=_MODEL,
        )
