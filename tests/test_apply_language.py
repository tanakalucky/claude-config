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
SCRIPT = ROOT / "scripts/apply_language.py"
SPEC = importlib.util.spec_from_file_location("apply_language", SCRIPT)
SETTINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SETTINGS)


class LanguageSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "settings.json"

    def run_script(self, *args, ok=True, env=None):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.returncode, 0 if ok else 2, result.stderr)
        return json.loads(result.stdout if ok else result.stderr), result

    def test_create_and_second_run_does_not_write(self):
        """新規作成後の再実行では内容も更新時刻も変わらない。"""
        first = SETTINGS.apply_settings(self.path)
        before = self.path.stat().st_mtime_ns
        raw = self.path.read_bytes()
        second = SETTINGS.apply_settings(self.path)
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(self.path.stat().st_mtime_ns, before)
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(json.loads(raw), {"language": "japanese"})
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_replace_only_top_level_value_preserves_format_and_mode(self):
        """既存の権限・入れ子の値・書式・改行・ファイルモードを維持する。"""
        original = '{\r\n  "language" : "english",\r\n  "permissions":{"deny":["Read(.env)"]},\r\n  "nested":{"language":"keep"},"text":"秘密の代わりの合成値"\r\n}\r\n'
        self.path.write_bytes(original.encode())
        self.path.chmod(0o640)
        SETTINGS.apply_settings(self.path)
        self.assertEqual(self.path.read_bytes().decode(), original.replace('"english"', '"japanese"'))
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o640)

    def test_add_preserves_other_keys(self):
        """キー追加でも無関係な設定は保持する。"""
        original = {"model": "example-model", "nested": [True, None, {"language": "unchanged"}], "permissions": {"allow": []}}
        self.path.write_text(json.dumps(original))
        SETTINGS.apply_settings(self.path)
        value = json.loads(self.path.read_text())
        self.assertEqual(value.pop("language"), "japanese")
        self.assertEqual(value, original)

    def test_whitespace_empty_object_and_nonstring_existing_language(self):
        """空オブジェクト、空白、既存の異なる型を正しく扱う。"""
        for raw in ('{}', ' \n{ \t}\n', '{"language":null}', '{"language":{"x":[1,2]}}', '{"language":false}', '{"language":12}'):
            with self.subTest(raw=raw):
                updated = SETTINGS.update_text(raw)
                self.assertEqual(json.loads(updated), {"language": "japanese"})
                self.assertEqual(SETTINGS.update_text(updated), updated)

    def test_dry_run_never_creates_or_changes_file(self):
        """確認だけの実行ではディレクトリも設定も作成しない。"""
        new = Path(self.tmp.name) / "missing" / "settings.json"
        value = SETTINGS.apply_settings(new, dry_run=True)
        self.assertTrue(value["changed"])
        self.assertFalse(new.parent.exists())
        self.path.write_text('{"language":"english"}')
        before = self.path.read_bytes()
        SETTINGS.apply_settings(self.path, dry_run=True)
        self.assertEqual(self.path.read_bytes(), before)

    def test_reject_invalid_json_duplicates_constants_and_wrong_root(self):
        """不正 JSON・重複キー・非標準定数・配列を上書きしない。"""
        for raw in ('', '{', '{"x":1,}', '{"language":"a","language":"b"}', '{"nested":{"x":1,"x":2}}', '{"x":NaN}', '{"x":Infinity}', '[]', 'null'):
            with self.subTest(raw=raw):
                self.path.write_text(raw)
                with self.assertRaises(SETTINGS.SettingsError):
                    SETTINGS.apply_settings(self.path)
                self.assertEqual(self.path.read_text(), raw)

    def test_reject_non_utf8_without_revealing_contents(self):
        """文字コードエラーでも入力内容を出力しない。"""
        raw = b'\xff synthetic-private-content'
        self.path.write_bytes(raw)
        value, result = self.run_script("--settings", self.path, ok=False)
        self.assertIn("error", value)
        self.assertNotIn("synthetic-private-content", result.stdout + result.stderr)
        self.assertEqual(self.path.read_bytes(), raw)

    def test_reject_symlink_target_or_parent_and_hardlink(self):
        """リンク経由で別ファイルを変更しない。"""
        real = Path(self.tmp.name) / "real.json"
        real.write_text('{}')
        self.path.symlink_to(real)
        with self.assertRaises(SETTINGS.SettingsError):
            SETTINGS.apply_settings(self.path)
        self.path.unlink()
        os.link(real, self.path)
        with self.assertRaises(SETTINGS.SettingsError):
            SETTINGS.apply_settings(self.path)
        self.path.unlink()
        directory = Path(self.tmp.name) / "alias"
        directory.symlink_to(Path(self.tmp.name), target_is_directory=True)
        with self.assertRaises(SETTINGS.SettingsError):
            SETTINGS.apply_settings(directory / "settings.json")
        self.assertEqual(real.read_text(), '{}')

    def test_reject_non_settings_name_and_non_regular_target(self):
        """認証ファイル名や通常ファイル以外を対象にしない。"""
        with self.assertRaises(SETTINGS.SettingsError):
            SETTINGS.apply_settings(Path(self.tmp.name) / ".credentials.json")
        self.path.mkdir()
        with self.assertRaises(SETTINGS.SettingsError):
            SETTINGS.apply_settings(self.path)

    def test_changed_target_is_not_overwritten_and_temp_is_removed(self):
        """読み取り後の競合を検出して他の変更を保護する。"""
        self.path.write_text('{}')
        original_reader = SETTINGS.read_existing
        count = 0

        def changed_reader(path):
            nonlocal count
            count += 1
            if count == 2:
                path.write_text('{"other":"concurrent-change"}')
            return original_reader(path)

        with mock.patch.object(SETTINGS, "read_existing", side_effect=changed_reader):
            with self.assertRaises(SETTINGS.SettingsError):
                SETTINGS.apply_settings(self.path)
        self.assertEqual(json.loads(self.path.read_text()), {"other": "concurrent-change"})
        self.assertEqual(list(self.path.parent.glob('.language-*.tmp')), [])

    def test_template_cannot_expand_settings_scope(self):
        """テンプレートに別の設定が混入した場合は拒否する。"""
        template = Path(self.tmp.name) / "template.json"
        template.write_text('{"language":"japanese","permissions":{"allow":["Bash(*)"]}}')
        with mock.patch.object(SETTINGS, "TEMPLATE", template):
            with self.assertRaises(SETTINGS.SettingsError):
                SETTINGS.apply_settings(self.path)
        self.assertFalse(self.path.exists())

    def test_output_only_contains_expected_keys_and_config_dir_is_respected(self):
        """環境変数の保存先を使い、既存の値を出力しない。"""
        self.path.write_text('{"example":"synthetic-private-value"}')
        env = dict(os.environ, CLAUDE_CONFIG_DIR=self.tmp.name)
        value, result = self.run_script(env=env)
        self.assertEqual(set(value), {"changed", "language", "dry_run"})
        self.assertEqual(value["language"], "japanese")
        self.assertNotIn("synthetic-private-value", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
