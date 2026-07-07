"""IdentityDriftTool — QC: compare a clip/still's face crop to the character reference sheet
and return a drift score. Gates keyframes (pre-animate) and clips (cross-scene).
"""
from __future__ import annotations


class IdentityDriftTool:  # (BaseTool)
    name = "identity_drift"
    category = "analysis"
    capability = "review"
    providers = ["local"]        # face-embedding compare; can run locally
    agent_skills = []
    input_schema = {
        "type": "object",
        "required": ["reference_sheet", "target"],
        "properties": {
            "reference_sheet": {"type": "array", "items": {"type": "string"}},
            "target": {"type": "string", "description": "image or video path"},
            "threshold": {"type": "number", "default": 0.35},
        },
    }

    def run(self, params: dict):
        # TODO(M3): extract face crop(s) from target, embed, cosine-compare to reference sheet;
        #   return { drift: 0..1, pass: bool, notes }.
        raise NotImplementedError("IdentityDriftTool.run (M3)")
