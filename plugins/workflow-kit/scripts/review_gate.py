#!/usr/bin/env python3
"""Local, non-inference review reservation ledger. Python 3.10+, POSIX."""

import argparse
import contextlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import sys
import uuid

PERSPECTIVES = ("security", "test-adequacy", "design-rules-docs")
LIMIT = 3
SCHEMA = "1"


class GateError(Exception):
    pass


def digest(value):
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise GateError("Expected a lowercase SHA-256 digest")
    return value


def directory(args):
    if args.state_dir:
        path = Path(args.state_dir).absolute()
    else:
        result = subprocess.run(
            ["git", "-C", args.repo, "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode:
            raise GateError("Git repository required, or supply a persistent --state-dir")
        path = Path(result.stdout.strip()) / "workflow-kit"
    # Reject symlinks rather than resolving attacker-controlled state paths.
    for part in (path, *path.parents):
        if part.is_symlink():
            raise GateError("State path must not contain symlinks")
    return path


def secure_file(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise GateError("Ledger missing; do not reset it. Restore its backup or ask a human")
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise GateError("Ledger files must be regular, owner-only files owned by this user")


def setup(path, acknowledge):
    if not acknowledge:
        raise GateError("First setup requires --ack-new-ledger; never use setup to reset a change")
    if path.exists():
        # An existing empty/partial directory may be a lost ledger. Fail closed.
        with connect(path):
            return {"initialized": False, "state_dir": str(path)}
    path.mkdir(mode=0o700)  # Parents must already exist; no implicit repo/path creation.
    try:
        for name in ("initialized", "ledger.sqlite3"):
            fd = os.open(path / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        db = sqlite3.connect(path / "ledger.sqlite3")
        try:
            db.executescript("""
                PRAGMA synchronous=FULL;
                CREATE TABLE meta (version TEXT NOT NULL);
                INSERT INTO meta VALUES ('1');
                CREATE TABLE changes (
                    id TEXT PRIMARY KEY, change_key TEXT UNIQUE NOT NULL
                );
                CREATE TABLE rounds (
                    change_id TEXT NOT NULL REFERENCES changes(id),
                    number INTEGER NOT NULL CHECK(number BETWEEN 1 AND 3),
                    snapshot TEXT NOT NULL, status TEXT NOT NULL,
                    PRIMARY KEY(change_id, number)
                );
                CREATE TABLE reviews (
                    change_id TEXT NOT NULL, round INTEGER NOT NULL,
                    perspective TEXT NOT NULL, status TEXT NOT NULL,
                    token TEXT UNIQUE, p0 INTEGER, p1 INTEGER, p2 INTEGER, report TEXT,
                    PRIMARY KEY(change_id, round, perspective),
                    FOREIGN KEY(change_id, round) REFERENCES rounds(change_id, number)
                );
            """)
        finally:
            db.close()
    except Exception:
        # Preserve partial initialization for explicit human recovery, not retry/reset.
        raise GateError("Initialization incomplete; preserve the state directory and ask a human")
    return {"initialized": True, "state_dir": str(path)}


@contextlib.contextmanager
def connect(path):
    if not path.is_dir() or path.is_symlink():
        raise GateError("Ledger not initialized; first-time setup requires --ack-new-ledger")
    info = path.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise GateError("State directory must be owner-only and owned by this user")
    secure_file(path / "initialized")
    secure_file(path / "ledger.sqlite3")
    db = sqlite3.connect((path / "ledger.sqlite3").as_uri() + "?mode=rw", uri=True, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")  # Serialize transitions across independent processes.
        versions = db.execute("SELECT version FROM meta").fetchall()
        if len(versions) != 1 or versions[0][0] != SCHEMA:
            raise GateError("Unsupported ledger schema; preserve state and ask a human")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def require_change(db, change):
    if not db.execute("SELECT 1 FROM changes WHERE id=?", (change,)).fetchone():
        raise GateError("Unknown change ID; use list, never silently create a replacement")


def status(db, change):
    require_change(db, change)
    rounds = []
    for row in db.execute("SELECT * FROM rounds WHERE change_id=? ORDER BY number", (change,)):
        item = dict(row)
        item["reviews"] = [dict(r) for r in db.execute(
            "SELECT perspective,status,token,p0,p1,p2,report FROM reviews "
            "WHERE change_id=? AND round=? ORDER BY perspective", (change, row["number"])
        )]
        rounds.append(item)
    latest = rounds[-1] if rounds else None
    decision = "not_reviewed"
    if latest:
        if latest["status"] == "active":
            decision = "in_progress"
        elif latest["status"] == "passed":
            decision = "passed"
        else:
            decision = "human_required" if len(rounds) >= LIMIT else "changes_or_retry_needed"
    return {"change_id": change, "rounds_used": len(rounds), "limit": LIMIT,
            "decision": decision, "rounds": rounds}


def finalize(db, change, number):
    rows = db.execute("SELECT * FROM reviews WHERE change_id=? AND round=?", (change, number)).fetchall()
    if all(r["status"] in ("complete", "failed") for r in rows):
        passed = all(r["status"] == "complete" and r["p0"] == r["p1"] == 0 for r in rows)
        db.execute("UPDATE rounds SET status=? WHERE change_id=? AND number=?",
                   ("passed" if passed else "blocked", change, number))


def execute(db, args):
    if args.command == "new":
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", args.key):
            raise GateError("Use an opaque stable key (1-96 ASCII letters, digits, ., _, -); no personal data")
        row = db.execute("SELECT id FROM changes WHERE change_key=?", (args.key,)).fetchone()
        change = row[0] if row else str(uuid.uuid4())
        if not row:
            db.execute("INSERT INTO changes VALUES (?,?)", (change, args.key))
        return {"change_id": change, "created": not bool(row)}
    if args.command == "list":
        return [dict(r) for r in db.execute("SELECT id,change_key FROM changes ORDER BY rowid")]
    require_change(db, args.change)
    if args.command == "status":
        return status(db, args.change)
    if args.command == "check":
        snapshot = digest(args.snapshot)
        current = status(db, args.change)
        if (current["decision"] != "passed" or
                current["rounds"][-1]["snapshot"] != snapshot):
            raise GateError("This snapshot has not passed all three reviews; no completion claim")
        return {"review_passed": True, "change_id": args.change, "snapshot": snapshot,
                "merge_or_deploy_authorized": False}
    if args.command == "start":
        snapshot = digest(args.snapshot)
        old = db.execute("SELECT * FROM rounds WHERE change_id=? ORDER BY number DESC LIMIT 1",
                         (args.change,)).fetchone()
        if old and old["status"] == "active":
            if old["snapshot"] != snapshot:
                raise GateError("An interrupted/active round owns another snapshot; resume or interrupt it")
            return {"round": old["number"], "created": False, "status": status(db, args.change)}
        number = old["number"] + 1 if old else 1
        if number > LIMIT:
            raise GateError("Three rounds consumed. Stop reviews and report unresolved work to a human")
        if old and old["status"] == "passed" and old["snapshot"] == snapshot:
            raise GateError("This snapshot already passed; do not run redundant reviews")
        db.execute("INSERT INTO rounds VALUES (?,?,?, 'active')", (args.change, number, snapshot))
        db.executemany("INSERT INTO reviews(change_id,round,perspective,status) VALUES (?,?,?, 'pending')",
                       [(args.change, number, p) for p in PERSPECTIVES])
        return {"round": number, "created": True, "status": status(db, args.change)}
    row = db.execute("SELECT * FROM rounds WHERE change_id=? AND number=?",
                     (args.change, args.round)).fetchone()
    if not row:
        raise GateError("Unknown review round")
    if args.command == "interrupt":
        if row["status"] != "active":
            raise GateError("Round already closed")
        db.execute("UPDATE reviews SET status='failed' WHERE change_id=? AND round=? "
                   "AND status IN ('pending','running')", (args.change, args.round))
        finalize(db, args.change, args.round)
        return status(db, args.change)
    review = db.execute("SELECT * FROM reviews WHERE change_id=? AND round=? AND perspective=?",
                        (args.change, args.round, args.perspective)).fetchone()
    if args.command == "claim":
        if row["status"] != "active" or review["status"] != "pending":
            raise GateError("Perspective already claimed or closed; resume the original agent, do not relaunch")
        token = str(uuid.uuid4())
        db.execute("UPDATE reviews SET status='running',token=? "
                   "WHERE change_id=? AND round=? AND perspective=?",
                   (token, args.change, args.round, args.perspective))
        return {"token": token, "change_id": args.change, "round": args.round,
                "perspective": args.perspective, "snapshot": row["snapshot"]}
    if review["token"] != args.token:
        raise GateError("Claim token mismatch")
    counts = (args.p0, args.p1, args.p2)
    if args.result == "complete":
        if any(n is None or n < 0 for n in counts) or not args.report:
            raise GateError("Complete results require nonnegative p0/p1/p2 counts and --report SHA-256")
        report = digest(args.report)
    else:
        if any(n is not None for n in counts) or args.report:
            raise GateError("Failed results cannot claim findings or a complete report")
        report = None
    values = (args.result, *counts, report)
    existing = tuple(review[k] for k in ("status", "p0", "p1", "p2", "report"))
    if review["status"] in ("complete", "failed"):
        if existing == values:
            return status(db, args.change)
        raise GateError("Recorded results are immutable; no silent overwrite")
    if row["status"] != "active" or review["status"] != "running":
        raise GateError("Claim the perspective before recording")
    db.execute("UPDATE reviews SET status=?,p0=?,p1=?,p2=?,report=? "
               "WHERE change_id=? AND round=? AND perspective=?",
               (*values, args.change, args.round, args.perspective))
    finalize(db, args.change, args.round)
    return status(db, args.change)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", default=".", help="Git worktree; default state is in its shared Git directory")
    p.add_argument("--state-dir", help="Explicit persistent owner-only directory; never change to reset a budget")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("setup").add_argument("--ack-new-ledger", action="store_true")
    sub.add_parser("new").add_argument("--key", required=True)
    sub.add_parser("list")
    for command in ("status", "check", "start", "claim", "record", "interrupt"):
        cmd = sub.add_parser(command)
        cmd.add_argument("--change", required=True)
        if command in ("start", "check"):
            cmd.add_argument("--snapshot", required=True)
        if command in ("claim", "record", "interrupt"):
            cmd.add_argument("--round", type=int, required=True)
        if command in ("claim", "record"):
            cmd.add_argument("--perspective", choices=PERSPECTIVES, required=True)
        if command == "record":
            cmd.add_argument("--token", required=True)
            cmd.add_argument("--result", choices=("complete", "failed"), required=True)
            for count in ("p0", "p1", "p2"):
                cmd.add_argument("--" + count, type=int)
            cmd.add_argument("--report", help="SHA-256 of the sanitized reviewer result; no report text")
    return p


def main():
    args = parser().parse_args()
    os.umask(0o077)
    try:
        path = directory(args)
        if args.command == "setup":
            result = setup(path, args.ack_new_ledger)
        else:
            with connect(path) as db:
                result = execute(db, args)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (GateError, sqlite3.Error, OSError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
