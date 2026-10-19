#!/usr/bin/env bash
# Read-only review context for the smell skill; run from the target repository.
set -euo pipefail
export GIT_OPTIONAL_LOCKS=0

if [ "$#" -gt 1 ]; then
  printf 'usage: collect_diff.sh [base-branch]\n' >&2
  exit 2
fi
root=$(git rev-parse --show-toplevel)
cd "$root"
if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  printf 'ERROR: this repository has no initial commit.\n' >&2
  exit 1
fi

base="${1:-}"
if [ -z "$base" ]; then
  default=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)
  for candidate in "$default" origin/main main origin/master master; do
    if [ -n "$candidate" ] && git rev-parse --verify --end-of-options "$candidate^{commit}" >/dev/null 2>&1; then
      base="$candidate"
      break
    fi
  done
fi
if [ -z "$base" ] || ! base_commit=$(git rev-parse --verify --end-of-options "$base^{commit}" 2>/dev/null); then
  printf 'ERROR: base %s not found. Invoke $smell with an existing branch or commit.\n' "$base" >&2
  exit 1
fi
if ! git merge-base "$base_commit" HEAD >/dev/null 2>&1; then
  printf 'ERROR: no merge base with %s; comparison history may be missing.\n' "$base" >&2
  exit 1
fi

printf '===== BASE: %s =====\n' "$base"
printf '\n----- Stat (committed changes) -----\n'
git --no-pager diff --no-ext-diff --no-textconv --stat "$base_commit...HEAD" --
printf '\n----- Stat (working tree, staged + unstaged) -----\n'
git --no-pager diff --no-ext-diff --no-textconv --stat HEAD --
printf '\n===== Committed diff (-U10) =====\n'
git --no-pager diff --no-ext-diff --no-textconv -U10 "$base_commit...HEAD" --
printf '\n===== Working-tree diff (staged + unstaged, -U10) =====\n'
git --no-pager diff --no-ext-diff --no-textconv -U10 HEAD --
printf '\n===== Untracked files (inspect contents separately) =====\n'
git ls-files --others --exclude-standard
