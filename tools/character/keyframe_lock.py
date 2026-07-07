"""KeyframeLockTool — per-scene identity-locked still: LoRA + Nano Banana Pro + identity block.
Locks the character BEFORE animation (lock-identity-first). QC via IdentityDriftTool after.
"""
from __future__ import annotations


class KeyframeLockTool:  # (BaseTool)
    name = "keyframe_lock"
    category = "character"
    capability = "image"
    providers = ["openrouter", "fal"]
    agent_skills = ["nano-banana-pro", "lora-training"]
    input_schema = {
        "type": "object",
        "required": ["character_id", "scene"],
        "properties": {
            "character_id": {"type": "string"},
            "scene": {"type": "object", "description": "setting/camera/emotion + identity block"},
            "key_alias": {"type": "string"},
        },
    }

    def run(self, params: dict):
        # TODO(M3): compose identity block + LoRA + scene desc -> Nano Banana Pro still.
        raise NotImplementedError("KeyframeLockTool.run (M3)")
