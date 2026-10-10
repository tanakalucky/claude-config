import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/workflow-kit/scripts/review_gate.py"
SPEC = importlib.util.spec_from_file_location("review_gate", SCRIPT)
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)
HASH = "a" * 64
OTHER = "b" * 64


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state"
        self.run_gate("setup", "--ack-new-ledger")
        self.change = self.run_gate("new", "--key", "change-001")["change_id"]

    def tearDown(self):
        self.tmp.cleanup()

    def run_gate(self, *args, ok=True):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--state-dir", str(self.state), *map(str, args)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0 if ok else 2, result.stdout + result.stderr)
        return json.loads(result.stdout if ok else result.stderr)

    def start(self, snapshot=HASH):
        return self.run_gate("start", "--change", self.change, "--snapshot", snapshot)

    def claim(self, number, perspective):
        return self.run_gate("claim", "--change", self.change, "--round", number,
                             "--perspective", perspective)["token"]

    def record(self, number, perspective, token, p1=0, p2=0, ok=True):
        return self.run_gate("record", "--change", self.change, "--round", number,
                             "--perspective", perspective, "--token", token,
                             "--result", "complete", "--p0", 0, "--p1", p1,
                             "--p2", p2, "--report", HASH, ok=ok)

    def complete_round(self, number, p1=0, p2=0):
        for perspective in GATE.PERSPECTIVES:
            outcome = self.record(number, perspective, self.claim(number, perspective), p1, p2)
        return outcome

    def test_new_key_is_idempotent_and_id_is_not_a_pr_number(self):
        same = self.run_gate("new", "--key", "change-001")
        self.assertFalse(same["created"])
        self.assertEqual(same["change_id"], self.change)
        self.assertEqual(len(self.change), 36)
        self.assertEqual(len(self.run_gate("list")), 1)

    def test_reject_bad_key_and_unknown_change(self):
        self.run_gate("new", "--key", "../../secret", ok=False)
        self.run_gate("status", "--change", "unknown", ok=False)

    def test_three_perspectives_are_one_round_p2_is_optional(self):
        self.start()
        outcome = self.complete_round(1, p2=2)
        self.assertEqual(outcome["rounds_used"], 1)
        self.assertEqual(outcome["decision"], "passed")
        self.assertEqual(len(outcome["rounds"][0]["reviews"]), 3)
        check = self.run_gate("check", "--change", self.change, "--snapshot", HASH)
        self.assertTrue(check["review_passed"])
        self.assertFalse(check["merge_or_deploy_authorized"])

    def test_missing_incomplete_or_changed_snapshot_cannot_pass(self):
        self.run_gate("check", "--change", self.change, "--snapshot", HASH, ok=False)
        self.start()
        self.record(1, "security", self.claim(1, "security"))
        self.run_gate("check", "--change", self.change, "--snapshot", HASH, ok=False)
        for name in ("test-adequacy", "design-rules-docs"):
            self.record(1, name, self.claim(1, name))
        self.run_gate("check", "--change", self.change, "--snapshot", OTHER, ok=False)
        self.assertEqual(self.start(OTHER)["round"], 2)

    def test_maximum_three_rounds_and_no_reset(self):
        for number in range(1, 4):
            self.assertEqual(self.start()["round"], number)
            result = self.complete_round(number, p1=1)
        self.assertEqual(result["decision"], "human_required")
        self.run_gate("start", "--change", self.change, "--snapshot", OTHER, ok=False)
        self.assertFalse(self.run_gate("setup", "--ack-new-ledger")["initialized"])
        self.assertEqual(self.run_gate("new", "--key", "change-001")["change_id"], self.change)
        self.assertEqual(self.run_gate("status", "--change", self.change)["rounds_used"], 3)

    def test_interrupted_round_preserves_claim_and_budget(self):
        self.start()
        token = self.claim(1, "security")
        resumed = self.start()
        self.assertFalse(resumed["created"])
        self.assertEqual(resumed["round"], 1)
        self.assertEqual(next(r for r in resumed["status"]["rounds"][0]["reviews"]
                              if r["perspective"] == "security")["token"], token)
        self.run_gate("claim", "--change", self.change, "--round", 1,
                      "--perspective", "security", ok=False)
        self.run_gate("start", "--change", self.change, "--snapshot", OTHER, ok=False)
        self.record(1, "security", token)
        result = self.run_gate("interrupt", "--change", self.change, "--round", 1)
        self.assertEqual(sorted(r["status"] for r in result["rounds"][0]["reviews"]),
                         ["complete", "failed", "failed"])
        self.assertEqual(self.start(OTHER)["round"], 2)

    def test_three_interruptions_exhaust_budget(self):
        for n in range(1, 4):
            self.start()
            result = self.run_gate("interrupt", "--change", self.change, "--round", n)
        self.assertEqual(result["decision"], "human_required")
        self.run_gate("start", "--change", self.change, "--snapshot", HASH, ok=False)

    def test_failed_review_does_not_pass(self):
        self.start()
        token = self.claim(1, "security")
        self.run_gate("record", "--change", self.change, "--round", 1,
                      "--perspective", "security", "--token", token, "--result", "failed")
        for name in ("test-adequacy", "design-rules-docs"):
            result = self.record(1, name, self.claim(1, name))
        self.assertEqual(result["decision"], "changes_or_retry_needed")

    def test_record_is_idempotent_but_not_overwritable(self):
        self.start()
        token = self.claim(1, "security")
        self.record(1, "security", token, p1=1)
        self.record(1, "security", token, p1=1)
        self.record(1, "security", token, p1=0, ok=False)
        self.record(1, "security", "wrong-token", ok=False)

    def test_invalid_snapshot_counts_and_missing_evidence(self):
        self.run_gate("start", "--change", self.change, "--snapshot", "not-a-digest", ok=False)
        self.start()
        token = self.claim(1, "security")
        self.record(1, "security", token, p1=-1, ok=False)
        self.run_gate("record", "--change", self.change, "--round", 1,
                      "--perspective", "security", "--token", token, "--result", "complete", ok=False)
        self.assertEqual(self.run_gate("status", "--change", self.change)["decision"], "in_progress")

    def test_concurrent_start_reserves_only_one_round(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.start(), range(8)))
        self.assertEqual(sum(r["created"] for r in results), 1)
        self.assertEqual({r["round"] for r in results}, {1})

    def test_concurrent_claim_has_single_winner(self):
        self.start()
        command = [sys.executable, str(SCRIPT), "--state-dir", str(self.state), "claim",
                   "--change", self.change, "--round", "1", "--perspective", "security"]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: subprocess.run(command, capture_output=True), range(8)))
        self.assertEqual(sum(r.returncode == 0 for r in results), 1)
        self.assertEqual(sum(r.returncode == 2 for r in results), 7)

    def test_concurrent_result_recording_finishes_one_round(self):
        self.start()
        claims = [(p, self.claim(1, p)) for p in GATE.PERSPECTIVES]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda item: self.record(1, *item), claims))
        result = self.run_gate("status", "--change", self.change)
        self.assertEqual(result["decision"], "passed")
        self.assertEqual(result["rounds_used"], 1)

    def test_redundant_review_of_passed_snapshot_is_rejected(self):
        self.start()
        self.complete_round(1)
        self.run_gate("start", "--change", self.change, "--snapshot", HASH, ok=False)

    def test_transaction_failure_rolls_back_without_losing_committed_round(self):
        self.start()
        with self.assertRaises(RuntimeError):
            with GATE.connect(self.state) as db:
                db.execute("INSERT INTO changes VALUES ('temporary-id','temporary-key')")
                raise RuntimeError("simulated process error")
        self.assertEqual(len(self.run_gate("list")), 1)
        self.assertEqual(self.run_gate("status", "--change", self.change)["rounds_used"], 1)

    def test_hard_process_exit_rolls_back_uncommitted_state(self):
        self.start()
        code = (
            "import importlib.util,os,pathlib;"
            f"s=importlib.util.spec_from_file_location('gate',{str(SCRIPT)!r});"
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
            f"c=m.connect(pathlib.Path({str(self.state)!r}));db=c.__enter__();"
            "db.execute(\"INSERT INTO changes VALUES ('crash','crash')\");os._exit(9)"
        )
        result = subprocess.run([sys.executable, "-c", code])
        self.assertEqual(result.returncode, 9)
        self.assertEqual(len(self.run_gate("list")), 1)
        self.assertEqual(self.run_gate("status", "--change", self.change)["rounds_used"], 1)

    def test_missing_or_partial_state_never_auto_reinitializes(self):
        (self.state / "ledger.sqlite3").unlink()
        self.run_gate("list", ok=False)
        self.run_gate("setup", "--ack-new-ledger", ok=False)
        self.assertFalse((self.state / "ledger.sqlite3").exists())

    def test_corrupt_or_unsupported_state_is_not_reset(self):
        with sqlite3.connect(self.state / "ledger.sqlite3") as db:
            db.execute("UPDATE meta SET version='future'")
        self.run_gate("list", ok=False)
        self.run_gate("setup", "--ack-new-ledger", ok=False)

    def test_state_permissions_and_symlinks_are_rejected(self):
        (self.state / "ledger.sqlite3").chmod(0o644)
        self.run_gate("list", ok=False)
        (self.state / "ledger.sqlite3").chmod(0o600)
        alternate = Path(self.tmp.name) / "linked"
        alternate.symlink_to(self.state, target_is_directory=True)
        original, self.state = self.state, alternate
        self.run_gate("list", ok=False)
        self.state = original

    def test_setup_requires_explicit_ack_and_does_not_create_parents(self):
        self.state = Path(self.tmp.name) / "fresh"
        self.run_gate("setup", ok=False)
        self.assertFalse(self.state.exists())
        self.state = Path(self.tmp.name) / "missing-parent" / "fresh"
        self.run_gate("setup", "--ack-new-ledger", ok=False)

    def adopt(self, count=1, key="adopted-001", evidence=HASH, ok=True):
        return self.run_gate("adopt", "--key", key, "--rounds-consumed", count,
                             "--evidence", evidence, "--ack-history", ok=ok)

    def test_adoption_preserves_usage_without_fabricated_reviews_or_approval(self):
        result = self.adopt()
        self.change = result["change_id"]
        self.assertEqual(result["status"]["decision"], "historical_unverified")
        self.assertEqual(result["status"]["rounds_used"], 1)
        history = result["status"]["rounds"][0]
        self.assertEqual(history["status"], "adopted")
        self.assertEqual(history["evidence_sha256"], HASH)
        self.assertNotIn("snapshot", history)
        self.assertEqual(history["reviews"], [])
        self.run_gate("check", "--change", self.change, "--snapshot", HASH, ok=False)
        self.assertEqual(self.start(OTHER)["round"], 2)
        self.assertEqual(self.complete_round(2)["decision"], "passed")

    def test_adoption_keeps_three_round_cap_after_future_blocked_review(self):
        self.change = self.adopt(2)["change_id"]
        self.assertEqual(self.start()["round"], 3)
        self.assertEqual(self.complete_round(3, p1=1)["decision"], "human_required")
        self.run_gate("start", "--change", self.change, "--snapshot", OTHER, ok=False)

    def test_adopting_three_consumed_rounds_requires_human(self):
        result = self.adopt(3)
        self.change = result["change_id"]
        self.assertEqual(result["status"]["decision"], "human_required")
        self.assertEqual(result["status"]["rounds_used"], 3)
        self.run_gate("start", "--change", self.change, "--snapshot", HASH, ok=False)
        self.run_gate("check", "--change", self.change, "--snapshot", HASH, ok=False)

    def test_adoption_rejects_existing_empty_active_or_imported_history(self):
        self.adopt(key="change-001", ok=False)
        self.start()
        self.adopt(key="change-001", ok=False)
        result = self.adopt()
        self.adopt(ok=False)
        self.adopt(count=2, evidence=OTHER, ok=False)
        current = self.run_gate("status", "--change", result["change_id"])
        self.assertEqual(current["rounds_used"], 1)
        self.assertEqual(current["rounds"][0]["evidence_sha256"], HASH)

    def test_adoption_rejects_invalid_count_digest_and_unacknowledged_history(self):
        for count in (-1, 0, 4, 100):
            self.adopt(count, ok=False)
        self.adopt(evidence="not-a-sha256", ok=False)
        self.adopt(key="../bad-key", ok=False)
        self.run_gate("adopt", "--key", "adopted-001", "--rounds-consumed", 1,
                      "--evidence", HASH, ok=False)
        self.assertEqual(len(self.run_gate("list")), 1)

    def test_same_history_cannot_be_readopted_under_a_new_key(self):
        result = self.adopt()
        self.adopt(key="renamed-key", ok=False)
        self.assertEqual(len(self.run_gate("list")), 2)
        current = self.run_gate("status", "--change", result["change_id"])
        self.assertEqual(current["rounds_used"], 1)

    def test_historical_round_cannot_be_claimed_recorded_or_interrupted(self):
        self.change = self.adopt()["change_id"]
        self.run_gate("claim", "--change", self.change, "--round", 1,
                      "--perspective", "security", ok=False)
        self.record(1, "security", "made-up-token", ok=False)
        self.run_gate("interrupt", "--change", self.change, "--round", 1, ok=False)
        self.assertEqual(self.run_gate("status", "--change", self.change)["decision"],
                         "historical_unverified")

    def test_concurrent_adoption_has_one_winner_without_duplicate_history(self):
        command = [sys.executable, str(SCRIPT), "--state-dir", str(self.state), "adopt",
                   "--key", "adopted-001", "--rounds-consumed", "1", "--evidence", HASH,
                   "--ack-history"]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: subprocess.run(command, capture_output=True), range(4)))
        self.assertEqual(sum(r.returncode == 0 for r in results), 1)
        self.assertEqual(sum(r.returncode == 2 for r in results), 3)
        winner = json.loads(next(r.stdout for r in results if r.returncode == 0))
        self.assertEqual(winner["status"]["rounds_used"], 1)
        self.assertEqual(len(self.run_gate("list")), 2)

    def test_adoption_is_atomic_when_history_insert_fails(self):
        with sqlite3.connect(self.state / "ledger.sqlite3") as db:
            db.execute("CREATE TRIGGER fail_adoption BEFORE INSERT ON rounds "
                       "WHEN NEW.status='adopted' BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        self.adopt(ok=False)
        self.assertEqual(len(self.run_gate("list")), 1)

    def test_explicit_state_supports_adoption_without_git(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", "/does-not-exist", "--state-dir", str(self.state),
             "adopt", "--key", "non-git-change", "--rounds-consumed", "1",
             "--evidence", HASH, "--ack-history"],
            cwd=self.tmp.name, env={**os.environ, "PATH": ""}, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"]["rounds_used"], 1)
        self.assertFalse((Path(self.tmp.name) / ".git").exists())

    def test_linked_worktrees_use_same_default_ledger(self):
        repo = Path(self.tmp.name) / "repo"
        worktree = Path(self.tmp.name) / "linked-worktree"
        def git(*args):
            subprocess.run(["git", *map(str, args)], check=True, capture_output=True)
        git("init", repo)
        git("-C", repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
            "-c", "core.hooksPath=/dev/null", "commit", "--allow-empty", "-m", "test")
        git("-C", repo, "-c", "core.hooksPath=/dev/null", "worktree", "add", "-b", "other", worktree)
        for root in (repo, worktree):
            args = GATE.parser().parse_args(["--repo", str(root), "list"])
            if root == repo:
                first = GATE.directory(args)
            else:
                self.assertEqual(GATE.directory(args), first)


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
        self.assertEqual(manifest["version"], "0.1.2")
        self.assertFalse((plugin / "hooks").exists())
        self.assertFalse((plugin / ".mcp.json").exists())

    def test_reviewers_have_read_only_tools_without_implicit_repo_instructions(self):
        agents = ROOT / "plugins/workflow-kit/agents"
        for name in ("security", "test-adequacy", "design-rules-docs"):
            data = (agents / (name + "-reviewer.md")).read_text()
            header = data.split("---", 2)[1]
            fields = dict(line.split(": ", 1) for line in header.strip().splitlines())
            self.assertEqual(fields["tools"], "Read")
            self.assertEqual(fields["omitClaudeMd"], "true")
            self.assertNotIn("permissionMode", fields)
            self.assertNotIn("hooks", fields)


if __name__ == "__main__":
    unittest.main()
