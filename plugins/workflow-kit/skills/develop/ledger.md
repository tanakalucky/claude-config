# Ledger commands

Python 3.10+ and POSIX (macOS/Linux/WSL) are required. No dependencies or inference.
Run from the target Git repo. Use the helper's absolute installed path in place
of `GATE`; shell-quote paths and opaque values. Do not eval task or repo text.
`--repo /path` is a global option. The default state is
`git rev-parse --git-common-dir` plus `/workflow-kit`, shared by linked worktrees.
Alternatively supply the same absolute `--state-dir /trusted/path` every time;
its parent must exist. Never place it in the plugin cache or tracked source.
This explicit state directory also works without Git metadata; do not initialize
Git merely to use this helper.

```sh
# Only for genuinely new state, never recovery of a previously used ledger:
python3 "GATE" setup --ack-new-ledger
python3 "GATE" list
python3 "GATE" new --key feature-opaque-001
# Save the returned change_id. Repeating the same key returns the same ID.
python3 "GATE" status --change CHANGE_ID
python3 "GATE" start --change CHANGE_ID --snapshot PACKET_SHA256
python3 "GATE" claim --change CHANGE_ID --round 1 --perspective security
# Invoke security-reviewer only after a successful claim, retaining its token.
python3 "GATE" record --change CHANGE_ID --round 1 --perspective security \
  --token CLAIM_TOKEN --result complete --p0 0 --p1 0 --p2 1 --report REPORT_SHA256
# Also claim/invoke/record test-adequacy and design-rules-docs for this same round.
python3 "GATE" check --change CHANGE_ID --snapshot PACKET_SHA256
```

## Adopting a change already reviewed outside this ledger

Before using `new`, check whether this logical change already consumed review
rounds. For a first-time migration only, reconcile that count against existing
evidence. Preserve a sanitized historical summary identifying the change, the
rounds actually consumed (including interruptions), and evidence references.
Hash it locally; do not invent reviewer results or discard unresolved findings.
If the count or history is uncertain, stop and ask the human.

```sh
# Non-Git checkout: choose one persistent, private directory outside source.
# Only if this ledger has genuinely never been initialized:
python3 "GATE" --state-dir /trusted/state/workflow-kit setup --ack-new-ledger
python3 "GATE" --state-dir /trusted/state/workflow-kit list
python3 "GATE" --state-dir /trusted/state/workflow-kit adopt \
  --key existing-change-001 --rounds-consumed 1 \
  --evidence HISTORY_SHA256 --ack-history
# Keep the returned change_id. The next start reserves round 2, not round 1.
```

`adopt` accepts 1-3 previously consumed rounds and only an unused change key.
It is atomic and refuses repeats or adoption over any existing change, even one
without rounds. The same evidence hash cannot be adopted under another key.
After an uncertain response, use `list`/`status`, never a new key.
Imported rounds have status `adopted`, an `evidence_sha256`, and no reviewer rows,
claims, finding counts, or code snapshot. They cannot be edited or retroactively
marked complete. They reserve budget without claiming approval: `check` fails;
status is `historical_unverified`, or `human_required` when all three rounds were
consumed. The next normal round still needs all three perspectives. The helper
validates the hash format, not the evidence's truth; the lead must reconcile it.
This is not a recovery/reset mechanism for a lost existing ledger.

## Results and recovery

All digests are lowercase SHA-256 (64 hex characters). Compute them locally from
sanitized artifacts, e.g. `sha256sum` or Python hashlib. A packet must identify
its base/revision, relevant dirty and untracked changes, and test evidence.
Redaction can hide relevant behavior: ask for safe synthetic evidence rather
than sending raw secrets or pretending the review is complete.

`claim` succeeds once per perspective; duplicate claims fail. Persist the agent
identifier alongside the change ID in the development handoff, without secrets.
`status` recovers claim tokens after a session interruption. Continue the original
agent if possible. If its launch/result is uncertain, do not relaunch blindly:

```sh
python3 "GATE" record --change CHANGE_ID --round 1 --perspective security \
  --token CLAIM_TOKEN --result failed
# Or close the whole interrupted round, preserving any completed perspectives:
python3 "GATE" interrupt --change CHANGE_ID --round 1
```

No reset/delete/overwrite command exists. Completed identical records are
idempotent; contradictory records fail. A started round consumes budget even
if no agent launched. SQLite transactions serialize concurrent processes, and
committed reservations survive crashes. Interrupted claims never expire.
All three complete with zero P0/P1 means passed; P2 does not block. At three
blocked/failed rounds, status says `human_required`. `check` rejects missing,
failed, in-progress, or mismatched snapshots and grants no merge/deploy authority.

State contains only opaque keys/IDs, hashes, counts, and statuses. Keep it private
and retain it across sessions. Do not check it into Git. For backup, stop writers
and copy the entire state directory using trusted tooling. Missing, partial,
corrupt, unsupported-version, or insecure state fails closed. Do not delete it
or run setup elsewhere; restore a known backup or ask the human to reconcile.
A new clone/machine needs the same history transferred before continuing a
change. This local ledger cannot detect deletion of its entire directory,
fabricated inputs, a deliberately changed key/path, or direct Agent invocations.
