"""
Pure helpers for userPosixInit: turn a user-lookup UserGidsInfo into the posix fields written to the users
collection. No database or network access, so it is unit-testable; main.py does the lookup and the write.
"""

from datetime import datetime
from typing import Optional

from models import UserGidsInfo


def posix_init_set(username: str, looked_up: Optional[UserGidsInfo], now: datetime) -> dict:
    """
    The $set document for initialising a user's posix data from a user-lookup result: gidnumber,
    secondarygids (deduped, sorted ints) and ldapsyncedat. uidnumber is deliberately never included;
    it is owned by userUpsert.

    Raises (so nothing is written) if user-lookup has no entry for the user or no primary gid.
    """
    if looked_up is None:
        raise Exception(f"user {username} not found in user-lookup; posix data not written")
    if looked_up.primaryGid is None:
        raise Exception(f"user-lookup returned no primary gid for user {username}; posix data not written")
    return {
        "gidnumber": int(looked_up.primaryGid),
        "secondarygids": sorted({ int(g) for g in (looked_up.secondaryGidNumbers or []) }),
        "ldapsyncedat": now,
    }


def uidnumber_differs(coact_uidnumber: Optional[int], looked_up_uidnumber: Optional[int]) -> bool:
    """ True only when both sides have a uidnumber and they disagree. """
    if coact_uidnumber is None or looked_up_uidnumber is None:
        return False
    return int(coact_uidnumber) != int(looked_up_uidnumber)
