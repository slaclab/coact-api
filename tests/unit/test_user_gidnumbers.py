"""
Unit tests for the User.gidNumbers / User.accessGroupObjs resolvers.

These derive a user's POSIX groups from the `posixgroup` feature options nested in
every repo the user belongs to (as a user, leader, or principal). gidNumbers is the
deduplicated, sorted projection of those gids and must stay consistent with the gids
exposed under Repo.features by construction (same source of truth).
"""
import json
from unittest.mock import Mock

from models import User, AccessGroup


def _posixgroup(state, *gid_name_pairs):
    """Build a posixgroup feature dict with JSON-serialized options like production."""
    return {
        "state": state,
        "options": [json.dumps({"name": name, "gidNumber": gid}) for gid, name in gid_name_pairs],
    }


def _mock_info(repos):
    """Mock info.context.db.collection('repos').find(...) to return the given repos."""
    mock_info = Mock()
    mock_collection = Mock()
    mock_collection.find.return_value = iter(repos)
    mock_info.context.db.collection.return_value = mock_collection
    return mock_info


def _repos_for_alice():
    return [
        # member via `users`
        {"_id": "r1", "name": "repoA", "users": ["alice", "bob"], "leaders": [], "principal": "carol",
         "features": {"posixgroup": _posixgroup(True, (5001, "grpA"))}},
        # member via `principal`
        {"_id": "r2", "name": "repoB", "users": ["dave"], "leaders": [], "principal": "alice",
         "features": {"posixgroup": _posixgroup(True, (5002, "grpB"))}},
        # member via `leaders`, duplicate gid 5001 -> must dedupe in gidNumbers
        {"_id": "r3", "name": "repoC", "users": [], "leaders": ["alice"], "principal": "carol",
         "features": {"posixgroup": _posixgroup(True, (5001, "grpA"))}},
        # multiple options in a single posixgroup feature
        {"_id": "r4", "name": "repoD", "users": ["alice"], "leaders": [], "principal": "carol",
         "features": {"posixgroup": _posixgroup(True, (5003, "grpD1"), (5004, "grpD2"))}},
        # disabled posixgroup (state False) -> still included regardless of state
        {"_id": "r5", "name": "repoE", "users": ["alice"], "leaders": [], "principal": "carol",
         "features": {"posixgroup": _posixgroup(False, (5005, "grpE"))}},
        # repo without a posixgroup feature -> ignored
        {"_id": "r6", "name": "repoF", "users": ["alice"], "leaders": [], "principal": "carol",
         "features": {"slurm": {"state": True, "options": []}}},
        # option missing a gidNumber -> skipped
        {"_id": "r7", "name": "repoG", "users": ["alice"], "leaders": [], "principal": "carol",
         "features": {"posixgroup": {"state": True, "options": [json.dumps({"name": "noGid"})]}}},
    ]


def test_gidnumbers_dedupes_and_sorts_across_memberships():
    user = User(username="alice")
    info = _mock_info(_repos_for_alice())

    result = user.gidNumbers(info)

    # deduped (5001 appears twice), sorted, includes disabled group (5005),
    # excludes options without a gidNumber
    assert result == [5001, 5002, 5003, 5004, 5005]


def test_gidnumbers_returns_plain_int_list():
    user = User(username="alice")
    info = _mock_info(_repos_for_alice())

    result = user.gidNumbers(info)

    assert isinstance(result, list)
    assert all(isinstance(g, int) for g in result)


def test_gidnumbers_empty_when_no_posixgroups():
    user = User(username="loner")
    info = _mock_info([
        {"_id": "r1", "name": "repoX", "users": ["loner"], "leaders": [], "principal": "x",
         "features": {"slurm": {"state": True, "options": []}}},
    ])

    assert user.gidNumbers(info) == []


def test_accessgroupobjs_keeps_duplicates_and_is_consistent_with_gidnumbers():
    """accessGroupObjs is the richer source; gidNumbers must be its deduped gid projection."""
    user = User(username="alice")

    objs = user.accessGroupObjs(_mock_info(_repos_for_alice()))
    gidnums = user.gidNumbers(_mock_info(_repos_for_alice()))

    assert all(isinstance(o, AccessGroup) for o in objs)
    # accessGroupObjs does NOT dedupe: 5001 appears twice (repoA + repoC)
    obj_gids = sorted(o.gidnumber for o in objs)
    assert obj_gids == [5001, 5001, 5002, 5003, 5004, 5005]
    # gidNumbers is exactly the sorted unique set of accessGroupObjs gids
    assert gidnums == sorted(set(obj_gids))
