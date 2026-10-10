import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/apply_settings.py"
SPEC = importlib.util.spec_from_file_location("apply_settings", SCRIPT)
SETTINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SETTINGS)


class SharedSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "personal" / "settings.json"
        self.source = Path(self.tmp.name) / "shared.json"
        self.source.write_text('{"language":"japanese"}')
        patcher = mock.patch.object(SETTINGS, "SOURCE", self.source)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_target(self, value):
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.target.write_text(json.dumps(value))

    def test_create_then_noop_keeps_bytes_and_mtime(self):
        """初回は作成し、再実行では書き込まない。"""
        self.assertEqual(SETTINGS.apply_settings(self.target)["changed_keys"], ["language"])
        original = self.target.read_bytes()
        before = self.target.stat().st_mtime_ns
        self.assertEqual(SETTINGS.apply_settings(self.target)["changed_keys"], [])
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual(self.target.stat().st_mtime_ns, before)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)

    def test_recursive_merge_preserves_unmentioned_keys(self):
        """共通設定の指定値を反映し、未指定のキーを各階層で保持する。"""
        self.write_target({"language":"english", "model":"keep", "display":{"theme":"dark", "size":12}})
        self.source.write_text('{"language":"japanese","display":{"size":14}}')
        result = SETTINGS.apply_settings(self.target)
        self.assertEqual(result["changed_keys"], ["display", "language"])
        self.assertEqual(json.loads(self.target.read_text()), {"language":"japanese", "model":"keep", "display":{"theme":"dark", "size":14}})

    def test_arrays_replace_and_null_is_an_explicit_value(self):
        """配列は連結せず置き換え、null も明示した値として扱う。"""
        self.write_target({"items":[1,2], "value":"old", "other":3})
        self.source.write_text('{"items":[4],"value":null}')
        SETTINGS.apply_settings(self.target)
        self.assertEqual(json.loads(self.target.read_text()), {"items":[4], "value":None, "other":3})

    def test_objects_replace_scalars_and_empty_objects_preserve_existing_children(self):
        """共通オブジェクトは既存の異なる型を置き換え、既存オブジェクトの子は保持する。"""
        self.write_target({"nested":"old", "keep":{"child":1}, "scalar":{"old":1}})
        self.source.write_text('{"nested":{"child":2},"keep":{},"scalar":false}')
        SETTINGS.apply_settings(self.target)
        self.assertEqual(json.loads(self.target.read_text()), {"nested":{"child":2}, "keep":{"child":1}, "scalar":False})

    def test_json_types_remain_distinct(self):
        """真偽値と数値が等しいと誤判定しない。"""
        self.write_target({"value":1})
        self.source.write_text('{"value":true}')
        self.assertEqual(SETTINGS.apply_settings(self.target)["changed_keys"], ["value"])
        self.assertIs(json.loads(self.target.read_text())["value"], True)

    def test_dry_run_does_not_create_or_change_anything(self):
        """確認モードでは値を出力せず、フォルダも作成しない。"""
        result = SETTINGS.apply_settings(self.target, dry_run=True)
        self.assertEqual(result, {"changed_keys":["language"], "dry_run":True})
        self.assertFalse(self.target.parent.exists())
        self.write_target({"language":"english"})
        before = self.target.read_bytes()
        SETTINGS.apply_settings(self.target, dry_run=True)
        self.assertEqual(self.target.read_bytes(), before)

    def test_invalid_json_duplicates_and_unsupported_values_are_refused(self):
        """不正な既存設定を上書きしない。"""
        self.target.parent.mkdir()
        for raw in (b'', b'{', b'{"x":1,}', b'{"x":1,"x":2}', b'{"a":{"x":1,"x":2}}', b'{"x":NaN}', b'{"x":1e999}', b'{"x":"\\ud800"}', b'[]', b'null', b'\xff'):
            with self.subTest(raw=raw):
                self.target.write_bytes(raw)
                with self.assertRaises(SETTINGS.SettingsError):
                    SETTINGS.apply_settings(self.target)
                self.assertEqual(self.target.read_bytes(), raw)

    def test_invalid_source_does_not_touch_target(self):
        """共通設定が壊れている場合も個人設定を保持する。"""
        self.write_target({"keep":"unchanged"})
        before = self.target.read_bytes()
        self.source.write_text('{"language":"a","language":"b"}')
        with self.assertRaises(SETTINGS.SettingsError):
            SETTINGS.apply_settings(self.target)
        self.assertEqual(self.target.read_bytes(), before)

    def test_symlinks_hardlinks_and_wrong_filename_are_refused(self):
        """別のファイルへつながる対象を拒否する。"""
        self.target.parent.mkdir()
        self.target.symlink_to(self.source)
        with self.assertRaises(SETTINGS.SettingsError):
            SETTINGS.apply_settings(self.target)
        self.target.unlink()
        os.link(self.source, self.target)
        with self.assertRaises(SETTINGS.SettingsError):
            SETTINGS.apply_settings(self.target)
        self.target.unlink()
        with self.assertRaises(SETTINGS.SettingsError):
            SETTINGS.apply_settings(self.target.with_name('.credentials.json'))
        alias = Path(self.tmp.name) / "alias"
        alias.symlink_to(self.target.parent, target_is_directory=True)
        with self.assertRaises(SETTINGS.SettingsError):
            SETTINGS.apply_settings(alias / "settings.json")

    def test_mode_is_preserved_and_atomic_failure_leaves_original(self):
        """書き込み失敗でも元の設定を残し、一時ファイルを片付ける。"""
        self.write_target({"keep":"original"})
        self.target.chmod(0o640)
        before = self.target.read_bytes()
        with mock.patch.object(SETTINGS.os, "replace", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                SETTINGS.apply_settings(self.target)
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(list(self.target.parent.glob('.settings-*.tmp')), [])
        SETTINGS.apply_settings(self.target)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o640)

    def test_concurrent_change_is_not_overwritten(self):
        """読み取り後の変更を検出し、他の編集を保持する。"""
        self.write_target({"original":True})
        reader = SETTINGS.read_file
        reads = 0

        def changing_reader(path):
            nonlocal reads
            if path == self.target:
                reads += 1
                if reads == 2:
                    self.target.write_text('{"other":"changed"}')
            return reader(path)

        with mock.patch.object(SETTINGS, "read_file", side_effect=changing_reader):
            with self.assertRaises(SETTINGS.SettingsError):
                SETTINGS.apply_settings(self.target)
        self.assertEqual(json.loads(self.target.read_text()), {"other":"changed"})
        self.assertEqual(list(self.target.parent.glob('.settings-*.tmp')), [])

    def test_cli_honors_config_dir_and_reports_only_changed_keys(self):
        """個人設定の保存先を尊重し、既存値を出力しない。"""
        self.write_target({"example":"synthetic-private-value"})
        env = dict(os.environ, CLAUDE_CONFIG_DIR=str(self.target.parent))
        result = subprocess.run([sys.executable, str(SCRIPT), "--dry-run"], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"changed_keys":["language"], "dry_run":True})
        self.assertNotIn("synthetic-private-value", result.stdout + result.stderr)
        self.assertEqual(json.loads(self.target.read_text()), {"example":"synthetic-private-value"})


if __name__ == "__main__":
    unittest.main()
