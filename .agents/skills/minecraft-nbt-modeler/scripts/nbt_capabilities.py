"""Shared application/CLI capability description; no GUI dependency."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def capabilities():
    raw=(ROOT/'tool-catalog.json').read_bytes();data=json.loads(raw)
    from nbt_refine import SUPPORTED_OPERATION_KINDS
    if set(data['tools'])!=SUPPORTED_OPERATION_KINDS:raise ValueError('Engine and shared catalogue differ')
    return dict(data,capabilities_sha256=hashlib.sha256(raw).hexdigest(),gui_required=False,
                default_workspace='agent_cwd',default_assets='nbt_models',skill_entry='.agents/skills/nbtcreator-workspace/SKILL.md',knowledge_config='.nbtcreator/skill-exposure.json',path_policy='request_relative_with_absolute_legacy_compatibility')

if __name__=='__main__':print(json.dumps(capabilities(),ensure_ascii=False,indent=2))
