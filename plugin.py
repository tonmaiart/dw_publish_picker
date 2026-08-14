from __future__ import annotations

import sys
from pathlib import Path

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

TOOL_ID = "dw_publish_picker"
TOOL_LABEL = "DW Publish Picker"
MAYA_ENV_BRIDGE_PLUGIN_ID = "maya_launcher_env_bridge"
ANY_VERSION = "*"


def register(api) -> None:
    tool_root = Path(__file__).resolve().parent

    bridge = api.project_plugin_config_store(MAYA_ENV_BRIDGE_PLUGIN_ID)
    if bridge is None:
        return

    # 1. เพิ่ม PYTHONPATH สำหรับ Maya
    contributions = bridge.get("contributions", {})
    contributions[TOOL_ID] = {
        "PYTHONPATH": {ANY_VERSION: [str(tool_root / "maya-scripts")]},
    }
    bridge.set("contributions", contributions)

    labels = bridge.get("labels", {})
    labels[TOOL_ID] = TOOL_LABEL
    bridge.set("labels", labels)

    # 2. เพิ่ม Launch Hook เพื่อลงทะเบียน MenuItem เข้า UkoreMenu เมื่อเปิด Maya
    hooks = bridge.get("launch_hooks", {})
    hooks[TOOL_ID] = {
        "order": 100,
        # Registers the automatic kAfterOpen scene-load callback before
        # MayaLauncher's own `file -open`, so the very first scene open of
        # the session triggers it too (see picker_loader.register_scene_open_callback).
        "pre_open_mel": 'python("import DwPublishPicker");',
        "post_open_mel": 'python("import DwPublishPicker; DwPublishPicker.register_menu()");',
        "diagnostic_msg": "DwPublishPicker menu registered to UkoreMenu",
    }
    bridge.set("launch_hooks", hooks)