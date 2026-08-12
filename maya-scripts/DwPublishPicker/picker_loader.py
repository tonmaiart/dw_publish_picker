"""DW Publish Picker Loader with Version Resolution and Selection Dialogs."""

from __future__ import annotations

import os
import re
from pathlib import Path
import maya.cmds as cmds

from tmlib.module.PySide import QtWidgets
from PublishApi import repo_paths
from UkoreMenu import registry, MenuItemSpec


_VERSION_PATTERN = re.compile(r"^v(\d{3})$", re.IGNORECASE)


def get_maya_main_window() -> QtWidgets.QWidget | None:
    """Retrieve Maya's main window as a PySide widget parent."""
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == "MayaWindow":
            return widget
    return None


class PickerVersionDialog(QtWidgets.QDialog):
    """Dialog prompting the user when picker version resolution needs decision."""

    RESULT_CANCEL = 0
    RESULT_LATEST = 1
    RESULT_PICK = 2

    def __init__(self, char_name: str, available_versions: list[str], parent=None):
        super().__init__(parent or get_maya_main_window())
        self.setWindowTitle(f"DW Picker — Version Choice ({char_name})")
        self.resize(380, 160)

        self.selected_version: str | None = None
        self.choice = self.RESULT_CANCEL

        # UI Layout
        layout = QtWidgets.QVBoxLayout(self)

        label_msg = QtWidgets.QLabel(
            f"<b>Character:</b> {char_name}<br>"
            f"Please choose how to load the Picker for this character:"
        )
        layout.addWidget(label_msg)

        # Version Combobox (for Manual Pick)
        combo_layout = QtWidgets.QHBoxLayout()
        combo_layout.addWidget(QtWidgets.QLabel("Select Version:"))
        self.version_combo = QtWidgets.QComboBox()
        self.version_combo.addItems(available_versions)
        if available_versions:
            self.version_combo.setCurrentIndex(len(available_versions) - 1)
        combo_layout.addWidget(self.version_combo)
        layout.addLayout(combo_layout)

        # Action Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        latest_str = available_versions[-1] if available_versions else "N/A"
        self.btn_latest = QtWidgets.QPushButton(f"Use Latest ({latest_str})")
        self.btn_pick = QtWidgets.QPushButton("Pick Version")
        self.btn_cancel = QtWidgets.QPushButton("Cancel")

        btn_layout.addWidget(self.btn_latest)
        btn_layout.addWidget(self.btn_pick)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        # Signal Connections
        self.btn_latest.clicked.connect(self._on_latest)
        self.btn_pick.clicked.connect(self._on_pick)
        self.btn_cancel.clicked.connect(self.reject)

    def _on_latest(self):
        self.choice = self.RESULT_LATEST
        self.accept()

    def _on_pick(self):
        self.choice = self.RESULT_PICK
        self.selected_version = self.version_combo.currentText()
        self.accept()


def get_dreamwall_picker_dir() -> Path | None:
    """Resolve physical path for 'DreamwallPicker' Custom Path from active repo."""
    project, repo, repo_path = repo_paths.get_active_repo()
    if not (project and repo and repo_path):
        print("[DW Picker] No active project/repo found in UkoreHub.")
        return None

    custom_paths = repo_paths.get_custom_paths(project.id, repo.id)
    target_cp = None
    for cp in custom_paths:
        cp_id = cp.get("id", "").lower()
        cp_label = cp.get("label", "").lower()
        if "dreamwallpicker" in cp_id or "dreamwallpicker" in cp_label or "dreamwall picker" in cp_label:
            target_cp = cp
            break

    if not target_cp:
        print("[DW Picker] Custom Path 'DreamwallPicker' is not configured for this repo.")
        return None

    rel_path = target_cp.get("path", "").lstrip("/\\")
    full_path = repo_path / rel_path

    if not full_path.is_dir():
        print(f"[DW Picker] Target directory does not exist: {full_path}")
        return None

    return full_path


def get_available_picker_versions(char_dir: Path) -> list[str]:
    """Scans character directory and returns sorted list of vNNN version folder names."""
    if not char_dir.is_dir():
        return []

    versions = []
    for entry in os.listdir(char_dir):
        if (char_dir / entry).is_dir() and _VERSION_PATTERN.match(entry):
            if (char_dir / entry / "Picker.json").exists():
                versions.append(entry)

    versions.sort(key=lambda v: int(_VERSION_PATTERN.match(v).group(1)))
    return versions


