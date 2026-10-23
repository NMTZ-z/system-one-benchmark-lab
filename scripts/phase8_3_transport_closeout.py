#!/usr/bin/env python3
"""Physical Provider ledger closeout for a NEW bounded run after frozen H1.

H1 is immutable historical evidence: source SHA and the EXACT first ledger
bytes are checked against the already-published SHA. H1's unresolved slot is
NOT reclassified or erased. A later scoped run may independently establish
its own terminal provenance, but global Phase 8.3A remains BLOCKED.
No Provider I/O in this module. Callers must stop proxy on any mismatch.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

H1_ORIGINAL_SHA256 = "bded2cecb79bcf22a6cdb39a4186b99fb68e881651d18142de370e3b120133de"
H2_ORIGINAL_SHA256 = "dbd2be172785d94ded75e264be1534f4f9396a33edf4bb4f555492604b6a7b3f"
H3_ORIGINAL_SHA256 = "5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb"
H1 = "h1_read_off"
H2 = "h2_read_shadow"
H3 = "h3_runtime_down"
H4 = "h4_missing_read"
H4B = "h4b_missing_read"
NEW_SUPPORTED_RUNS = frozenset({H2, H3, H4, H4B})
TOTAL_CAP = 24
PER_CASE_CAP = 3
KINDS = frozenset({"reserved", "attempted", "responded", "outcome_unknown", "result"})


class CloseoutBlocked(ValueError):
    pass


def _read(ledger: Path) -> tuple[list[dict], bytes]:
    if ledger.is_symlink() or not ledger.is_file():
        raise CloseoutBlocked("physical Provider ledger missing/unsafe")
    # The genuine HTTP proxy uses this same .lock with LOCK_EX around
    # each durable JSONL append. A raw read can observe half a line and
    # mistakenly terminate a live proxy while its Provider response is
    # still pending. Shared lock makes snapshots transactionally stable.
    lock=ledger.with_name(ledger.name+".lock")
    if lock.is_symlink():
        raise CloseoutBlocked("physical Provider ledger lock symlinked")
    flags=os.O_RDWR|os.O_CREAT|getattr(os,"O_NOFOLLOW",0)
    descriptor=os.open(lock,flags,0o600)
    try:
        with os.fdopen(descriptor,"r+") as handle:
            fcntl.flock(handle.fileno(),fcntl.LOCK_SH)
            try:
                raw=ledger.read_bytes()
            finally:
                fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
    except (OSError,ValueError) as exc:
        raise CloseoutBlocked("stable physical Provider ledger snapshot unavailable") from exc
    if not raw.endswith(b"\n") or len(raw) > 250_000:
        raise CloseoutBlocked("ledger has partial/oversized data")
    lines = raw.splitlines(keepends=True)
    if len(lines) < 10 or hashlib.sha256(b"".join(lines[:10])).hexdigest() != H1_ORIGINAL_SHA256:
        raise CloseoutBlocked("original H1 ledger prefix has been altered")
    # When a third real scenario is appended, also protect the *entire*
    # H1+H2 public-evidence prefix. H2 transport must never be rewritten to
    # give the subsequent run an apparently clean historical budget.
    if len(lines)>22 and hashlib.sha256(b"".join(lines[:22])).hexdigest()!=H2_ORIGINAL_SHA256:
        raise CloseoutBlocked("original H1+H2 ledger prefix has been altered")
    if len(lines)>30 and hashlib.sha256(b"".join(lines[:30])).hexdigest()!=H3_ORIGINAL_SHA256:
        raise CloseoutBlocked("original H1+H2+H3 ledger prefix has been altered")
    records = []
    for line in lines:
        row = json.loads(line)
        if not isinstance(row, dict) or set(row) - {
            "kind", "run", "slot", "http_status", "duration_ms",
        } or row.get("kind") not in KINDS:
            raise CloseoutBlocked("malformed/nonprivate Provider ledger entry")
        if row.get("run") not in ({H1} | NEW_SUPPORTED_RUNS):
            raise CloseoutBlocked("Provider ledger contains undeclared run")
        if type(row.get("slot")) is not int or row["slot"] < 1 or row["slot"] > TOTAL_CAP:
            raise CloseoutBlocked("unexpected physical slot ID")
        records.append(row)
    return records, raw


def audited_snapshot(ledger: Path, *, new_run: str = "h2_read_shadow") -> dict:
    if new_run not in NEW_SUPPORTED_RUNS:
        raise CloseoutBlocked("undeclared new Provider test run")
    rows, raw = _read(ledger)
    by = defaultdict(lambda: defaultdict(list))
    reservations = {}
    for e in rows:
        slot = e["slot"]
        if e["kind"] == "reserved":
            if slot in reservations:
                raise CloseoutBlocked("duplicate physical reservation")
            reservations[slot] = e["run"]
        elif slot not in reservations or reservations[slot] != e["run"]:
            raise CloseoutBlocked("terminal/request activity without matching reservation")
        if e["kind"] != "reserved":
            by[e["run"]][slot].append(e)
    if len(reservations) > TOTAL_CAP or sorted(reservations) != list(range(1, len(reservations)+1)):
        raise CloseoutBlocked("physical reservation count/ordering violated")
    if set(reservations.values())-({H1,H2,H3,H4,H4B}):
        raise CloseoutBlocked("undeclared Provider task observed")
    if new_run in {H3,H4}:
        h2slots={s for s,r in reservations.items() if r==H2}
        if h2slots!={4,5,6}:
            raise CloseoutBlocked("original three H2 Provider slots missing")
        h2events=Counter(x["kind"] for y in by[H2].values() for x in y)
        if h2events!={"attempted":3,"responded":3,"result":3}:
            raise CloseoutBlocked("original H2 terminals have changed")
        if any(e.get("http_status")!=200 for e in rows
               if e.get("run")==H2 and e.get("kind")=="responded"):
            raise CloseoutBlocked("original H2 upstream provider outcomes changed")
    if new_run in {H4,H4B}:
        # H4/H4B cannot take H3's completed slots or retroactively
        # mark the Laya-runtime-down control as a local-MLX run.
        if {s for s,r in reservations.items() if r==H3}!={7,8}:
            raise CloseoutBlocked("original two H3 physical slots missing")
        h3events=Counter(x["kind"] for y in by[H3].values() for x in y)
        if h3events!={"attempted":2,"responded":2,"result":2}:
            raise CloseoutBlocked("original H3 Provider terminal history changed")
        if any(e.get("http_status")!=200 for e in rows
               if e.get("run")==H3 and e.get("kind")=="responded"):
            raise CloseoutBlocked("original H3 Provider outcomes changed")
    if set(s for s,r in reservations.items() if r == H1) != {1,2,3}:
        raise CloseoutBlocked("historical physical reservations changed")
    previous = by[H1]
    if (set(previous) != {1,2,3}
        or Counter(x["kind"] for es in previous.values() for x in es)
        != {"attempted":3,"responded":2,"result":2}):
        raise CloseoutBlocked("original H1 history changed")
    if new_run==H4B and any(run==H4 for run in reservations.values()):
        raise CloseoutBlocked("original H4 startup incident must have zero physical requests")
    slots = {s:v for s,v in by[new_run].items()}
    first_new_slot = 9 if new_run in {H4,H4B} else 7 if new_run == H3 else 4
    if len(slots)>PER_CASE_CAP or any(s < first_new_slot for s in slots):
        raise CloseoutBlocked("new Provider attempt outside authorized physical slots")
    stats = Counter()
    invalid = []
    for slot, entries in slots.items():
        kinds = Counter(x["kind"] for x in entries)
        if (kinds["attempted"]>1 or kinds["responded"]+kinds["outcome_unknown"]>1
            or kinds["result"]>1 or kinds["reserved"]>0
            or set(kinds)-{"attempted","responded","outcome_unknown","result"}):
            invalid.append("duplicate_or_unknown_event")
        if kinds["responded"] and not all(
            isinstance(x.get("http_status"),int) and 100<=x["http_status"]<=599
            for x in entries if x["kind"]=="responded"
        ):
            invalid.append("malformed_provider_response")
        for key in ("attempted","responded","outcome_unknown","result"):
            stats[key]+=kinds[key]
    if invalid:
        raise CloseoutBlocked("invalid new Provider lifecycle event")
    complete = bool(slots) and (
        len(slots)==stats["attempted"]
        ==stats["responded"]+stats["outcome_unknown"]
        ==stats["result"]
    )
    status = "SCOPE_COMPLETE" if complete else "SCOPE_INCOMPLETE"
    return {
        "run_id": new_run,
        "reserved_global": len(reservations),
        "reserved_h1": 3,
        "reserved_h2": 3 if new_run in {H3,H4,H4B} else len(
            [s for s,r in reservations.items() if r==H2]),
        "reserved_h3": (
            2 if new_run in {H4,H4B} else
            len([s for s,r in reservations.items() if r==H3])
        ),
        "reserved_original_h4": (
            len([s for s,r in reservations.items() if r==H4])
            if new_run==H4B else 0
        ),
        "reserved_new": len(slots),
        "attempted_new": stats["attempted"],
        "responded_new": stats["responded"],
        "unknown_new": stats["outcome_unknown"],
        "finalized_new": stats["result"],
        "new_run_status": status,
        "historic_h1_unresolved": 1,
        "overall_phase_8_3a_integrity": "BLOCKED_HISTORICAL_UNRESOLVED",
        "global_request_limit": TOTAL_CAP,
        "per_run_limit": PER_CASE_CAP,
        "ledger_digest_sha256": hashlib.sha256(raw).hexdigest(),
        "permission_to_override_h1": False,
    }


def drain_run(ledger: Path, *, run_id: str="h2_read_shadow", maximum_seconds: float=80.0) -> dict:
    if not 0<=maximum_seconds<=85:
        raise CloseoutBlocked("bounded proxy drain timeout required")
    deadline=time.monotonic()+maximum_seconds
    while True:
        result=audited_snapshot(ledger,new_run=run_id)
        if result["new_run_status"]=="SCOPE_COMPLETE":
            return result
        if time.monotonic()>=deadline:
            return result
        time.sleep(min(.3,max(0.01,deadline-time.monotonic())))
