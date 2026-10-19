#!/usr/bin/env python3
"""Check real tmux with fake Codex processes on a private, temporary socket."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


def main():
    repo = Path(__file__).resolve().parents[1]
    real_tmux = shutil.which("tmux")
    if not real_tmux or not shutil.which("zsh"):
        raise SystemExit("tmux and zsh are required")
    with tempfile.TemporaryDirectory(prefix="agentic-tmux-") as raw:
        root = Path(raw).resolve()
        socket = root / "tmux.sock"
        bin_dir = root / "bin"
        bin_dir.mkdir()
        log = root / "calls.log"
        stub = bin_dir / "codex"
        stub.write_text(
            '#!/bin/sh\n'
            'printf "%s|%s|%s\\n" "$TMUX_PANE" "$PWD" "$*" >> "$AGENTIC_SMOKE_LOG"\n'
            'exec sleep 30\n'
        )
        stub.chmod(0o755)
        env = dict(
            os.environ, AGENTIC_TEST_SOCKET=str(socket),
            AGENTIC_TEST_CONF=str(repo / "tmux.conf"),
            AGENTIC_REAL_TMUX=real_tmux, AGENTIC_SMOKE_LOG=str(log),
        )
        env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
        env.pop("TMUX", None)
        script = '''source "$1"
tmux() {
  case "$1" in
    attach-session|switch-client) return 0 ;;
    *) "$AGENTIC_REAL_TMUX" -S "$AGENTIC_TEST_SOCKET" -f "$AGENTIC_TEST_CONF" "$@" ;;
  esac
}
t
'''

        def tmux(*args):
            return subprocess.run(
                [real_tmux, "-S", str(socket), *args],
                env=env, text=True, capture_output=True, check=True, timeout=10,
            ).stdout

        try:
            subprocess.run(
                ["zsh", "-f", "-c", script, "--", str(repo / "shell.zsh")],
                cwd=root, env=env, check=True, timeout=15,
            )
            rows = tmux("list-panes", "-a", "-F", "#{pane_id}|#{pane_index}|#{pane_left}|#{pane_top}").splitlines()
            assert len(rows) == 4, rows
            for _ in range(50):
                if log.exists() and len(log.read_text().splitlines()) == 4:
                    break
                time.sleep(0.1)
            calls = {line.split("|", 1)[0]: line.split("|", 2)[1:] for line in log.read_text().splitlines()}
            assert len(calls) == 4, calls
            for row, effort in zip(rows, ("xhigh", "xhigh", "high", "medium")):
                pane_id, index, left, top = row.split("|")
                cwd, argv = calls[pane_id]
                assert Path(cwd).resolve() == root, cwd
                assert argv == f'-c model_reasoning_effort="{effort}"', argv
                print(f"pane {index}: {effort} effort at ({left}, {top})")
            bindings = tmux("list-keys", "-T", "copy-mode-vi")
            assert "agentic-clip" in bindings and ".claude" not in bindings
            print("PASS: tmux config, four pane startups, directories, effort order, and clipboard binding.")
        finally:
            subprocess.run([real_tmux, "-S", str(socket), "kill-server"], capture_output=True, timeout=10)


if __name__ == "__main__":
    main()
