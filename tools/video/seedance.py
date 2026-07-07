"""SeedanceTool — Seedance 2.0 image->video / reference-to-video with native audio.
Routes to Kie (reference discount ~$4.65/15s 1080p) or OpenRouter (~$5.10), or fal.

NOTE: import paths + BaseTool/ToolResult field names below MUST be reconciled against the
fork's tools/tool_registry.py and an existing tools/video/*.py. This is intended shape.
"""
from __future__ import annotations
import time
# from tools.base import BaseTool, ToolResult      # <-- confirm real module path in fork
from lib.keyvault import get_vault


class SeedanceTool:  # class SeedanceTool(BaseTool):  <-- inherit the real ABC
    name = "seedance"
    category = "video"
    capability = "i2v"                       # image-to-video / reference-to-video
    providers = ["kie", "openrouter", "fal"] # selector ranks these; user preference honored
    native_audio = True
    agent_skills = ["seedance"]              # -> .agents/skills/seedance.md (Layer 3)

    # input_schema / output_schema: declare per the fork's convention (jsonschema).
    input_schema = {
        "type": "object",
        "required": ["image", "prompt"],
        "properties": {
            "image": {"type": "string", "description": "reference/first-frame path"},
            "prompt": {"type": "string"},
            "line": {"type": "string", "description": "dialogue; native lip-sync (EN)"},
            "duration_s": {"type": "number", "default": 8, "maximum": 10},
            "resolution": {"type": "string", "default": "1080p"},
            "provider": {"type": "string"},          # explicit override
            "model": {"type": "string"},
            "key_alias": {"type": "string"},          # SPEC addition B
        },
    }

    def estimate_cost(self, params: dict) -> float:
        # Kie ref ~$0.31/s, OpenRouter ~$0.34/s (token formula), fal $0.682/s (x0.6 w/ ref).
        rate = {"kie": 0.31, "openrouter": 0.34, "fal": 0.41}.get(params.get("provider", "kie"), 0.34)
        return rate * float(params.get("duration_s", 8))

    def run(self, params: dict):  # def run(self, ...) -> ToolResult   <-- match real signature
        t0 = time.time()
        provider = params.get("provider", "kie")
        secret = get_vault().resolve(provider, params.get("key_alias"))  # never logged
        # TODO(M2): submit reference-to-video job to `provider`, poll, download.
        #   - Kie:        POST seedance ref-to-video (line in quotes for native dialogue)
        #   - OpenRouter: video-generation endpoint, poll returned URL
        #   - keep clips <= 10s (15s native-audio drift); pass `image` as reference role
        raise NotImplementedError("SeedanceTool.run (M2)")
        # return ToolResult(success=True, artifacts=[out_path], cost_usd=self.estimate_cost(params),
        #                   duration_seconds=time.time()-t0, model=params.get("model","seedance-2.0"))
