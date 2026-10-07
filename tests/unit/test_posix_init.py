"""
Unit tests for userPosixInit: the pure $set builder and the GraphQL mutation contract coactd relies on.
main.py is not imported (it connects to MongoDB at import time); the mutation is exercised against a fake context.
"""
from datetime import datetime, timezone

import pytest
import strawberry

from models import UserGidsInfo
from schema import Query, Mutation
from utils.posix_init import posix_init_set, uidnumber_differs

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


class TestPosixInitSet:

    def test_sets_primary_secondaries_and_synced_at(self):
        info = UserGidsInfo(uidnumber=1, primaryGid=10, secondaryGidNumbers=[30, 20])
        assert posix_init_set("alice", info, NOW) == {"gidnumber": 10, "secondarygids": [20, 30], "ldapsyncedat": NOW}

    def test_never_writes_uidnumber(self):
        posix = posix_init_set("alice", UserGidsInfo(uidnumber=1, primaryGid=10), NOW)
        assert "uidnumber" not in posix
        assert set(posix) == {"gidnumber", "secondarygids", "ldapsyncedat"}

    def test_secondaries_are_deduped_sorted_ints(self):
        info = UserGidsInfo(primaryGid="10", secondaryGidNumbers=[30, "20", 30, 20])
        posix = posix_init_set("alice", info, NOW)
        assert posix["gidnumber"] == 10
        assert posix["secondarygids"] == [20, 30]
        assert all(type(g) is int for g in posix["secondarygids"])

    def test_no_secondaries_is_empty_list(self):
        assert posix_init_set("alice", UserGidsInfo(primaryGid=10), NOW)["secondarygids"] == []
        assert posix_init_set("alice", UserGidsInfo(primaryGid=10, secondaryGidNumbers=None), NOW)["secondarygids"] == []

    def test_primary_gid_zero_is_kept(self):
        assert posix_init_set("alice", UserGidsInfo(primaryGid=0), NOW)["gidnumber"] == 0

    def test_user_missing_from_user_lookup_raises(self):
        with pytest.raises(Exception, match="not found in user-lookup; posix data not written"):
            posix_init_set("alice", None, NOW)

    def test_missing_primary_gid_raises(self):
        # a partial lookup (secondaries but no primary) must not produce a partial write
        with pytest.raises(Exception, match="no primary gid for user alice; posix data not written"):
            posix_init_set("alice", UserGidsInfo(uidnumber=1, secondaryGidNumbers=[20]), NOW)


class TestUidnumberDiffers:

    def test_equal(self):
        assert uidnumber_differs(1, 1) is False
        assert uidnumber_differs(1, "1") is False

    def test_different(self):
        assert uidnumber_differs(1, 2) is True

    def test_either_side_missing_is_not_a_mismatch(self):
        assert uidnumber_differs(None, 2) is False
        assert uidnumber_differs(1, None) is False
        assert uidnumber_differs(None, None) is False


class FakeContext:
    """ Just enough of CustomContext for IsAuthenticated / IsAdmin and the userPosixInit resolver. """

    def __init__(self, is_admin, result=None, error=None):
        self.username = "caller"
        self.is_admin = is_admin
        self.result = result
        self.error = error
        self.calls = []

    def authn(self, **kwargs):
        return self.username

    def userPosixInit(self, username):
        self.calls.append(username)
        if self.error:
            raise self.error
        return self.result


MUTATION = """
mutation userPosixInit($username: String!) {
    userPosixInit(username: $username) { uidnumber primaryGid secondaryGidNumbers syncedAt }
}
"""


class TestUserPosixInitMutation:

    @pytest.fixture(scope="class")
    def schema(self):
        return strawberry.Schema(query=Query, mutation=Mutation)

    def test_signature(self, schema):
        sdl = schema.as_str()
        assert "userPosixInit(username: String!): UserGidsInfo!" in sdl

    def test_admin_gets_context_result(self, schema):
        ctx = FakeContext(is_admin=True, result=UserGidsInfo(uidnumber=1, primaryGid=10, secondaryGidNumbers=[20, 30], syncedAt=NOW))
        res = schema.execute_sync(MUTATION, variable_values={"username": "alice"}, context_value=ctx)
        assert res.errors is None
        assert ctx.calls == ["alice"]
        out = res.data["userPosixInit"]
        assert out["uidnumber"] == 1 and out["primaryGid"] == 10 and out["secondaryGidNumbers"] == [20, 30]
        assert out["syncedAt"] is not None

    def test_non_admin_is_rejected_without_calling_context(self, schema):
        ctx = FakeContext(is_admin=False)
        res = schema.execute_sync(MUTATION, variable_values={"username": "alice"}, context_value=ctx)
        assert res.errors and "not an admin" in res.errors[0].message
        assert ctx.calls == []

    def test_context_error_is_surfaced(self, schema):
        ctx = FakeContext(is_admin=True, error=Exception("user-lookup returned no primary gid for user alice; posix data not written"))
        res = schema.execute_sync(MUTATION, variable_values={"username": "alice"}, context_value=ctx)
        assert res.errors and "no primary gid" in res.errors[0].message
        assert res.data is None
