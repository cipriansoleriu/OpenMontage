"""Train a portrait identity LoRA on fal.ai and key it to a reusable character.

The trained adapter (the character's real "Soul") is stored in the character
registry — keyed to the CHARACTER, not a project — so every future project
that casts this character reuses the same identity for free.
API contract cached in docs-cache/fal-flux-lora-trainer.md.
"""

from __future__ import annotations

import time
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
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

_TRAINER_MODEL = "fal-ai/flux-lora-portrait-trainer"
_QUEUE_URL = f"https://queue.fal.run/{_TRAINER_MODEL}"
_MIN_REFS = 5


class LoraTrain(BaseTool):
    name = "lora_train"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "character_identity"
    provider = "fal"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set FAL_KEY (or a named PERSONA_KEY_fal_<alias>) to your fal.ai API key.\n"
        "  Get one at https://fal.ai/dashboard/keys"
    )
    agent_skills = ["lora-training"]

    capabilities = ["lora_training", "identity_training"]
    supports = {"portrait_identity": True, "style_training": False}
    best_for = [
        "locking a recurring character's identity into a reusable flux LoRA",
        "characters that will appear across many projects (train once, reuse everywhere)",
    ]
    not_good_for = [
        "one-off characters (Nano Banana Pro references are cheaper and instant)",
        "style LoRAs (use fal-ai/flux-lora-fast-training with is_style directly)",
    ]
    fallback_tools = []

    input_schema = {
        "type": "object",
        "required": ["character_id"],
        "properties": {
            "character_id": {
                "type": "string",
                "description": "Character in lib/character_registry.py to train and store the adapter on",
            },
            "image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Training images (local paths). Defaults to the character's "
                    "registered reference images. Minimum 5; 15-30 recommended."
                ),
            },
            "trigger_phrase": {
                "type": "string",
                "description": "Token that summons the identity at inference (default: '<character_id> person')",
            },
            "steps": {"type": "integer", "default": 2500},
            "learning_rate": {"type": "number", "default": 0.00009},
            "key_alias": {
                "type": "string",
                "description": (
                    "Named key alias to bill this training to (PERSONA_KEY_fal_<alias> "
                    "in .env, see lib/keyvault.py). Defaults to 'main', then FAL_KEY."
                ),
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=1000, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=0)  # trainings are expensive; never auto-retry
    idempotency_key_fields = ["character_id", "image_paths", "trigger_phrase", "steps"]
    side_effects = [
        "calls fal.ai API (paid training run)",
        "writes adapter record into the character registry",
    ]
    user_visible_verification = [
        "Generate a keyframe with the trained LoRA and confirm identity match vs the references"
    ]

    def _get_api_key(self, key_alias: str | None = None) -> str | None:
        """Resolve the fal key via the named-key vault (PERSONA_KEY_fal_<alias>),
        falling back to the conventional FAL_KEY / FAL_AI_API_KEY env vars."""
        from lib.keyvault import get_vault

        try:
            return get_vault().resolve("fal", key_alias)
        except KeyError:
            return None

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # fal does not publish the trainer price on the API page; ~$2/run is the
        # observed ballpark. Treat as an estimate and check the fal dashboard.
        return 2.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 900.0

    @staticmethod
    def _redact(message: str, api_key: str) -> str:
        return message.replace(api_key, "[REDACTED]") if api_key else message

    @staticmethod
    def _zip_refs(paths: list[Path], zip_path: Path) -> None:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, p in enumerate(paths):
                zf.write(p, arcname=f"{i:03d}{p.suffix.lower()}")

    @staticmethod
    def _upload_archive_fal(zip_path: Path, api_key: str) -> str:
        """fal storage 2-step upload (initiate -> PUT), zip content type."""
        import requests

        init = requests.post(
            "https://rest.alpha.fal.ai/storage/upload/initiate",
            headers={"Authorization": f"Key {api_key}", "Content-Type": "application/json"},
            json={"content_type": "application/zip", "file_name": zip_path.name},
            timeout=30,
        )
        init.raise_for_status()
        data = init.json()
        put = requests.put(
            data["upload_url"],
            headers={"Content-Type": "application/zip"},
            data=zip_path.read_bytes(),
            timeout=300,
        )
        put.raise_for_status()
        return data["file_url"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        from lib.keyvault import get_vault

        try:
            api_key = get_vault().resolve("fal", inputs.get("key_alias"))
        except KeyError as exc:
            detail = exc.args[0] if exc.args else str(exc)
            return ToolResult(success=False, error=f"{detail} {self.install_instructions}")
        api_key = api_key.strip()

        char_id = inputs.get("character_id")
        if not char_id:
            return ToolResult(success=False, error="'character_id' is required")

        from lib.character_registry import CharacterNotFound, CharacterRegistry

        registry = CharacterRegistry()
        missing_refs: list[str] = []
        try:
            registry.get(char_id)
            if inputs.get("image_paths"):
                refs = [Path(p) for p in inputs["image_paths"]]
                missing = [str(p) for p in refs if not p.is_file()]
                if missing:
                    return ToolResult(
                        success=False, error=f"Training images not found: {missing}"
                    )
            else:
                refs = registry.reference_paths(char_id)
                missing_refs = registry.missing_reference_paths(char_id)
        except CharacterNotFound as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=f"Invalid inputs: {exc}")

        if len(refs) < _MIN_REFS:
            return ToolResult(
                success=False,
                error=(
                    f"Need at least {_MIN_REFS} training images for character '{char_id}' "
                    f"(have {len(refs)}; 15-30 recommended). Add refs via the character "
                    f"registry or pass image_paths."
                ),
            )

        trigger_phrase = inputs.get("trigger_phrase") or f"{char_id} person"
        start = time.time()

        import requests

        request_id = None
        try:
            with TemporaryDirectory() as tmp:
                zip_path = Path(tmp) / f"{char_id}-refs.zip"
                self._zip_refs(refs, zip_path)
                images_data_url = self._upload_archive_fal(zip_path, api_key)

            payload: dict[str, Any] = {
                "images_data_url": images_data_url,
                "trigger_phrase": trigger_phrase,
                "steps": inputs.get("steps", 2500),
                "learning_rate": inputs.get("learning_rate", 0.00009),
            }
            headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
            submit = requests.post(_QUEUE_URL, headers=headers, json=payload, timeout=60)
            submit.raise_for_status()
            queue_data = submit.json()
            status_url = queue_data["status_url"]
            response_url = queue_data["response_url"]
            request_id = queue_data.get("request_id")

            # Training runs minutes-to-an-hour; poll patiently, tolerate blips.
            deadline = time.monotonic() + 3600.0
            consecutive_failures = 0
            while True:
                if time.monotonic() > deadline:
                    return ToolResult(
                        success=False,
                        error=(
                            f"LoRA training {request_id} timed out after 3600s — it may "
                            f"still complete; check https://fal.ai/dashboard/requests"
                        ),
                    )
                time.sleep(20)
                try:
                    status_resp = requests.get(status_url, headers=headers, timeout=15)
                    status_resp.raise_for_status()
                    status = status_resp.json().get("status", "UNKNOWN")
                except (requests.RequestException, ValueError) as poll_exc:
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        raise RuntimeError(
                            f"training {request_id}: polling failed 3x in a row ({poll_exc})"
                        ) from poll_exc
                    continue
                consecutive_failures = 0
                if status == "COMPLETED":
                    break
                if status in ("FAILED", "CANCELLED"):
                    return ToolResult(
                        success=False,
                        error=f"LoRA training {request_id} {status.lower()}",
                    )

            result_resp = requests.get(response_url, headers=headers, timeout=30)
            result_resp.raise_for_status()
            result = result_resp.json()
            adapter_url = (result.get("diffusers_lora_file") or {}).get("url")
            if not adapter_url:
                return ToolResult(
                    success=False,
                    error=f"Training {request_id} completed but returned no diffusers_lora_file",
                )
        except Exception as e:
            return ToolResult(
                success=False,
                error=self._redact(f"LoRA training failed: {e}", api_key),
            )

        data: dict[str, Any] = {
            "character_id": char_id,
            "adapter_url": adapter_url,
            "trigger_phrase": trigger_phrase,
            "training_images": len(refs),
            "request_id": request_id,
        }
        if missing_refs:
            data["warning_missing_references"] = (
                f"{len(missing_refs)} registered reference file(s) were missing and "
                f"not trained on: {missing_refs}"
            )
        # The training is PAID and already complete — a registry-write failure
        # (character deleted mid-training, disk full) must never lose the
        # adapter_url or crash the caller.
        try:
            data["adapter_record"] = registry.add_lora(
                char_id,
                {
                    "provider": "fal",
                    "model_family": "flux",
                    "adapter_url": adapter_url,
                    "trigger_phrase": trigger_phrase,
                    "training_task_id": request_id,
                    "steps": inputs.get("steps", 2500),
                    "training_images": len(refs),
                },
            )
        except Exception as exc:
            data["warning_registry_write_failed"] = (
                f"Training succeeded but the adapter was NOT saved to the character "
                f"registry ({exc}). Save it manually: CharacterRegistry().add_lora("
                f"'{char_id}', {{'provider': 'fal', 'model_family': 'flux', "
                f"'adapter_url': '{adapter_url}', 'trigger_phrase': '{trigger_phrase}'}})"
            )
        return ToolResult(
            success=True,
            data=data,
            artifacts=[],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=_TRAINER_MODEL,
        )
