"""入口の互換性と、正本から配布物までの更新経路を検証する。"""

import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
# 移行前main 9cf0459。意図した方針変更時のみ、差分を確認して更新する。
LEGACY_HASHES = {
    "commands/clarify.md": "1c6020235de27da827686c1b5dcc631247f003d45be0abcefddf2e64144e4977",
    "commands/review.md": "c4a7955ef9be82b9aed3fc2d365c179ac66c27490c01d19edef368a5f47443e3",
    "skills/review-correctness/SKILL.md": "0543150d34b3a3036d9d6d048c54a64d51f349c4b508d03e9d86d6e8075081cb",
    "skills/review-tests/SKILL.md": "fea03afaaee2bfad20d977bf72752d5170cd40d4a6c30f750abc10d8bd87b45d",
    "skills/review-design/SKILL.md": "ad827917c217fffd57a6d7a24da24bbecf74143b027cc9ee64424f378cc18a99",
    "rules/coding.md": "efb88f09d5a4205a7f088ac4c6f0acbd4b644a6f295466fd83ea37c3e7b03b4b",
}
ASPECTS = ("correctness", "tests", "design")


class ConfigTests(unittest.TestCase):
    def test_legacy_entries_are_preserved(self):
        """既存の本文・frontmatter・秘密除外等を空白と生成通知以外そのまま保つ。"""
        for relative, expected in LEGACY_HASHES.items():
            with self.subTest(path=relative):
                content = (ROOT / relative).read_text(encoding="utf-8")
                normalized = "\n".join(
                    line.rstrip() for line in content.splitlines()
                    if line.strip() and not line.startswith("<!-- 自動生成:")
                )
                self.assertEqual(hashlib.sha256(normalized.encode()).hexdigest(), expected)

    def test_generated_entries_are_current(self):
        """別の作業ディレクトリからでもcommit済みの生成物と一致する。"""
        result = run_generator(ROOT, "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_drift_and_missing_entry_are_detected_without_writes(self):
        """手編集と欠落を検出し、checkでそれを勝手に修復しない。"""
        with temporary_repo() as directory:
            root = Path(directory) / "config"
            edited = root / "commands/review.md"
            missing = root / ".agents/skills/config-review-tests/SKILL.md"
            edited.write_text("手編集\n", encoding="utf-8")
            missing.unlink()
            result = run_generator(root, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("commands/review.md", result.stdout)
            self.assertIn(".agents/skills/config-review-tests/SKILL.md", result.stdout)
            self.assertEqual(edited.read_text(encoding="utf-8"), "手編集\n")
            self.assertFalse(missing.exists())

    def test_shared_edit_reaches_both_hosts_and_regeneration_is_stable(self):
        """1か所の方針変更が両方に届き、再生成しても内容が変わらない。"""
        with temporary_repo() as directory:
            root = Path(directory) / "config"
            source = root / "shared/review.md"
            marker = "追加の共通要件を確認する。"
            source.write_text(source.read_text(encoding="utf-8") + marker + "\n", encoding="utf-8")
            result = run_generator(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            for relative in ("commands/review.md", ".agents/skills/config-review/SKILL.md"):
                self.assertIn(marker, (root / relative).read_text(encoding="utf-8"))
            before = markdown_contents(root)
            self.assertEqual(run_generator(root).returncode, 0)
            self.assertEqual(markdown_contents(root), before)
            self.assertEqual(run_generator(root, "--check").returncode, 0)

    def test_all_entries_can_be_generated_from_scratch(self):
        """古い配布物に依存せず、両ツールの全入口を復元できる。"""
        names = ("clarify", "review", *(f"review-{aspect}" for aspect in ASPECTS))
        expected = [path for path in LEGACY_HASHES if path != "rules/coding.md"]
        expected.extend(f".agents/skills/config-{name}/SKILL.md" for name in names)
        with temporary_repo() as directory:
            root = Path(directory) / "config"
            for relative in expected:
                (root / relative).unlink()
            result = run_generator(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            for relative in expected:
                with self.subTest(path=relative):
                    self.assertTrue((root / relative).is_file())
                    self.assertEqual((root / relative).read_bytes(), (ROOT / relative).read_bytes())

    def test_codex_discovery_and_aspect_targets(self):
        """5入口が公式の探索位置にあり、3観点の呼出先が実在する。"""
        skills = ROOT / ".agents/skills"
        paths = sorted(skills.glob("*/SKILL.md"))
        self.assertEqual(len(paths), 5)
        for path in paths:
            content = path.read_text(encoding="utf-8")
            _, header, body = content.split("---", 2)
            metadata = dict(line.split(": ", 1) for line in header.strip().splitlines())
            self.assertEqual(set(metadata), {"name", "description"})
            self.assertEqual(metadata["name"], path.parent.name)
            self.assertTrue(metadata["description"])
            self.assertNotRegex(body, r"\{\{[a-z_]+\}\}")
            self.assertNotIn("Skill呼出", body)
        review = (skills / "config-review/SKILL.md").read_text(encoding="utf-8")
        targets = re.findall(r"^- `(config-review-[a-z]+)`$", review, re.MULTILINE)
        self.assertEqual(targets, [f"config-review-{aspect}" for aspect in ASPECTS])
        for name in targets:
            self.assertTrue((skills / name / "SKILL.md").is_file())

    def test_shared_review_rules_reach_codex(self):
        """秘密除外・固定base・全差分・不完了の扱いを共通の段落ごと維持する。"""
        skills = ROOT / ".agents/skills"
        for name in ("review", *(f"review-{aspect}" for aspect in ASPECTS)):
            source = (ROOT / f"shared/{name}.md").read_text(encoding="utf-8").split("---", 2)[2]
            target = (skills / f"config-{name}/SKILL.md").read_text(encoding="utf-8")
            for paragraph in source.strip().split("\n\n"):
                if "{{" not in paragraph:
                    self.assertIn(paragraph, target)

    def test_codex_review_requires_runtime_permissions(self):
        """Claudeの権限設定を流用した誤表示と、実行側の条件欠落を検出する。"""
        skills = ROOT / ".agents/skills"
        for name in ("review", *(f"review-{aspect}" for aspect in ASPECTS)):
            with self.subTest(skill=name):
                content = (skills / f"config-{name}/SKILL.md").read_text(encoding="utf-8")
                self.assertNotIn("`disallowed-tools: Write, Edit` で編集ツールを除外", content)
                self.assertIn("このMarkdown自体は権限を変更しない", content)
                self.assertIn("読取専用sandbox", content)
                self.assertIn("承認なし(never)", content)
                self.assertIn("変更可能な外部ツールも無効化", content)
                self.assertIn("設定できない場合はレビューを開始せず未完了", content)

    def test_agents_rule_reference_resolves(self):
        """AGENTSの参照先は空でない正本であり、規約の別コピーを持たない。"""
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        references = re.findall(r"\]\(([^)]+)\)", agents)
        self.assertEqual(references, ["rules/coding.md"])
        self.assertTrue((ROOT / references[0]).read_text(encoding="utf-8").strip())


def run_generator(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "scripts/generate.py"), *args],
        cwd=root.parent, capture_output=True, text=True,
    )


def temporary_repo() -> tempfile.TemporaryDirectory:
    directory = tempfile.TemporaryDirectory()
    shutil.copytree(ROOT, Path(directory.name) / "config", ignore=shutil.ignore_patterns(".git", "__pycache__"))
    return directory


def markdown_contents(root: Path) -> dict:
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*.md")}


if __name__ == "__main__":
    unittest.main()
