"""Per-scene identity-locked still for a registered character.

Lock-identity-first: every scene gets a keyframe anchored to the character's
canonical references (Nano Banana Pro, default) or trained LoRA (fal flux),
BEFORE any animation spends money. QC with identity_drift afterwards.
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

_IDENTITY_BLOCK = (
    "Maintain the EXACT identity of the person in the reference images: same face "
    "structure, eye color, hair color and texture, skin tone, freckles/marks, and "
    "overall build. Do not beautify, restyle, or age-shift them."
)

_FLUX_LORA_URL = "https://queue.fal.run/fal-ai/flux-lora"


class KeyframeLock(BaseTool):
    name = "keyframe_lock"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "character_identity"
    provider = "multi"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "references mode needs KIE_AI_API_KEY (Nano Banana Pro); lora mode needs FAL_KEY.\n"
        "  Named keys: PERSONA_KEY_kie_<alias> / PERSONA_KEY_fal_<alias>."
    )
    agent_skills = ["nano-banana-pro", "lora-training"]

    capabilities = ["identity_locked_still", "keyframe_generation"]
    supports = {
        "reference_identity": True,
        "lora_identity": True,
        "aspect_ratio": True,
    }
    best_for = [
        "per-scene keyframes that must keep one character's identity locked",
        "character bibles: canonical stills in varied scenes/wardrobe/lighting",
    ]
    not_good_for = [
        "characterless imagery (use image_selector)",
        "unregistered characters (create them in lib/character_registry.py first)",
    ]
    fallback_tools = ["nano_banana_pro"]

    input_schema = {
        "type": "object",
        "required": ["character_id", "prompt"],
        "properties": {
            "character_id": {
                "type": "string",
                "description": "Character in lib/character_registry.py whose identity to lock",
            },
            "prompt": {
                "type": "string",
                "description": "Scene description (setting, action, camera, lighting) — identity comes from the character",
            },
            "mode": {
                "type": "string",
                "enum": ["references", "lora"],
                "default": "references",
                "description": (
                    "references = Nano Banana Pro with the character's reference images "
                    "(instant, ~$0.12); lora = fal flux with the character's trained "
                    "adapter (requires lora_train first)"
                ),
            },
            "resolution": {
                "type": "string",
                "enum": ["1K", "2K", "4K"],
                "default": "1K",
                "description": "references mode only",
            },
            "aspect_ratio": {"type": "string", "default": "16:9"},
            "scene_id": {"type": "string", "description": "Optional scene tag for the board"},
            "key_alias": {
                "type": "string",
                "description": (
                    "Named key alias for the active backend (PERSONA_KEY_kie_<alias> in "
                    "references mode, PERSONA_KEY_fal_<alias> in lora mode)"
                ),
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["character_id", "prompt", "mode", "resolution", "aspect_ratio"]
    side_effects = ["writes image file to output_path", "calls Kie.ai or fal.ai API"]
    user_visible_verification = [
        "Compare the keyframe against the character's reference images (or run identity_drift)"
    ]

    def get_status(self) -> ToolStatus:
        from lib.keyvault import get_vault

        for provider in ("kie", "fal"):
            try:
                get_vault().resolve(provider)
                return ToolStatus.AVAILABLE
            except KeyError:
                continue
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        if inputs.get("mode") == "lora":
            return 0.035  # fal flux-lora ~$0.035/megapixel image
        return 0.24 if inputs.get("resolution") == "4K" else 0.12

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 90.0

    @staticmethod
    def _redact(message: str, api_key: str) -> str:
        return message.replace(api_key, "[REDACTED]") if api_key else message

    def _via_references(
        self, inputs: dict[str, Any], refs: list[Path], scene_prompt: str
    ) -> ToolResult:
        from tools.graphics.nano_banana_pro import NanoBananaPro

        return NanoBananaPro().execute(
            {
                "prompt": scene_prompt,
                "image_paths": [str(p) for p in refs[:8]],
                "resolution": inputs.get("resolution", "1K"),
                "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
                "key_alias": inputs.get("key_alias"),
                "output_path": inputs.get("output_path", "keyframe_lock_output.png"),
                "scene_id": inputs.get("scene_id"),
            }
        )

    # fal flux image_size enums by requested aspect ratio.
    _FAL_IMAGE_SIZES = {
        "16:9": "landscape_16_9",
        "9:16": "portrait_16_9",
        "4:3": "landscape_4_3",
        "3:4": "portrait_4_3",
        "1:1": "square_hd",
    }

    def _via_lora(self, inputs: dict[str, Any], adapter: dict[str, Any]) -> ToolResult:
        from lib.keyvault import get_vault

        adapter_url = adapter.get("adapter_url")
        if not adapter_url:
            return ToolResult(
                success=False,
                error=(
                    f"Character '{inputs.get('character_id')}' flux LoRA record has no "
                    f"adapter_url — re-run lora_train"
                ),
            )
        aspect_ratio = inputs.get("aspect_ratio", "16:9")
        image_size = self._FAL_IMAGE_SIZES.get(aspect_ratio)
        if not image_size:
            return ToolResult(
                success=False,
                error=(
                    f"aspect_ratio '{aspect_ratio}' is not supported in lora mode "
                    f"(fal flux sizes: {', '.join(self._FAL_IMAGE_SIZES)}). "
                    f"Use references mode for other ratios."
                ),
            )

        try:
            api_key = get_vault().resolve("fal", inputs.get("key_alias"))
        except KeyError as exc:
            detail = exc.args[0] if exc.args else str(exc)
            return ToolResult(success=False, error=f"{detail} {self.install_instructions}")
        api_key = api_key.strip()

        import requests

        prompt = f"{adapter.get('trigger_phrase', '')} {inputs['prompt']}".strip()
        payload = {
            "prompt": prompt,
            "loras": [{"path": adapter_url, "scale": 1.0}],
            "image_size": image_size,
            "num_images": 1,
        }
        headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
        try:
            submit = requests.post(_FLUX_LORA_URL, headers=headers, json=payload, timeout=60)
            submit.raise_for_status()
            queue_data = submit.json()
            status_url, response_url = queue_data["status_url"], queue_data["response_url"]
            deadline = time.monotonic() + 300.0
            while time.monotonic() < deadline:
                time.sleep(3)
                status_resp = requests.get(status_url, headers=headers, timeout=15)
                status_resp.raise_for_status()
                status = status_resp.json().get("status")
                if status == "COMPLETED":
                    break
                if status in ("FAILED", "CANCELLED"):
                    return ToolResult(success=False, error=f"flux-lora render {status.lower()}")
            else:
                return ToolResult(success=False, error="flux-lora render timed out after 300s")
            result = requests.get(response_url, headers=headers, timeout=30)
            result.raise_for_status()
            images = result.json().get("images") or []
            if not images:
                return ToolResult(success=False, error="flux-lora returned no images")
            from tools._kie.client import download

            output_path = Path(inputs.get("output_path", "keyframe_lock_output.png"))
            download(images[0]["url"], output_path)
        except Exception as e:
            return ToolResult(
                success=False,
                error=self._redact(f"flux-lora keyframe failed: {e}", api_key),
            )
        return ToolResult(
            success=True,
            data={
                "backend": "fal-flux-lora",
                "prompt": prompt,
                "adapter_url": adapter_url,
                "output_path": str(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            model="fal-ai/flux-lora",
        )

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        char_id = inputs.get("character_id")
        if not char_id:
            return ToolResult(success=False, error="'character_id' is required")
        if not inputs.get("prompt"):
            return ToolResult(success=False, error="'prompt' is required")

        from lib.character_registry import CharacterNotFound, CharacterRegistry

        registry = CharacterRegistry()
        try:
            character = registry.get(char_id)
            refs = registry.reference_paths(char_id)
            missing_refs = registry.missing_reference_paths(char_id)
        except CharacterNotFound as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(
                success=False, error=f"Character registry read failed for '{char_id}': {exc}"
            )

        mode = inputs.get("mode", "references")
        start = time.time()

        if mode == "lora":
            try:
                adapter = registry.latest_lora(char_id, model_family="flux")
            except Exception as exc:
                return ToolResult(
                    success=False,
                    error=f"Character registry read failed for '{char_id}': {exc}",
                )
            if not adapter:
                return ToolResult(
                    success=False,
                    error=(
                        f"Character '{char_id}' has no trained flux LoRA — run lora_train "
                        f"first, or use mode='references'"
                    ),
                )
            result = self._via_lora(inputs, adapter)
        else:
            if not refs:
                return ToolResult(
                    success=False,
                    error=(
                        f"Character '{char_id}' has no reference images — add them via "
                        f"CharacterRegistry.add_reference() first"
                    ),
                )
            scene_prompt = (
                f"{_IDENTITY_BLOCK}\n\nCharacter: {character.get('description') or character['name']}."
                f"\nScene: {inputs['prompt']}"
            )
            result = self._via_references(inputs, refs, scene_prompt)

        if result.success:
            result.data.setdefault("character_id", char_id)
            result.data.setdefault("keyframe_mode", mode)
            if missing_refs:
                result.data["warning_missing_references"] = (
                    f"{len(missing_refs)} registered reference file(s) missing — "
                    f"identity anchoring is weaker than registered: {missing_refs}"
                )
            result.duration_seconds = round(time.time() - start, 2)
        return result
