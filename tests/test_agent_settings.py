import json
import os
import tempfile
import unittest
from pathlib import Path

from devsync import agent_settings
from devsync.config import ConfigError, load
from tests.test_skills import make_cfg

VALUES = {"autoMemoryEnabled": False, "attribution": {"commit": "", "pr": ""},
          "env": {"EXAMPLE_FLAG": "1"}}


class AgentSettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        for d in ["claude", "work"]:
            (self.base / d).mkdir()
        self.cfg = make_cfg(self.base)
        self.cfg.agent_settings_targets = [self.base / "claude/settings.json",
                                           self.base / "work/settings.json",
                                           self.base / "absent/settings.json"]
        self.cfg.agent_settings_values = VALUES

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, rel):
        return json.loads((self.base / rel).read_text())

    def test_merges_without_touching_other_keys(self):
        existing = {"model": "x", "permissions": {"allow": ["Bash(ls)"]},
                    "env": {"OTHER": "keep"}, "attribution": {"commit": "old"}}
        (self.base / "claude/settings.json").write_text(json.dumps(existing))
        os.chmod(self.base / "claude/settings.json", 0o600)
        actions, notes = agent_settings.apply(self.cfg)
        self.assertEqual(notes, [])
        got = self.read("claude/settings.json")
        self.assertEqual(got["model"], "x")
        self.assertEqual(got["permissions"], {"allow": ["Bash(ls)"]})
        self.assertEqual(got["env"], {"OTHER": "keep", "EXAMPLE_FLAG": "1"})
        self.assertEqual(got["attribution"], {"commit": "", "pr": ""})
        self.assertIs(got["autoMemoryEnabled"], False)
        self.assertEqual(os.stat(self.base / "claude/settings.json").st_mode & 0o777, 0o600)
        self.assertEqual(self.read("work/settings.json"), VALUES)  # missing file is created
        self.assertFalse((self.base / "absent").exists())  # no config folder, nothing created
        self.assertEqual(len(actions), 2)
        self.assertEqual(agent_settings.apply(self.cfg), ([], []))  # idempotent
        self.assertTrue(all(r["status"] == "ok" for r in agent_settings.check(self.cfg)))

    def test_false_is_not_mistaken_for_zero(self):
        (self.base / "claude/settings.json").write_text('{"autoMemoryEnabled": 0}')
        agent_settings.apply(self.cfg)
        self.assertIs(self.read("claude/settings.json")["autoMemoryEnabled"], False)

    def test_invalid_json_is_left_alone(self):
        bad = '{"model": "x",, }'
        (self.base / "claude/settings.json").write_text(bad)
        actions, notes = agent_settings.apply(self.cfg)
        self.assertEqual((self.base / "claude/settings.json").read_text(), bad)
        self.assertTrue(any("not valid JSON" in n for n in notes))
        row = next(r for r in agent_settings.check(self.cfg) if "claude" in r["path"])
        self.assertIn("not valid JSON", row["status"])

    def test_only_settings_files_and_no_symlinks(self):
        account = self.base / "claude.json"
        account.write_text('{"oauthAccount": {"emailAddress": "a@example.com"}}')
        link = self.base / "work/settings.json"
        link.symlink_to(account)
        self.cfg.agent_settings_targets = [account, link]
        actions, notes = agent_settings.apply(self.cfg)
        self.assertEqual(actions, [])
        self.assertEqual(len(notes), 2)
        self.assertEqual(json.loads(account.read_text()), {"oauthAccount": {"emailAddress": "a@example.com"}})

    def test_auth_keys_are_refused(self):
        for values in [{"apiKeyHelper": "x"}, {"env": {"ANTHROPIC_API_KEY": "x"}},
                       {"env": {"CLAUDE_CODE_USE_BEDROCK": "1"}}, {"env": {"GITHUB_TOKEN": "x"}},
                       {"forceLoginMethod": "claudeai"}, {"nested": {"oauthThing": 1}}]:
            self.assertTrue(agent_settings.auth_paths(values), values)
            self.cfg.agent_settings_values = values
            actions, notes = agent_settings.apply(self.cfg)
            self.assertEqual(actions, [])
            self.assertIn("auth keys are never managed", notes[0])
        self.assertFalse((self.base / "claude/settings.json").exists())
        self.assertEqual(agent_settings.auth_paths(VALUES), [])

    def test_load_refuses_auth_keys(self):
        cdir = self.base / "conf"
        cdir.mkdir()
        (cdir / "config.toml").write_text(
            '[machines.a]\n[agent_settings]\ntargets = ["~/x/settings.json"]\n'
            '[agent_settings.values.env]\nANTHROPIC_BASE_URL = "https://example.invalid"\n')
        with self.assertRaises(ConfigError):
            load(cdir, "a")
        (cdir / "config.toml").write_text(
            '[machines.a]\n[agent_settings]\ntargets = ["~/x/settings.json"]\n'
            '[agent_settings.values]\nautoMemoryEnabled = false\n'
            'attribution = { commit = "", pr = "" }\n')
        cfg = load(cdir, "a")
        self.assertEqual(cfg.agent_settings_values,
                         {"autoMemoryEnabled": False, "attribution": {"commit": "", "pr": ""}})


if __name__ == "__main__":
    unittest.main()
