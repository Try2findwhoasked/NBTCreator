"""Locate the shared NBT toolkit without starting its detail console."""
from pathlib import Path
import os
import sys

REPOSITORY = Path(__file__).resolve().parents[3]
TOOLKIT = Path(os.environ.get('SAODG_NBT_TOOLKIT', REPOSITORY/'.agents/skills/minecraft-nbt-modeler')).resolve()
if not (TOOLKIT/'scripts/nbt_model.py').is_file():
    raise RuntimeError('找不到NBT基础工具；请设置 SAODG_NBT_TOOLKIT 或安装工作区 minecraft-nbt-modeler')
sys.path.insert(0, str(TOOLKIT/'scripts'))
