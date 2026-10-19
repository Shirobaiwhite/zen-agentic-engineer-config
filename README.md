# Agentic engineer workspace for Codex

A small terminal workflow: tmux + zsh helpers + the native Codex status line + a code-smell review skill. Adapted from the original Claude Code setup ([explainer video](https://youtu.be/ElYxdpYi4U0)).

Requires macOS or Linux with `codex`, `tmux`, `zsh`, and Python 3.11+. Install and sign in to the [Codex CLI](https://learn.chatgpt.com/docs/cli), then run:

```sh
./install.sh
codex login  # if not already signed in
exec zsh
```

If tmux is already running, reload its configuration:

```sh
tmux source-file ~/.tmux.conf
```

From your project directory, run `t` (or `cwork`) to open a fresh four-pane Codex workspace:

| Pane index | Position | Reasoning effort |
| --- | --- | --- |
| 0 | Top left | xhigh |
| 1 | Top right | xhigh |
| 2 | Bottom left | high |
| 3 | Bottom right | medium |

Each pane uses `codex -c 'model_reasoning_effort="…"'`. Your configured model and permissions apply; choose a model that supports these effort levels. Exiting Codex returns to zsh. Each call to `t` creates a separate tmux session, and calling it inside tmux switches to that session.

The panes share the current checkout. Use separate Git worktrees when working on overlapping files. Detach with `Ctrl-b d`; list sessions with `tmux ls`, and reconnect with `tmux attach -t <session-name>`.

The native footer shows the model and reasoning effort, Git branch, context remaining, and current directory. Customize it with `/statusline` inside Codex. It uses [`tui.status_line`](https://learn.chatgpt.com/docs/config-file/config-reference), so a background daemon, hook, or `jq` is not needed. An existing `tui.status_line` is preserved, including an empty list that hides the footer. An inline `tui = { ... }` table is left untouched; use `/statusline` to configure it.

Invoke the review skill inside Codex:

```text
$smell main
```

Or use `$smell` alone to detect `origin/HEAD`, `origin/main`, `main`, `origin/master`, or `master`, in that order. The skill reviews committed, staged, unstaged, and untracked changes using the original Clean Code, Gang of Four, and Python catalogs. Collection is read-only; fixes require a request. Restart Codex if a newly installed skill is not visible. See the official [skill discovery documentation](https://learn.chatgpt.com/docs/build-skills).

The installer makes these changes, with timestamped backups for files it replaces or edits:

| Destination | Change |
| --- | --- |
| `~/.tmux.conf` | Link to this repo's `tmux.conf` |
| `~/.zshrc` | Append a source line for this repo's `shell.zsh` |
| `${CODEX_HOME:-~/.codex}/config.toml` | Add the native footer if no status line is configured; preserve other settings and comments |
| `~/.agents/skills/smell` | Link to `skills/smell` in this repo |
| `~/.local/bin/agentic-clip` | Link to `bin/clip`, used directly by tmux |

Keep this repository in place because the installed helpers are symlinks. Re-running the installer is idempotent. `CODEX_HOME` selects the Codex configuration directory; user skills are installed in `~/.agents/skills`, which Codex discovers independently.

Clipboard copying uses `pbcopy` on macOS, then `wl-copy`, `xclip`, or `xsel` on Linux. Install one of those Linux tools to use the mouse-copy bindings.

If migrating an installed version of this repository, the old `~/.claude` settings and hooks remain untouched. Remove this repository's old `statusLine`, `SessionStart`/`Stop` hook entries, and command symlinks there if you still use Claude Code; the Codex installer no longer manages them. The old status scripts have been removed from this repository.

Run the local checks without changing your home configuration or starting paid model sessions:

```sh
python3 -m unittest discover -s tests -v
```

To also check real tmux pane creation and configuration on a temporary socket (using fake Codex processes), run `python3 tests/smoke_tmux.py`.
