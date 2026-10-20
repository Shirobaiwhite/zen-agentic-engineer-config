#!/usr/bin/env python3
"""Install an iTerm2 dynamic editing profile, inheriting the user's appearance."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "iterm2/Codex Editing.json"


def build_profile(preferences, previous=None):
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))["Profiles"][0]
    parent_guid = preferences.get("Default Bookmark Guid")
    # Re-running after making this profile the default must keep its original
    # parent; a dynamic profile cannot inherit from itself.
    if parent_guid == template["Guid"]:
        parent_guid = (previous or {}).get("Dynamic Profile Parent GUID")
    parent = next(
        (profile for profile in preferences.get("New Bookmarks", [])
         if profile.get("Guid") == parent_guid),
        None,
    )
    if parent is None:
        raise ValueError("Could not find the original default iTerm2 profile")
    profile = dict(previous or {})
    profile.update(template)
    profile["Dynamic Profile Parent GUID"] = parent["Guid"]
    # A Keyboard Map overrides the whole inherited map, so keep other mappings.
    profile["Keyboard Map"] = {
        **parent.get("Keyboard Map", {}),
        **(previous or {}).get("Keyboard Map", {}),
        **template["Keyboard Map"],
    }
    return profile


def save_profile(path, profile, backup_dir):
    content = json.dumps({"Profiles": [profile]}, indent=2, ensure_ascii=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        print(f"Already configured: {path}")
        return
    if path.exists():
        # iTerm2 loads every file in DynamicProfiles, even .bak files. Backups
        # must live outside that watched directory to avoid duplicate GUIDs.
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        saved = backup_dir / f"{path.name}.{stamp}.bak"
        saved.write_bytes(path.read_bytes())
        saved.chmod(0o600)
        print(f"Backed up profile: {saved}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent.parent, delete=False) as stream:
        stream.write(content)
        pending = Path(stream.name)
    pending.replace(path)
    print(f"Installed profile: {path}")


def main():
    support = Path.home() / "Library/Application Support/iTerm2"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preferences", type=Path, help="Read an exported preferences plist (for offline checks)")
    parser.add_argument("--output", type=Path, default=support / "DynamicProfiles/agentic-codex-editing.json")
    parser.add_argument("--set-default", action="store_true", help="Use the editing profile for new iTerm2 windows")
    args = parser.parse_args()
    if args.set_default and args.preferences:
        parser.error("--set-default requires live iTerm2 preferences")
    if args.preferences:
        raw = args.preferences.read_bytes()
    else:
        if sys.platform != "darwin":
            parser.error("Live iTerm2 configuration is available only on macOS")
        raw = subprocess.run(
            ["/usr/bin/defaults", "export", "com.googlecode.iterm2", "-"],
            check=True, capture_output=True,
        ).stdout
    preferences = plistlib.loads(raw)
    previous = None
    if args.output.exists():
        entries = json.loads(args.output.read_text(encoding="utf-8"))["Profiles"]
        if len(entries) != 1:
            raise ValueError("Expected one managed editing profile")
        previous = entries[0]
        template_guid = json.loads(TEMPLATE.read_text(encoding="utf-8"))["Profiles"][0]["Guid"]
        if previous.get("Guid") != template_guid:
            raise ValueError("The destination belongs to a different profile")
    profile = build_profile(preferences, previous)
    backup_dir = args.output.parent.parent / "ProfileBackups"
    save_profile(args.output, profile, backup_dir)
    if args.set_default and preferences.get("Default Bookmark Guid") != profile["Guid"]:
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        saved = backup_dir / f"preferences-before-codex-editing.{stamp}.plist"
        saved.write_bytes(raw)
        saved.chmod(0o600)
        subprocess.run(
            ["/usr/bin/defaults", "write", "com.googlecode.iterm2", "Default Bookmark Guid", "-string", profile["Guid"]],
            check=True,
        )
        print(f"Made Codex Editing the default; previous preferences saved to {saved}")
    print("Open a new window using Profiles > Codex Editing, then run t.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        sys.exit(f"Could not configure iTerm2 ({type(exc).__name__}); no preference contents were printed.")
