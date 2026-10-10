import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/workflow-kit"


class PackagingTests(unittest.TestCase):
    def test_marketplace_points_to_matching_contained_plugin(self):
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertTrue(marketplace["owner"]["name"])
        self.assertEqual(len(marketplace["plugins"]), 1)
        entry = marketplace["plugins"][0]
        plugin = (ROOT / entry["source"]).resolve()
        self.assertTrue(plugin.is_relative_to(ROOT))
        manifest = json.loads((plugin / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(entry["name"], manifest["name"])
        self.assertEqual(manifest["version"], "0.2.0")
        self.assertFalse((plugin / "hooks").exists())
        self.assertFalse((plugin / ".mcp.json").exists())

    def test_reviewers_have_read_only_tools_without_implicit_repo_instructions(self):
        agents = PLUGIN / "agents"
        for name in ("security", "test-adequacy", "design-rules-docs"):
            data = (agents / (name + "-reviewer.md")).read_text()
            header = data.split("---", 2)[1]
            fields = dict(line.split(": ", 1) for line in header.strip().splitlines())
            self.assertEqual(fields["tools"], "Read")
            self.assertEqual(fields["omitClaudeMd"], "true")
            self.assertNotIn("permissionMode", fields)
            self.assertNotIn("hooks", fields)

    def test_workflow_skills_exist(self):
        """ワークフローの 4 つのスキルが存在する。"""
        for name in ("develop", "plan", "review", "architecture"):
            self.assertTrue((PLUGIN / "skills" / name / "SKILL.md").is_file(), name)

    def test_lead_agents_match_agent_files(self):
        """lead が列挙するエージェントが実在し、未参照のエージェントファイルがない。"""
        lead = (PLUGIN / "agents/lead.md").read_text()
        agent_list = re.search(r"Agent\(([^)]*)\)", lead).group(1)
        names = set(re.findall(r"workflow-kit:([\w-]+)", agent_list))
        self.assertTrue(names)
        files = {p.stem for p in (PLUGIN / "agents").glob("*.md")}
        self.assertEqual(files - {"lead"}, names)

    def test_markdown_relative_links_resolve(self):
        """README とプラグイン配下の Markdown の相対リンク先が存在する。"""
        documents = [ROOT / "README.md", *PLUGIN.rglob("*.md")]
        for document in documents:
            for target in re.findall(r"\]\(([^)\s]+)\)", document.read_text()):
                if re.match(r"[a-z][a-z0-9+.-]*:|#", target):
                    continue
                path = target.split("#", 1)[0]
                self.assertTrue((document.parent / path).exists(), f"{document}: {target}")


if __name__ == "__main__":
    unittest.main()
