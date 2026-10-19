#!/usr/bin/env bash
# Install the tmux/zsh workspace and Codex skill without replacing user settings.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_CONFIG_DIR="${CODEX_HOME:-$HOME/.codex}"
ZSHRC="$HOME/.zshrc"
printf -v SHELL_LINE 'source %q  # agentic-config' "$REPO/shell.zsh"

say() { printf '✓ %s\n' "$*"; }
backup() {
  local saved="$1.bak.$(date +%Y%m%d-%H%M%S).$$"
  cp -p "$1" "$saved"
  say "backed up $1 -> $saved"
}
link_file() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
    say "$dst already linked"
    return
  fi
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    local saved="$dst.bak.$(date +%Y%m%d-%H%M%S).$$"
    mv "$dst" "$saved"
    say "backed up $dst -> $saved"
  fi
  ln -s "$src" "$dst"
  say "linked $dst -> $src"
}

# Validate prerequisites before changing user files.
for dependency in codex tmux zsh python3; do
  if ! command -v "$dependency" >/dev/null 2>&1; then
    printf 'Missing dependency: %s. See README.md.\n' "$dependency" >&2
    exit 1
  fi
done
if ! python3 -c 'import tomllib' 2>/dev/null; then
  printf 'Python 3.11 or later is required.\n' >&2
  exit 1
fi

python3 "$REPO/scripts/configure_codex.py" "$CODEX_CONFIG_DIR/config.toml"
link_file "$REPO/tmux.conf" "$HOME/.tmux.conf"
link_file "$REPO/bin/clip" "$HOME/.local/bin/agentic-clip"
link_file "$REPO/skills/smell" "$HOME/.agents/skills/smell"

if [ -f "$ZSHRC" ] && grep -Fqx -- "$SHELL_LINE" "$ZSHRC"; then
  say "$ZSHRC already sources shell.zsh"
else
  if [ -f "$ZSHRC" ]; then
    backup "$ZSHRC"
  fi
  printf '\n%s\n' "$SHELL_LINE" >>"$ZSHRC"
  say "appended source line to $ZSHRC"
fi

cat <<'EOF'

Next steps:
  1. codex login                       # if not already signed in
  2. exec zsh                          # reload shell helpers
  3. tmux source-file ~/.tmux.conf      # if tmux is already running
  4. t                                 # launch the 4-pane Codex workspace
  5. In Codex: $smell main              # review against a target branch
     /statusline                       # customize the native footer
EOF
