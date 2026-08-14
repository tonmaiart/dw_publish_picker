from DwPublishPicker.picker_loader import (
    import_all_picker,
    register_menu,
    register_scene_open_callback,
)

__all__ = ["import_all_picker", "register_menu", "register_scene_open_callback"]

# Registered at import time (mirrors MayaToolkit/UkoreMaya/__init__.py's own
# _register_ukore_reference_editor_callback() call) — see plugin.py's
# pre_open_mel hook for why this must be a pre_open_mel import, not post_open_mel.
register_scene_open_callback()