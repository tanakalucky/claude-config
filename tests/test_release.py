import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/release.py"
SPEC = importlib.util.spec_from_file_location("release", SCRIPT)
RELEASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELEASE)


class ReleaseFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        self.plugin_path = self.root / RELEASE.PLUGIN_PATH
        self.marketplace_path = self.root / RELEASE.MARKETPLACE_PATH
        self.plugin = {"name": "workflow-kit", "version": "0.1.3"}
        self.marketplace = {
            "name": "workflow-kit-marketplace",
            "plugins": [{"name": "workflow-kit", "source": "./plugins/workflow-kit"}],
        }
        self.write_manifests()
        (self.root / "README.md").write_text("# 設定\n\nバージョン: 0.1.3\n", encoding="utf-8")

    def write_manifests(self):
        for path, value in ((self.plugin_path, self.plugin), (self.marketplace_path, self.marketplace)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding="utf-8")


class ReleaseValidationTests(ReleaseFixture):
    def test_valid_manifests_do_not_require_git_or_write_files(self):
        """Git 管理外でも版の検証ができ、ファイルは変更しない。"""
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(RELEASE.validate_release(self.root), "0.1.3")
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_only_explicit_stable_versions_are_accepted(self):
        """空値、先頭ゼロ、接頭辞、改行、シェル文字列、先行版を受け付けない。"""
        for version in (None, 123, "", "v0.1.3", "0.1", "01.2.3", "1.02.3", "1.2.03",
                        "1.2.3-rc.1", "1.2.3+build", " 1.2.3", "1.2.3\n", "$(touch injected)"):
            with self.subTest(version=version):
                self.plugin["version"] = version
                self.write_manifests()
                with self.assertRaises(RELEASE.ReleaseError):
                    RELEASE.validate_release(self.root)
        self.assertFalse((self.root / "injected").exists())

    def test_missing_version_is_not_inferred(self):
        """version がなければ README や既定値で補わず失敗する。"""
        del self.plugin["version"]
        self.write_manifests()
        with self.assertRaises(RELEASE.ReleaseError):
            RELEASE.validate_release(self.root)

    def test_readme_version_must_exist_once_and_match(self):
        """README の版表示の欠落、重複、不一致を拒否する。"""
        for text in ("# 設定\n", "バージョン: 0.1.2\n", "バージョン: 0.1.3\nバージョン: 0.1.3\n",
                     "バージョン: 0.1.3 \n", "バージョン:0.1.3\n"):
            with self.subTest(text=text):
                (self.root / "README.md").write_text(text, encoding="utf-8")
                with self.assertRaises(RELEASE.ReleaseError):
                    RELEASE.validate_release(self.root)
        (self.root / "README.md").unlink()
        with self.assertRaises(RELEASE.ReleaseError):
            RELEASE.validate_release(self.root)

    def test_invalid_or_ambiguous_manifests_fail_closed(self):
        """不正 JSON、重複キー、非オブジェクト、欠落ファイルを拒否する。"""
        for path in (self.plugin_path, self.marketplace_path):
            original = path.read_bytes()
            for raw in (b"{", b"[]", b"null", b'{"name":"a","name":"b"}',
                        b'{"nested":{"version":"1","version":"2"}}', b'{"value":NaN}', b"\xff"):
                with self.subTest(path=path, raw=raw):
                    path.write_bytes(raw)
                    with self.assertRaises(RELEASE.ReleaseError):
                        RELEASE.validate_release(self.root)
            path.unlink()
            with self.assertRaises(RELEASE.ReleaseError):
                RELEASE.validate_release(self.root)
            path.write_bytes(original)

    def test_marketplace_must_reference_the_single_contained_plugin(self):
        """別のプラグイン、外部 source、複数プラグインへの意図しない変更を止める。"""
        for entry in ({"name": "other", "source": "./plugins/workflow-kit"},
                      {"name": "workflow-kit", "source": "../outside"},
                      {"name": "workflow-kit", "source": {"source": "github", "repo": "someone/repo"}}):
            with self.subTest(entry=entry):
                self.marketplace["plugins"] = [entry]
                self.write_manifests()
                with self.assertRaises(RELEASE.ReleaseError):
                    RELEASE.validate_release(self.root)
        for entries in (None, [], [{}, {}], ["workflow-kit"], {}):
            with self.subTest(entries=entries):
                self.marketplace["plugins"] = entries
                self.write_manifests()
                with self.assertRaises(RELEASE.ReleaseError):
                    RELEASE.validate_release(self.root)

    def test_names_must_remain_compatible(self):
        """既存のプラグイン名と marketplace 名を誤って変更した場合に失敗する。"""
        for manifest in (self.plugin, self.marketplace):
            previous = manifest["name"]
            manifest["name"] = "unexpected"
            self.write_manifests()
            with self.assertRaises(RELEASE.ReleaseError):
                RELEASE.validate_release(self.root)
            manifest["name"] = previous

    def test_marketplace_must_not_duplicate_the_version(self):
        """marketplace 側に別の版の正本を増やさない。"""
        self.marketplace["metadata"] = {}
        for target in (self.marketplace, self.marketplace["plugins"][0], self.marketplace["metadata"]):
            target["version"] = "0.1.3"
            self.write_manifests()
            with self.assertRaises(RELEASE.ReleaseError):
                RELEASE.validate_release(self.root)
            del target["version"]
        self.marketplace["metadata"] = "invalid"
        self.write_manifests()
        with self.assertRaises(RELEASE.ReleaseError):
            RELEASE.validate_release(self.root)

    def test_repository_check_command_succeeds(self):
        """実際のリポジトリに対して公開する検証コマンドが成功する。"""
        result = subprocess.run([sys.executable, str(SCRIPT), "check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(RELEASE.validate_release(ROOT), result.stdout)


class ReleaseTagTests(ReleaseFixture):
    def setUp(self):
        super().setUp()
        self.remote = Path(self.tmp.name) / "origin.git"
        self.git("init", "--bare", str(self.remote))
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Release Test")
        self.git("config", "user.email", "release-test@example.invalid")
        self.git("add", ".")
        self.git("commit", "-m", "検証用の初期状態")
        self.commit = self.git("rev-parse", "HEAD")
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "origin", "main")

    def git(self, *args):
        result = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def remote_ref(self):
        return self.git("ls-remote", "--tags", "origin", "refs/tags/v0.1.3", "refs/tags/v0.1.3^{}")

    def test_create_then_noop_only_tags_the_verified_commit(self):
        """初回だけ検証済みコミットへタグを作成し、同じ状態での再実行は変更しない。"""
        self.assertEqual(RELEASE.create_release_tag(self.root, self.commit), ("v0.1.3", True))
        before = self.remote_ref()
        self.assertEqual(before, f"{self.commit}\trefs/tags/v0.1.3")
        self.assertEqual(RELEASE.create_release_tag(self.root, self.commit), ("v0.1.3", False))
        self.assertEqual(self.remote_ref(), before)
        self.assertEqual(self.git("ls-remote", "origin", "refs/heads/main"), f"{self.commit}\trefs/heads/main")

    def test_existing_annotated_tag_for_same_commit_is_preserved(self):
        """同じコミットの注釈付きタグも、そのタグオブジェクトを変えず受け入れる。"""
        self.git("tag", "-a", "v0.1.3", "-m", "既存の注釈")
        self.git("push", "origin", "refs/tags/v0.1.3")
        before = self.remote_ref()
        self.assertEqual(RELEASE.create_release_tag(self.root, self.commit), ("v0.1.3", False))
        self.assertEqual(self.remote_ref(), before)

    def test_existing_tag_on_another_commit_is_never_moved(self):
        """別コミットにある軽量タグ・注釈付きタグは失敗させ、変更しない。"""
        for annotated in (False, True):
            with self.subTest(annotated=annotated):
                tag_args = ("-a", "-m", "既存の注釈") if annotated else ()
                # 各形式を別名の一時リモートで検証し、タグ削除で試験をリセットしない。
                remote = Path(self.tmp.name) / f"conflict-{annotated}.git"
                self.git("init", "--bare", str(remote))
                self.git("remote", "set-url", "origin", str(remote))
                local_tag = f"fixture-{annotated}"
                self.git("tag", *tag_args, local_tag, self.commit)
                self.git("push", "origin", f"refs/tags/{local_tag}:refs/tags/v0.1.3")
                before = self.remote_ref()
                self.git("commit", "--allow-empty", "-m", "次のコミット")
                current = self.git("rev-parse", "HEAD")
                with self.assertRaises(RELEASE.ReleaseError):
                    RELEASE.create_release_tag(self.root, current)
                self.assertEqual(self.remote_ref(), before)

    def test_unverified_or_dirty_checkout_cannot_create_a_tag(self):
        """SHA 不一致や追跡・未追跡ファイルの変更があればリモートに書き込まない。"""
        for commit in ("0" * 40, "main", "$(touch injected)", self.commit + "\n"):
            with self.subTest(commit=commit):
                with self.assertRaises(RELEASE.ReleaseError):
                    RELEASE.create_release_tag(self.root, commit)
                self.assertEqual(self.remote_ref(), "")
        (self.root / "unexpected.txt").write_text("未追跡の変更", encoding="utf-8")
        with self.assertRaises(RELEASE.ReleaseError):
            RELEASE.create_release_tag(self.root, self.commit)
        (self.root / "unexpected.txt").unlink()
        with (self.root / "README.md").open("a", encoding="utf-8") as stream:
            stream.write("\n未コミットの変更\n")
        with self.assertRaises(RELEASE.ReleaseError):
            RELEASE.create_release_tag(self.root, self.commit)
        self.assertEqual(self.remote_ref(), "")

    def test_unreachable_remote_does_not_mean_the_tag_is_absent(self):
        """リモートの読み取りに失敗したら作成へ進まず、エラーを返す。"""
        self.git("remote", "set-url", "origin", str(Path(self.tmp.name) / "missing.git"))
        with mock.patch.object(RELEASE, "git", wraps=RELEASE.git) as run:
            with self.assertRaises(RELEASE.ReleaseError):
                RELEASE.create_release_tag(self.root, self.commit)
        self.assertFalse(any(call.args[1] == "push" for call in run.call_args_list))

    def test_concurrent_conflicting_tag_is_not_overwritten(self):
        """確認直後に別コミットのタグが作られても通常の push が拒否し、元を守る。"""
        self.git("commit", "--allow-empty", "-m", "競合するコミット")
        other = self.git("rev-parse", "HEAD")
        self.git("checkout", "--detach", self.commit)
        original = RELEASE.remote_tag_commit
        calls = 0

        def race(root, tag):
            nonlocal calls
            result = original(root, tag)
            if calls == 0:
                self.git("push", "origin", f"{other}:refs/tags/v0.1.3")
            calls += 1
            return result

        with mock.patch.object(RELEASE, "remote_tag_commit", side_effect=race):
            with self.assertRaises(RELEASE.ReleaseError):
                RELEASE.create_release_tag(self.root, self.commit)
        self.assertEqual(self.remote_ref(), f"{other}\trefs/tags/v0.1.3")

    def test_only_the_release_tag_is_pushed_even_with_follow_tags_enabled(self):
        """利用環境の followTags 設定が有効でも無関係な注釈付きタグは送らない。"""
        self.git("config", "push.followTags", "true")
        self.git("tag", "-a", "unrelated", "-m", "対象外のタグ")
        RELEASE.create_release_tag(self.root, self.commit)
        self.assertEqual(self.git("ls-remote", "--tags", "origin"), f"{self.commit}\trefs/tags/v0.1.3")

    def test_concurrent_annotated_tag_for_same_commit_is_preserved(self):
        """確認後に同じコミットの注釈付きタグが作成されても、そのまま成功として扱う。"""
        self.git("tag", "-a", "v0.1.3", "-m", "同時実行の注釈")
        original = RELEASE.remote_tag_commit
        calls = 0

        def race(root, tag):
            nonlocal calls
            result = original(root, tag)
            if calls == 0:
                self.git("push", "origin", "refs/tags/v0.1.3")
            calls += 1
            return result

        with mock.patch.object(RELEASE, "remote_tag_commit", side_effect=race):
            self.assertEqual(RELEASE.create_release_tag(self.root, self.commit), ("v0.1.3", False))
        self.assertIn(f"{self.commit}\trefs/tags/v0.1.3^{{}}", self.remote_ref())
        self.assertIn(self.git("rev-parse", "refs/tags/v0.1.3"), self.remote_ref())


if __name__ == "__main__":
    unittest.main()
