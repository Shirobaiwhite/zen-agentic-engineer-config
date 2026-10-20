#!/usr/bin/env python3
"""Test iTerm2 mapping bytes and mouse clicks through tmux into a real Codex draft.

Uses an isolated tmux socket and never submits a prompt to a model.
Requires an already signed-in Codex CLI and permission to create local sockets.
"""

import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import struct
import subprocess
import tempfile
import termios
import time


def main():
    repo = Path(__file__).resolve().parents[1]
    for name in ("tmux", "codex"):
        if not shutil.which(name):
            raise SystemExit(f"Missing dependency: {name}")
    mappings = json.loads((repo / "iterm2/Codex Editing.json").read_text())["Profiles"][0]["Keyboard Map"]
    with tempfile.TemporaryDirectory(prefix="codex-edit-check-") as raw:
        root = Path(raw).resolve()
        socket = root / "tmux.sock"
        client = None
        master = None

        def tmux(*args, check=True):
            return subprocess.run(
                ["tmux", "-S", str(socket), *args],
                text=True, capture_output=True, check=check, timeout=10,
            ).stdout

        def drain():
            while select.select([master], [], [], 0)[0]:
                try:
                    if not os.read(master, 65536):
                        break
                except OSError:
                    break

        def snapshot():
            drain()
            text = tmux("capture-pane", "-p", "-t", "edit:0.0")
            position = tmux("display-message", "-p", "-t", "edit:0.0", "#{cursor_x},#{cursor_y}").strip()
            return text, tuple(map(int, position.split(",")))

        def wait_for(predicate, description, timeout=8):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                result = snapshot()
                if predicate(*result):
                    return result
                time.sleep(0.1)
            raise AssertionError(f"Timed out waiting for {description}")

        def send(data):
            os.write(master, data.encode() if isinstance(data, str) else data)
            time.sleep(0.2)

        def shortcut(key):
            mapping = mappings[key]
            assert mapping["Action"] == 11, "Expected iTerm2 Send Hex Code"
            send(bytes(int(part, 16) for part in mapping["Text"].split()))

        try:
            command = shlex.join([
                "codex", "--no-daemon", "-C", str(repo),
                "-c", "tui.fullscreen_transcript=true", "-c", "tui.show_tooltips=false",
            ])
            tmux("-f", str(repo / "tmux.conf"), "new-session", "-d", "-s", "edit", "-x", "120", "-y", "40", command)
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
            env = dict(os.environ, TERM="xterm-256color")
            env.pop("TMUX", None)
            client = subprocess.Popen(
                ["tmux", "-S", str(socket), "attach-session", "-t", "edit"],
                stdin=slave, stdout=slave, stderr=slave, env=env,
            )
            os.close(slave)
            wait_for(lambda text, cursor: "Context" in text and "›" in text, "idle Codex composer", timeout=30)
            send("alpha beta gamma")
            _, end = wait_for(lambda text, cursor: "alpha beta gamma" in text, "typed draft")
            shortcut("0xf702-0x300000")
            wait_for(lambda text, cursor: cursor == (end[0] - 16, end[1]), "Cmd+Left")
            shortcut("0xf703-0x300000")
            wait_for(lambda text, cursor: cursor == end, "Cmd+Right")
            shortcut("0xf702-0x280000")
            wait_for(lambda text, cursor: cursor == (end[0] - 5, end[1]), "Option+Left")
            shortcut("0xf703-0x280000")
            wait_for(lambda text, cursor: cursor == end, "Option+Right")
            print("PASS: line and word navigation", flush=True)

            shortcut("0xd-0x20000")
            send("second line")
            text, cursor = wait_for(lambda text, cursor: "alpha beta gamma" in text and "second line" in text, "Shift+Enter line break")
            rows = text.splitlines()
            row = next(index for index, line in enumerate(rows) if "alpha beta gamma" in line)
            column = rows[row].index("alpha beta gamma") + 6
            offset = tmux("display-message", "-p", "-t", "edit:0.0", "#{pane_left},#{pane_top}").strip()
            left, top = map(int, offset.split(","))
            # Send SGR mouse press/release to the outer tmux client, rather than
            # directly to Codex, to exercise tmux's actual mouse forwarding.
            send(f"\x1b[<0;{left+column+1};{top+row+1}M\x1b[<0;{left+column+1};{top+row+1}m")
            wait_for(lambda text, cursor: cursor == (column, row), "plain click placement")
            send("X")
            wait_for(lambda text, cursor: "alpha Xbeta gamma" in text, "typing at clicked position")
            print("PASS: Shift+Enter and plain-click placement in a multiline draft", flush=True)

            shortcut("0x7f-0x100000")
            wait_for(lambda text, cursor: "› beta gamma" in text and "alpha" not in text, "Cmd+Backspace")
            shortcut("0xf703-0x300000")
            shortcut("0x7f-0x80000")
            wait_for(lambda text, cursor: "› beta" in text and "gamma" not in text, "Option+Backspace")
            print("PASS: delete to line start and delete previous word", flush=True)
        finally:
            tmux("kill-server", check=False)
            if client is not None:
                client.wait(timeout=10)
            if master is not None:
                os.close(master)


if __name__ == "__main__":
    main()
