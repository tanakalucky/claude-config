"""コピー後の配布物が単独で読めることとツール固有境界を検証する。"""

import hashlib
from pathlib import Path
import re
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
DISTRIBUTION = ("AGENTS.md", "CLAUDE.md", ".ai-config", ".agents", ".claude")
NAMES = ("clarify", "review", "review-correctness", "review-tests", "review-design")


class LayoutTests(unittest.TestCase):
    def test_copied_bundle_has_no_external_reference(self):
        """生成処理なしで、配布物のsymlinkとMarkdown参照を解決する。"""
        # 準備 (Arrange)
        with tempfile.TemporaryDirectory() as directory:
            copied = (Path(directory) / "application").resolve()
            copied.mkdir()

            # 実行 (Act)
            copy_distribution(copied)
            links = [(path, link, (path.parent / link).resolve(strict=True))
                     for path in distribution_markdown(copied) for link in local_links(path)]
            claude = copied / "CLAUDE.md"

            # 検証 (Assert)
            self.assertTrue(claude.is_symlink())
            self.assertEqual(claude.readlink(), Path("AGENTS.md"))
            self.assertEqual(claude.read_bytes(), (copied / "AGENTS.md").read_bytes())
            self.assertIn(".ai-config/rules/coding.md", local_links(copied / "AGENTS.md"))
            for path, link, resolved in links:
                with self.subTest(source=path.relative_to(copied), target=link):
                    self.assertTrue(resolved.is_relative_to(copied))
                    self.assertTrue(resolved.is_file())

    def test_both_hosts_have_all_entrypoints(self):
        """既存の他skillとの共存を許し、配布対象5入口を検証する。"""
        # 準備 (Arrange)
        paths = [ROOT / f"{host}/skills/{prefix}{name}/SKILL.md"
                 for host, prefix in ((".claude", ""), (".agents", "config-")) for name in NAMES]

        # 実行 (Act)
        entries = [(path, frontmatter(path), path.read_text(encoding="utf-8")) for path in paths]

        # 検証 (Assert)
        self.assertEqual(len(entries), 10)
        for path, metadata, content in entries:
            with self.subTest(entry=path.relative_to(ROOT)):
                self.assertEqual(metadata["name"], path.parent.name)
                self.assertTrue(metadata["description"])
                self.assertNotIn("{{", content)

    def test_claude_execution_settings_are_preserved(self):
        """既存Claudeのfork・モデル・待機・Write/Edit制限を維持する。"""
        # 準備 (Arrange)
        paths = {name: ROOT / f".claude/skills/{name}/SKILL.md" for name in NAMES[1:]}

        # 実行 (Act)
        entries = {name: frontmatter(path) for name, path in paths.items()}

        # 検証 (Assert)
        for name, metadata in entries.items():
            self.assertEqual(metadata["disallowed-tools"], "Write, Edit")
            self.assertNotIn("allowed-tools", metadata)
            if name != "review":
                self.assertEqual(metadata["context"], "fork")
                self.assertEqual(metadata["model"], "sonnet")
                self.assertEqual(metadata["background"], "false")

    def test_codex_does_not_inherit_claude_frontmatter(self):
        """Codexのモデルや権限をClaudeのmetadataで設定したように見せない。"""
        # 準備 (Arrange)
        paths = {name: ROOT / f".agents/skills/config-{name}/SKILL.md" for name in NAMES}

        # 実行 (Act)
        entries = [(name, frontmatter(path), resolved_links(path)) for name, path in paths.items()]

        # 検証 (Assert)
        for name, metadata, links in entries:
            self.assertEqual(set(metadata), {"name", "description"})
            if name != "clarify":
                self.assertIn(ROOT / ".agents/review-runtime.md", links)

    def test_each_host_reaches_the_same_policy_and_aspects(self):
        """両hostの入口が同一実体の共通方針・観点を参照する。"""
        # 準備 (Arrange)
        paths = [(host, prefix, name, ROOT / f"{host}/skills/{prefix}{name}/SKILL.md")
                 for host, prefix in ((".claude", ""), (".agents", "config-")) for name in NAMES[1:]]

        # 実行 (Act)
        entries = [(host, prefix, name, resolved_links(path)) for host, prefix, name, path in paths]

        # 検証 (Assert)
        for host, prefix, name, links in entries:
            self.assertIn(ROOT / ".ai-config/review/policy.md", links)
            if name == "review":
                self.assertIn(ROOT / ".ai-config/review/workflow.md", links)
                for aspect in NAMES[2:]:
                    self.assertIn(ROOT / f"{host}/skills/{prefix}{aspect}/SKILL.md", links)
            else:
                self.assertIn(ROOT / ".ai-config/review/reviewer.md", links)
                self.assertIn(ROOT / f".ai-config/review/{name[7:]}.md", links)

    def test_codex_runtime_contract_is_present(self):
        """空ファイルや条件欠落を参照先の存在だけで成功としない。"""
        # 準備 (Arrange)
        path = ROOT / ".agents/review-runtime.md"
        requirements = ("ユーザー指定のモデル・推論量", "未指定なら実行セッションの設定を継承",
                        "読取専用sandbox", "on-request", "変更可能な外部ツールも無効化",
                        "条件を確認できなければ開始せず未完了", "技術的な書込拒否を実現しない")

        # 実行 (Act)
        content = path.read_text(encoding="utf-8")

        # 検証 (Assert)
        for requirement in requirements:
            self.assertIn(requirement, content)

    def test_coding_rules_include_the_approved_aaa_addition(self):
        """従来規約にAAA方針を追加した承認済み本文を保存する。"""
        # 準備 (Arrange)
        content = (ROOT / ".ai-config/rules/coding.md").read_text(encoding="utf-8")
        expected = "fd311361659b8beb28f397d16862acdd1f1934fdbd05fdce8352d17e3a776e31"

        # 実行 (Act)
        normalized = "\n".join(line.rstrip() for line in content.splitlines() if line.strip())
        actual = hashlib.sha256(normalized.encode()).hexdigest()

        # 検証 (Assert)
        self.assertEqual(actual, expected)


def copy_distribution(destination: Path) -> None:
    for name in DISTRIBUTION:
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, destination / name, symlinks=True,
                            ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(source, destination / name, follow_symlinks=False)


def distribution_markdown(root: Path) -> list:
    paths = [root / "AGENTS.md", root / "CLAUDE.md", root / ".agents/review-runtime.md"]
    paths.extend((root / ".ai-config").rglob("*.md"))
    paths.extend(root / f"{host}/skills/{prefix}{name}/SKILL.md"
                 for host, prefix in ((".claude", ""), (".agents", "config-")) for name in NAMES)
    return paths


def resolved_links(path: Path) -> set:
    return {(path.parent / link).resolve() for link in local_links(path)}


def local_links(path: Path) -> list:
    links = [link for link in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", path.read_text(encoding="utf-8"))
             if "://" not in link]
    # 統合先AGENTSの独自リンクは配布物の検証対象に含めない。
    if path.name in ("AGENTS.md", "CLAUDE.md"):
        return [link for link in links if link.startswith(".ai-config/")]
    return links


def frontmatter(path: Path) -> dict:
    header = path.read_text(encoding="utf-8").split("---", 2)[1]
    return dict(line.split(": ", 1) for line in header.strip().splitlines())


if __name__ == "__main__":
    unittest.main()
