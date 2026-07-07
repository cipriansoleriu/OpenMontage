"""LoRATrainTool — train a character LoRA on fal/Replicate (the real "Soul").
Submit 15-30 reference images -> poll -> return an adapter id stored for reuse across projects.
"""
from __future__ import annotations
from lib.keyvault import get_vault


class LoRATrainTool:  # (BaseTool)
    name = "lora_train"
    category = "character"
    capability = "train"
    providers = ["fal", "replicate"]
    agent_skills = ["lora-training"]
    input_schema = {
        "type": "object",
        "required": ["images", "trigger"],
        "properties": {
            "images": {"type": "array", "items": {"type": "string"}, "minItems": 12},
            "trigger": {"type": "string", "description": "trigger token, e.g. 'ohwx_person'"},
            "steps": {"type": "integer", "default": 1000},
            "provider": {"type": "string", "default": "fal"},
            "key_alias": {"type": "string"},
        },
    }

    def run(self, params: dict):
        provider = params.get("provider", "fal")
        secret = get_vault().resolve(provider, params.get("key_alias"))
        # TODO(M3): submit LoRA training (fal flux-lora / Replicate trainer), poll, return
        #   { lora_id, provider }. Persist to the global character registry for reuse.
        raise NotImplementedError("LoRATrainTool.run (M3)")
