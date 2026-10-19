#!/usr/bin/env python3
"""Add a native Codex status line while preserving existing TOML and comments."""

import copy
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import sys
import tomllib


STATUS_LINE = ["model-with-reasoning", "git-branch", "context-remaining", "current-dir"]


def configure(path: Path) -> None:
    # Follow existing config symlinks so their targets are updated in place.
    path = path.expanduser().resolve()
    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    config = tomllib.loads(raw)
    tui = config.get("tui", {})
    if not isinstance(tui, dict):
        raise ValueError("Codex 'tui' must be a TOML table")
    if "status_line" in tui:
        print(f"✓ preserved existing tui.status_line in {path}")
        return

    setting = f"status_line = {json.dumps(STATUS_LINE)}\n"
    expected = copy.deepcopy(config)
    expected.setdefault("tui", {})["status_line"] = STATUS_LINE
    # Only accept a patch if parsing proves that exactly the desired setting
    # changed. Matches inside multiline strings are rejected by this comparison.
    candidates = []
    for header in re.finditer(r"(?m)^[ \t]*\[[ \t]*(?:tui|\"tui\"|'tui')[ \t]*\][ \t]*(?:#[^\n]*)?(?:\n|$)", raw):
        candidates.append(raw[:header.end()] + "\n" + setting + raw[header.end():])
    candidates.extend(("tui." + setting + raw, raw + "\n[tui]\n" + setting))
    updated = None
    for candidate in candidates:
        try:
            if tomllib.loads(candidate) == expected:
                updated = candidate
                break
        except tomllib.TOMLDecodeError:
            continue
    if updated is None:
        print(f"! Preserved {path}: use /statusline in Codex to customize its inline tui table.")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        saved = path.with_name(f"{path.name}.bak.{stamp}")
        shutil.copy2(path, saved)
        print(f"✓ backed up {path} -> {saved}")
    path.write_text(updated, encoding="utf-8")
    print(f"✓ configured native status line in {path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: configure_codex.py <config.toml>")
    try:
        configure(Path(sys.argv[1]))
    except (OSError, ValueError) as exc:
        # Config contents can contain credentials, so report only the error type.
        sys.exit(f"Could not update Codex config ({type(exc).__name__}); check its syntax and permissions.")
