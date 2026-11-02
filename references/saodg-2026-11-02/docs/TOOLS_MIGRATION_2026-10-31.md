# 工具路径迁移（2026-10-31）

当前入口统一在 `tools/` 下，`tool/` 已删除。历史验证记录仍保留当时命令，当前使用下表路径。直接CLI与 `python -m tools.<分类>.<模块>` 均可用（测试采用包发现入口）。

| 原路径 | 当前路径 |
| --- | --- |
| `tools/nbt_read.py` | `tools/structures/nbt_read.py` |
| `tools/import_selected_rooms.py` | `tools/structures/import_selected_rooms.py` |
| `tools/import_latest_rooms.py` | `tools/structures/import_latest_rooms.py` |
| `tools/import_boss_and_shrine.py` | `tools/structures/import_boss_and_shrine.py` |
| `tools/room_markers.py` | `tools/structures/room_markers.py` |
| `tools/room_markers.json` | `tools/structures/room_markers.json` |
| `tools/ROOM_MARKERS.md` | `tools/structures/ROOM_MARKERS.md` |
| `tools/generate_ruins.py` | `tools/legacy/generate_ruins.py` |
| `tools/generate_room_models.py` | `tools/legacy/generate_room_models.py` |
| `tools/generate_sealed_models.py` | `tools/legacy/generate_sealed_models.py` |
| `tools/compat_profile_install.py` | `tools/compat/compat_profile_install.py` |
| `tools/generate_compat_patches.py` | `tools/compat/generate_compat_patches.py` |
| `tools/verify_compat_patches.py` | `tools/compat/verify_compat_patches.py` |
| `tools/install_legacy_ui.py` | `tools/compat/install_legacy_ui.py` |
| `tools/install_staged_pack.py` | `tools/compat/install_staged_pack.py` |
| `tools/prepare_admission_probe.py` | `tools/compat/prepare_admission_probe.py` |
| `tools/prepare_pack_rollout.py` | `tools/compat/prepare_pack_rollout.py` |
| `tools/prepare_pack_validation.py` | `tools/compat/prepare_pack_validation.py` |
| `tools/test_compat_profile_install.py` | `tools/compat/test_compat_profile_install.py` |
| `tools/test_install_legacy_ui.py` | `tools/compat/test_install_legacy_ui.py` |
| `tools/test_install_staged_pack.py` | `tools/compat/test_install_staged_pack.py` |
| `tools/export_metrics.py` | `tools/verification/export_metrics.py` |
| `tools/verify_process_recovery.py` | `tools/verification/verify_process_recovery.py` |
| `tools/test_export_metrics.py` | `tools/verification/test_export_metrics.py` |
| `tools/build_verified_release.py` | `tools/release/build_verified_release.py` |
| `tools/generate_event_sounds.py` | `tools/audio/generate_event_sounds.py` |
| `tools/ExportLayoutSamples.java` | `tools/layout/ExportLayoutSamples.java` |
| `tools/render_layout_samples.py` | `tools/layout/render_layout_samples.py` |
| `tools/start_sao_client.ps1` | `tools/launch/start_sao_client.ps1` |
| `tool/structure_world.py` | `tools/structures/structure_world.py` |
| `tool/nbt_world.py` | `tools/structures/nbt_world.py` |
| `tool/test_structure_world.py` | `tools/structures/test_structure_world.py` |
| `tool/README.md` | `tools/structures/README.md` |
| `tool/requirements.txt` | `tools/requirements.txt` |
| `tool/examples/structure_layout.json` | `tools/structures/examples/structure_layout.json` |

统一测试：`python -m unittest discover -s tools -t . -p 'test_*.py' -v`。Python3.12；依赖为 `tools/requirements.txt`。布局图额外使用 `tools/layout/requirements.txt`，声音生成还需要FFmpeg。

原 `tools/structura-render/` 已经独立分类，其本地虚拟环境和下载源码不挪动、不入Git。`.agents/` 是本机忽略的技能安装，不纳入源码分发；当前工作区的NBT技能入口已同步新路径，制作规范仍以仓库文档为准。