def resolve_picker_file(char_dir: Path, char_name: str) -> Path | None:
    """Finds target Picker.json file, prompting User dialog if version needs decision."""
    versions = get_available_picker_versions(char_dir)

    if not versions:
        print(f"[DW Picker] No valid vXXX folders with Picker.json found under: {char_dir}")
        return None

    if len(versions) == 1:
        return char_dir / versions[0] / "Picker.json"

    dialog = PickerVersionDialog(char_name=char_name, available_versions=versions)
    if dialog.exec_() != QtWidgets.QDialog.Accepted or dialog.choice == PickerVersionDialog.RESULT_CANCEL:
        print(f"[DW Picker] Canceled loading picker for '{char_name}'.")
        return None

    target_version = None
    if dialog.choice == PickerVersionDialog.RESULT_LATEST:
        target_version = versions[-1]
    elif dialog.choice == PickerVersionDialog.RESULT_PICK:
        target_version = dialog.selected_version

    if target_version:
        picker_path = char_dir / target_version / "Picker.json"
        if picker_path.exists():
            return picker_path

    return None


def import_all_picker() -> None:
    """Scan Maya scene for character matching folders and open Picker files."""
    picker_dir = get_dreamwall_picker_dir()
    if not picker_dir or not picker_dir.exists():
        cmds.warning("[DW Picker] Cannot import pickers: Invalid or missing DreamwallPicker directory.")
        return

    print(f"[DW Picker] Searching Pickers from: {picker_dir}")

    try:
        import dwpicker
    except ImportError:
        cmds.warning("[DW Picker] Error: 'dwpicker' module is not installed or available in Maya.")
        return

    if hasattr(dwpicker, "show"):
        dwpicker.show()

    if hasattr(dwpicker, "_dwpicker") and hasattr(dwpicker._dwpicker, "clear"):
        dwpicker._dwpicker.clear()

    # ดึงรายการ Namespace ทั้งหมดในฉากครั้งเดียวนอกลูปเพื่อ Performance
    scene_namespaces = [
        ns for ns in cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True)
        if ns not in ("UI", "shared")
    ]

    for char_folder in os.listdir(picker_dir):
        char_dir = picker_dir / char_folder
        if not char_dir.is_dir():
            continue

        # 1. ค้นหา Namespace ที่ตรงกับชื่อโฟลเดอร์ตัวละคร
        matching_ns = [ns for ns in scene_namespaces if char_folder.lower() in ns.lower()]

        # 2. ค้นหา Node ในกรณีไม่มี Namespace (Scene Node)
        ls_scene = cmds.ls(f"{char_folder}*", type="transform") or cmds.ls(f"{char_folder}*")

        # ถ้าไม่เจอทั้ง Namespace และ Node ในฉาก ให้ข้าม
        if not (matching_ns or ls_scene):
            continue

        picker_path = resolve_picker_file(char_dir, char_folder)
        if not picker_path:
            continue

        print(f"[DW Picker] Opening picker: {picker_path}")
        dwpicker.open_picker_file(str(picker_path))

        picker = dwpicker.current()
        if not picker:
            continue

        # กำหนด Target Namespace ให้ถูกต้อง
        if matching_ns:
            new_ns = matching_ns[0]
        else:
            new_ns = ""

        for shape in picker.document.shapes:
            targets = shape.options.get("action.targets", [])
            if not targets:
                continue

            new_targets = []
            for t in targets:
                base_name = t.split(":")[-1]
                if not new_ns or new_ns == ":":
                    new_targets.append(base_name)
                else:
                    new_targets.append(f"{new_ns}:{base_name}")

            shape.options["action.targets"] = new_targets

        picker.update()

    print("[DW Picker] Pickers successfully loaded.")


def register_menu() -> None:
    """Register menu item into UkoreMenu."""
    registry.register_item(
        MenuItemSpec(
            id="dw_publish_picker",
            label="Load DW Publish Pickers",
            category="Animation",
            command=import_all_picker,
            order=30,
        )
    )