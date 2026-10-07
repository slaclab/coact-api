"""
Unit tests for User.gids: primary gid first, then sorted supplemental gids, from the same source as myGids.
"""
from types import SimpleNamespace

from models import User, UserGidsInfo, gid_list


class TestGidList:

    def test_primary_first_then_sorted_secondaries(self):
        assert gid_list(UserGidsInfo(primaryGid=10, secondaryGidNumbers=[30, 20])) == [10, 20, 30]

    def test_primary_not_repeated_in_secondaries(self):
        assert gid_list(UserGidsInfo(primaryGid=10, secondaryGidNumbers=[20, 10, 20])) == [10, 20]

    def test_no_primary(self):
        assert gid_list(UserGidsInfo(primaryGid=None, secondaryGidNumbers=[20])) == [20]

    def test_unknown_user(self):
        assert gid_list(None) == []


class TestUserGidsField:

    def test_uses_context_user_gids(self):
        calls = []
        def user_gids(username):
            calls.append(username)
            return UserGidsInfo(primaryGid=10, secondaryGidNumbers=[30, 20])
        info = SimpleNamespace(context=SimpleNamespace(userGids=user_gids))
        user = User(username="alice", eppns=[], shell="/bin/bash", preferredemail="a@example.org")
        assert User.gids(user, info) == [10, 20, 30]
        assert calls == ["alice"]
