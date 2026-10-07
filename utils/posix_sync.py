"""
Pure diff of coact users against an LDAP posix snapshot. No database access, so it is unit-testable;
the mutation in main.py loads the users, calls compute_posix_sync and applies the returned updates.
"""

from typing import Iterable, List, Optional, Tuple
import logging

from models import PosixSyncResult

LOG = logging.getLogger(__name__)


def compute_posix_sync(current: dict, entries: Iterable, dry_run: bool, force: bool,
                       min_coverage: float, max_churn: float, include_primary: bool = True,
                       group_count: Optional[int] = None, last_group_count: Optional[int] = None,
                       max_group_drop: float = 1.0) -> Tuple[PosixSyncResult, List[tuple]]:
    """
    current: coact users keyed by username -> {uidnumber, gidnumber, secondarygids, isbot}
    entries: snapshot objects with .username .secondarygids, plus .uidnumber .gidnumber when include_primary
             (UserPosixInput / UserSecondaryGidsInput)

    Returns (result, updates) where updates is [(username, gidnumber, secondarygids)]. With include_primary=False
    only secondarygids are compared and each update carries the user's current gidnumber unchanged.

    group_count / last_group_count: posixGroups read this run vs the last successful run; a drop of more than
    max_group_drop means the group read was likely incomplete (which would strip gids from members).

    The diff is driven from coact usernames: the sync never creates users, and coact users missing from
    LDAP are reported (unknownUsers) but never nulled. uidnumber differences are reported, never written.

    The snapshot is expected to cover the coact users only (see posixSyncUsernames), so an incomplete LDAP
    read shows up as low coverage: the fraction of non-bot coact users found in the snapshot.
    """
    snapshot = { e.username: e for e in entries }
    total = len(snapshot)

    matched = 0
    eligible = 0
    eligible_matched = 0
    updates = []
    unknown = []
    uid_mismatches = []
    for username, doc in current.items():
        e = snapshot.get(username)
        if not doc.get("isbot"):
            eligible += 1
            if e is not None:
                eligible_matched += 1
        if e is None:
            if not doc.get("isbot"):
                unknown.append(username)
            continue
        matched += 1
        want_secondary = sorted({ int(g) for g in (e.secondarygids or []) })
        if include_primary:
            want_gid = int(e.gidnumber) if e.gidnumber is not None else None
            if e.uidnumber is not None and doc.get("uidnumber") is not None and int(e.uidnumber) != int(doc["uidnumber"]):
                uid_mismatches.append(f"{username}: coact={doc['uidnumber']} ldap={e.uidnumber}")
        else:
            want_gid = doc.get("gidnumber")
        if doc.get("gidnumber") != want_gid or sorted(doc.get("secondarygids") or []) != want_secondary:
            updates.append((username, want_gid, want_secondary))

    aborted = False
    reason = None
    coverage = eligible_matched / eligible if eligible else 1.0
    if coverage < min_coverage:
        aborted = True
        reason = (f"only {eligible_matched}/{eligible} coact users found in the snapshot ({coverage:.0%}), "
                  f"below minimum coverage {min_coverage:.0%}; LDAP read likely incomplete")
    elif group_count is not None and last_group_count and group_count < last_group_count * (1 - max_group_drop):
        aborted = True
        reason = (f"{group_count} posixGroups read vs {last_group_count} last successful run, a drop above "
                  f"{max_group_drop:.0%}; LDAP group read likely incomplete")
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
