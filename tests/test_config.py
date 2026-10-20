"""Regression checks use temporary homes/repos and never call a model."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIGURE = REPO / "scripts/configure_codex.py"
COLLECT = REPO / "skills/smell/scripts/collect_diff.sh"


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agentic-check-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_command(self, *argv, cwd=None, env=None, check=True):
        return subprocess.run(
            argv, cwd=cwd or self.root, env=env,
            text=True, capture_output=True, check=check,
        )

    def test_config_addition_preserves_settings_and_comments(self):
        fixtures = [
            '# personal settings\nmodel = "my-model"\n',
            '[tui] # keep this comment\nnotifications = false\n[mcp_servers.test]\ncommand = "example"\n',
            'tui.notifications = false\n',
            '["tui"]\nnotifications = false\n',
            '[tui.keymap.global]\nopen_transcript = "ctrl-t"\n',
            'developer_instructions = """\n[tui]\nexample only\n"""\n',
        ]
        for index, raw in enumerate(fixtures):
            with self.subTest(raw=raw):
                path = self.root / f"config-{index}.toml"
                path.write_text(raw)
                expected = tomllib.loads(raw)
                expected.setdefault("tui", {})["status_line"] = [
                    "model-with-reasoning", "git-branch", "context-remaining", "current-dir",
                ]
                self.run_command("python3", str(CONFIGURE), str(path))
                self.assertEqual(tomllib.loads(path.read_text()), expected)
                backups = list(self.root.glob(path.name + ".bak.*"))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_text(), raw)
                first = path.read_bytes()
                self.run_command("python3", str(CONFIGURE), str(path))
                self.assertEqual(path.read_bytes(), first)
                self.assertEqual(len(list(self.root.glob(path.name + ".bak.*"))), 1)

    def test_custom_status_line_and_inline_tui_are_preserved(self):
        for raw in ('[tui]\nstatus_line = []\n', 'tui = { notifications = false }\n'):
            with self.subTest(raw=raw):
                path = self.root / "config.toml"
                path.write_text(raw)
                self.run_command("python3", str(CONFIGURE), str(path))
                self.assertEqual(path.read_text(), raw)
                self.assertEqual(list(self.root.glob("*.bak.*")), [])

    def test_invalid_config_is_not_modified_or_echoed(self):
        path = self.root / "invalid.toml"
        raw = 'secret = "do-not-echo\n'
        path.write_text(raw)
        result = self.run_command("python3", str(CONFIGURE), str(path), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("do-not-echo", result.stdout + result.stderr)
        self.assertEqual(path.read_text(), raw)

    def test_config_symlink_survives_update(self):
        target = self.root / "actual.toml"
        target.write_text('model = "my-model"\n')
        link = self.root / "config.toml"
        link.symlink_to(target)
        self.run_command("python3", str(CONFIGURE), str(link))
        self.assertTrue(link.is_symlink())
        self.assertIn("status_line", tomllib.loads(target.read_text())["tui"])

    @unittest.skipUnless(shutil.which("codex"), "Codex CLI is required for config checks")
    def test_config_is_accepted_by_local_codex(self):
        config_dir = self.root / "codex-config"
        self.run_command("python3", str(CONFIGURE), str(config_dir / "config.toml"))
        env = dict(os.environ, CODEX_HOME=str(config_dir))
        result = self.run_command("codex", "features", "list", env=env, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_install_twice_preserves_user_files(self):
        # HOME here is a disposable subprocess home, never the running user's.
        test_home = self.root / "home with spaces"
        test_home.mkdir()
        test_bin = self.root / "bin"
        test_bin.mkdir()
        for name in ("codex", "tmux", "zsh"):
            stub = test_bin / name
            stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(0o755)
        env = dict(os.environ)
        env["HOME"] = str(test_home)
        env["CODEX_HOME"] = str(test_home / "custom codex")
        env["PATH"] = str(test_bin) + os.pathsep + env["PATH"]
        (test_home / ".tmux.conf").write_text("# existing tmux\n")
        (test_home / ".zshrc").write_text("# existing zsh\n")
        skill = test_home / ".agents/skills/smell"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("existing skill\n")
        config = Path(env["CODEX_HOME"]) / "config.toml"
        config.parent.mkdir()
        config.write_text('# keep\nmodel = "my-model"\n')
        legacy = test_home / ".claude/settings.json"
        legacy.parent.mkdir()
        legacy.write_text('{"unchanged":true}\n')

        # Exercise a clone path containing spaces, quotes, and shell syntax.
        clone = self.root / "clone 'quoted' $literal `text`"
        clone.mkdir()
        for name in ("install.sh", "shell.zsh", "tmux.conf", "bin", "scripts", "skills"):
            src = REPO / name
            if src.is_dir():
                shutil.copytree(src, clone / name)
            else:
                shutil.copy2(src, clone / name)
        self.run_command("bash", str(clone / "install.sh"), env=env)
        installed = {path: path.read_bytes() for path in (test_home / ".zshrc", config, legacy)}
        backups = sorted(test_home.rglob("*.bak.*"))
        self.run_command("bash", str(clone / "install.sh"), env=env)
        self.assertEqual(backups, sorted(test_home.rglob("*.bak.*")))
        self.assertEqual(installed, {path: path.read_bytes() for path in installed})
        self.assertEqual((test_home / ".tmux.conf").resolve(), (clone / "tmux.conf").resolve())
        self.assertEqual(skill.resolve(), (clone / "skills/smell").resolve())
        self.assertEqual((test_home / ".local/bin/agentic-clip").resolve(), (clone / "bin/clip").resolve())
        self.assertEqual(legacy.read_text(), '{"unchanged":true}\n')
        zsh = shutil.which("zsh")
        if zsh:
            self.run_command(zsh, "-f", "-c", 'source "$1"; whence -w t', "--", str(test_home / ".zshrc"), env=env)

    def git(self, *args):
        return self.run_command("git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *args).stdout

    def init_git(self):
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")

    def test_diff_collection_includes_all_change_sources_without_mutation(self):
        self.init_git()
        tracked = self.root / "tracked.txt"
        tracked.write_text("base\n")
        self.git("add", "tracked.txt")
        self.git("commit", "-m", "base")
        self.git("checkout", "-b", "feature")
        (self.root / "committed.txt").write_text("committed-marker\n")
        self.git("add", "committed.txt")
        self.git("commit", "-m", "committed change")
        tracked.write_text("base\nstaged-marker\n")
        self.git("add", "tracked.txt")
        tracked.write_text("base\nstaged-marker\nunstaged-marker\n")
        (self.root / "untracked.txt").write_text("new\n")
        subdir = self.root / "subdir"
        subdir.mkdir()
        before = self.git("status", "--porcelain=v1")
        head = self.git("rev-parse", "HEAD")
        result = self.run_command("bash", str(COLLECT), cwd=subdir)
        for marker in ("BASE: main", "+committed-marker", "+staged-marker", "+unstaged-marker", "untracked.txt"):
            self.assertIn(marker, result.stdout)
        self.assertEqual(before, self.git("status", "--porcelain=v1"))
        self.assertEqual(head, self.git("rev-parse", "HEAD"))
        result = self.run_command("bash", str(COLLECT), "--help", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not found", result.stderr)

    def test_diff_collection_reports_unborn_repository(self):
        self.init_git()
        result = self.run_command("bash", str(COLLECT), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no initial commit", result.stderr)

    @unittest.skipUnless(shutil.which("zsh"), "zsh is required for launcher checks")
    def test_launcher_passes_efforts_and_switches_or_attaches(self):
        for nested in (False, True):
            with self.subTest(nested=nested):
                script = r'''
source "$1"
tmux() {
  print -r -- "$*" >> "$AGENTIC_TEST_LOG"
  case "$1" in
    new-session) print '%0' ;;
    split-window) print '%1' ;;
  esac
}
codex() { return 0; }
t
'''
                log = self.root / f"tmux-{nested}.log"
                env = dict(os.environ, AGENTIC_TEST_LOG=str(log))
                if nested:
                    env["TMUX"] = "test-client"
                else:
                    env.pop("TMUX", None)
                self.run_command("zsh", "-f", "-c", script, "--", str(REPO / "shell.zsh"), env=env)
                calls = log.read_text()
                self.assertEqual(calls.count("tui.fullscreen_transcript=true"), 4)
                self.assertEqual(calls.count('model_reasoning_effort="xhigh"'), 2)
                self.assertEqual(calls.count('model_reasoning_effort="high"'), 1)
                self.assertEqual(calls.count('model_reasoning_effort="medium"'), 1)
                self.assertIn("switch-client" if nested else "attach-session", calls)


if __name__ == "__main__":
    unittest.main()
