"""
Pure diff of coact users against an LDAP posix snapshot. No database access, so it is unit-testable;
the mutation in main.py loads the users, calls compute_posix_sync and applies the returned updates.
"""

from typing import Iterable, List, Tuple
import logging

from models import PosixSyncResult

LOG = logging.getLogger(__name__)


def compute_posix_sync(current: dict, entries: Iterable, dry_run: bool, force: bool,
                       min_entries: int, max_churn: float) -> Tuple[PosixSyncResult, List[tuple]]:
    """
    current: coact users keyed by username -> {uidnumber, gidnumber, secondarygids, isbot}
    entries: snapshot objects with .username .uidnumber .gidnumber .secondarygids (UserPosixInput)

    Returns (result, updates) where updates is [(username, gidnumber, secondarygids)].

    The diff is driven from coact usernames: the sync never creates users, and coact users missing from
    LDAP are reported (unknownUsers) but never nulled. uidnumber differences are reported, never written.
    """
    snapshot = { e.username: e for e in entries }
    total = len(snapshot)

    matched = 0
    updates = []
    unknown = []
    uid_mismatches = []
    for username, doc in current.items():
        e = snapshot.get(username)
        if e is None:
            if not doc.get("isbot"):
                unknown.append(username)
            continue
        matched += 1
        want_gid = int(e.gidnumber) if e.gidnumber is not None else None
        want_secondary = sorted({ int(g) for g in (e.secondarygids or []) })
        if e.uidnumber is not None and doc.get("uidnumber") is not None and int(e.uidnumber) != int(doc["uidnumber"]):
            uid_mismatches.append(f"{username}: coact={doc['uidnumber']} ldap={e.uidnumber}")
        if doc.get("gidnumber") != want_gid or sorted(doc.get("secondarygids") or []) != want_secondary:
            updates.append((username, want_gid, want_secondary))

    aborted = False
    reason = None
    if total < min_entries:
        aborted = True
        reason = f"snapshot has {total} entries, below minimum {min_entries}; LDAP search likely truncated or failed"
    elif matched and len(updates) / matched > max_churn:
        aborted = True
        reason = f"{len(updates)}/{matched} users would change ({len(updates)/matched:.0%}), above max churn {max_churn:.0%}"
    if aborted and force:
        LOG.warning(f"posix sync guard overridden by force: {reason}")
        aborted = False
        reason = f"guard overridden by force: {reason}"

    result = PosixSyncResult(
        dryRun=dry_run, total=total, matched=matched, changed=len(updates),
        unknownUsers=sorted(unknown), uidMismatches=sorted(uid_mismatches),
        aborted=aborted, reason=reason)
    return result, updates
