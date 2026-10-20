# agentic-config shell helpers; sourced from ~/.zshrc by install.sh.

# Prevent Ctrl-S / Ctrl-Q from freezing the terminal.
stty -ixon 2>/dev/null

# Each invocation creates a fresh four-pane Codex workspace in $PWD.
# After tiling, pane indexes 0/1 use xhigh effort, 2 high, and 3 medium.
# The configured model, permissions, and approval policy remain in effect.
# Fullscreen mode lets Codex handle clicks inside the prompt editor.
t() {
  local dependency
  for dependency in tmux codex; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
      print -u2 "Missing dependency: $dependency. See agentic-config README.md."
      return 1
    fi
  done

  local dir="$PWD"
  local project="${PWD:t}"
  project="${project//[^a-zA-Z0-9_-]/_}"
  local session="codex-${project}-$$-$(date +%s)-$RANDOM"
  local p0 p1 p2 p3

  # Pass commands directly to tmux to avoid racing shell startup/send-keys.
  # These panes share a checkout; use separate worktrees for overlapping edits.
  p0=$(tmux new-session -d -s "$session" -c "$dir" -n codex -x 180 -y 50 -P -F '#{pane_id}' \
       "codex -c 'tui.fullscreen_transcript=true' -c 'model_reasoning_effort=\"xhigh\"'; exec zsh") || return 1
  if ! {
    p1=$(tmux split-window -h -t "$p0" -c "$dir" -P -F '#{pane_id}' \
         "codex -c 'tui.fullscreen_transcript=true' -c 'model_reasoning_effort=\"high\"'; exec zsh") &&
    p2=$(tmux split-window -v -t "$p0" -c "$dir" -P -F '#{pane_id}' \
         "codex -c 'tui.fullscreen_transcript=true' -c 'model_reasoning_effort=\"xhigh\"'; exec zsh") &&
    p3=$(tmux split-window -v -t "$p1" -c "$dir" -P -F '#{pane_id}' \
         "codex -c 'tui.fullscreen_transcript=true' -c 'model_reasoning_effort=\"medium\"'; exec zsh") &&
    tmux select-layout -t "$session:0" tiled &&
    tmux select-pane -t "$p0"
  }; then
    tmux kill-session -t "$session"
    return 1
  fi

  if [ -n "${TMUX:-}" ]; then
    tmux switch-client -t "$session"
  else
    tmux attach-session -t "$session"
  fi
}

alias cwork=t
