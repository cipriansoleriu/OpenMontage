"""InfiniteTalkTool — fal InfiniteTalk lip-sync (photo/clip + audio -> talking avatar).
The RO / long-script path: pair with ElevenLabs TTS. Better than stock Wav2Lip.
"""
from __future__ import annotations
from lib.keyvault import get_vault


class InfiniteTalkTool:  # (BaseTool)
    name = "infinitetalk"
    category = "avatar"
    capability = "lipsync"
    providers = ["fal", "wavespeed"]
    agent_skills = ["infinitetalk"]
    input_schema = {
        "type": "object",
        "required": ["image", "audio"],
        "properties": {
            "image": {"type": "string"},
            "audio": {"type": "string"},
            "key_alias": {"type": "string"},
        },
    }

    def run(self, params: dict):
        secret = get_vault().resolve("fal", params.get("key_alias"))
        # TODO(M5): submit InfiniteTalk job (image + audio), poll, download.
        raise NotImplementedError("InfiniteTalkTool.run (M5)")
