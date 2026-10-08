"""
Unit tests for the LDAP posix sync diff logic and the models it depends on.
"""
import dataclasses
from datetime import datetime, timezone

import pytest

from models import User, UserPosixInput, UserSecondaryGidsInput, UserGidsInfo
from utils.posix_sync import compute_posix_sync


def entry(username, uidnumber=None, gidnumber=None, secondarygids=None):
    return UserPosixInput(username=username, uidnumber=uidnumber, gidnumber=gidnumber, secondarygids=secondarygids or [])


def run(current, entries, dry_run=True, force=False, min_coverage=0.0, max_churn=1.0, **kw):
    return compute_posix_sync(current, entries, dry_run=dry_run, force=force, min_coverage=min_coverage, max_churn=max_churn, **kw)


class TestComputePosixSync:

    def test_unchanged_user_produces_no_update(self):
        current = {"alice": {"uidnumber": 1, "gidnumber": 10, "secondarygids": [20, 30]}}
        result, updates = run(current, [entry("alice", 1, 10, [30, 20])])
        assert updates == []
        assert result.changed == 0 and result.matched == 1 and result.total == 1
        assert not result.aborted

    def test_changed_gid_and_secondaries_are_updated(self):
        current = {"alice": {"uidnumber": 1, "gidnumber": 10, "secondarygids": [20]}}
        result, updates = run(current, [entry("alice", 1, 11, [20, 21])])
        assert updates == [("alice", 11, [20, 21])]
        assert result.changed == 1

    def test_secondaries_are_deduped_sorted_and_int(self):
        current = {"alice": {"gidnumber": 10, "secondarygids": []}}
        _, updates = run(current, [entry("alice", gidnumber=10, secondarygids=[30, "20", 30])])
        assert updates == [("alice", 10, [20, 30])]

    def test_none_secondaries_equal_empty_list(self):
        current = {"alice": {"gidnumber": 10}}  # no secondarygids key at all
        _, updates = run(current, [entry("alice", gidnumber=10, secondarygids=None)])
        assert updates == []

    def test_user_missing_from_ldap_is_reported_not_written(self):
        current = {"alice": {"gidnumber": 10, "secondarygids": [1]}, "bob": {"gidnumber": 11}}
        result, updates = run(current, [entry("alice", gidnumber=10, secondarygids=[1])])
        assert updates == []
        assert result.unknownUsers == ["bob"]
        assert result.matched == 1

    def test_bot_users_missing_from_ldap_are_not_reported(self):
        current = {"sdf-bot": {"isbot": True}}
        result, _ = run(current, [entry("alice")])
        assert result.unknownUsers == []

    def test_ldap_entry_without_coact_user_is_ignored(self):
        current = {"alice": {"gidnumber": 10}}
        result, updates = run(current, [entry("alice", gidnumber=10), entry("stranger", gidnumber=5)])
        assert updates == []
        assert result.total == 2 and result.matched == 1

    def test_uid_mismatch_is_reported_never_written(self):
        current = {"alice": {"uidnumber": 1, "gidnumber": 10}}
        result, updates = run(current, [entry("alice", uidnumber=2, gidnumber=10)])
        assert result.uidMismatches == ["alice: coact=1 ldap=2"]
        assert updates == []
        # even when the gid changes, the update tuple never carries a uidnumber
        _, updates = run(current, [entry("alice", uidnumber=2, gidnumber=99)])
        assert updates == [("alice", 99, [])]

    def test_uid_mismatch_not_reported_when_either_side_missing(self):
        current = {"alice": {"uidnumber": None, "gidnumber": 10}}
        result, _ = run(current, [entry("alice", uidnumber=2, gidnumber=10)])
        assert result.uidMismatches == []

    def test_coverage_guard_aborts(self):
        current = {"alice": {"gidnumber": 10}, "bob": {"gidnumber": 10}}
        result, updates = run(current, [entry("alice", gidnumber=11)], min_coverage=0.95)
        assert result.aborted and "below minimum coverage" in result.reason
        assert result.changed == 1  # the diff is still reported
        result, _ = run(current, [entry("alice", gidnumber=11)], min_coverage=0.5)
        assert not result.aborted

    def test_empty_snapshot_trips_coverage_guard(self):
        result, updates = run({"alice": {"gidnumber": 10}}, [], min_coverage=0.95)
        assert result.aborted and updates == []

    def test_bots_do_not_count_toward_coverage(self):
        current = {"alice": {"gidnumber": 10}, "sdf-bot": {"isbot": True}, "user-lookup-bot": {"isbot": True}}
        result, _ = run(current, [entry("alice", gidnumber=10)], min_coverage=1.0)
        assert not result.aborted

    def test_no_eligible_users_does_not_abort(self):
        result, _ = run({"sdf-bot": {"isbot": True}}, [], min_coverage=0.95)
        assert not result.aborted

    def test_churn_guard_aborts(self):
        current = {f"u{i}": {"gidnumber": 1} for i in range(10)}
        entries = [entry(f"u{i}", gidnumber=1 if i < 5 else 2) for i in range(10)]
        result, _ = run(current, entries, max_churn=0.20)
        assert result.aborted and "max churn" in result.reason
        result, _ = run(current, entries, max_churn=0.50)
        assert not result.aborted

    def test_force_overrides_guard_but_keeps_reason(self):
        current = {"alice": {"gidnumber": 10}, "bob": {"gidnumber": 10}}
        result, updates = run(current, [entry("alice", gidnumber=11)], min_coverage=0.95, force=True)
        assert not result.aborted
        assert "guard overridden by force" in result.reason
        assert updates == [("alice", 11, [])]

    def test_dry_run_flag_is_echoed(self):
        result, _ = run({}, [], dry_run=True)
        assert result.dryRun is True
        result, _ = run({}, [], dry_run=False)
        assert result.dryRun is False

    def test_result_lists_are_sorted(self):
        current = {"zed": {"uidnumber": 1}, "amy": {"uidnumber": 1}, "bob": {"uidnumber": 5}}
        result, _ = run(current, [entry("bob", uidnumber=6)])
        assert result.unknownUsers == ["amy", "zed"]


def sec(username, secondarygids=None):
    return UserSecondaryGidsInput(username=username, secondarygids=secondarygids or [])


class TestSecondaryOnlySync:

    def test_only_secondary_changes_and_primary_is_carried_unchanged(self):
        current = {"alice": {"uidnumber": 1, "gidnumber": 10, "secondarygids": [20]}}
        result, updates = run(current, [sec("alice", [21, 20])], include_primary=False)
        assert updates == [("alice", 10, [20, 21])]
        assert result.changed == 1

    def test_unchanged_secondaries_produce_no_update(self):
        current = {"alice": {"gidnumber": 10, "secondarygids": [20, 30]}}
        _, updates = run(current, [sec("alice", [30, 20])], include_primary=False)
        assert updates == []

    def test_empty_groups_clear_secondaries(self):
        current = {"alice": {"gidnumber": 10, "secondarygids": [20]}}
        _, updates = run(current, [sec("alice", [])], include_primary=False)
        assert updates == [("alice", 10, [])]

    def test_no_uid_mismatch_reporting(self):
        current = {"alice": {"uidnumber": 1, "gidnumber": 10, "secondarygids": []}}
        result, _ = run(current, [sec("alice")], include_primary=False)
        assert result.uidMismatches == []

    def test_group_drop_guard_aborts(self):
        current = {"alice": {"gidnumber": 10, "secondarygids": [20]}}
        result, updates = run(current, [sec("alice", [])], include_primary=False,
                              group_count=800, last_group_count=1000, max_group_drop=0.10)
        assert result.aborted and "posixGroups read vs 1000" in result.reason
        assert result.changed == 1  # the diff is still reported

    def test_group_drop_within_threshold_passes(self):
        current = {"alice": {"gidnumber": 10, "secondarygids": [20]}}
        result, _ = run(current, [sec("alice", [20])], include_primary=False,
                        group_count=950, last_group_count=1000, max_group_drop=0.10)
        assert not result.aborted

    def test_no_baseline_skips_group_guard(self):
        result, _ = run({"alice": {"gidnumber": 10}}, [sec("alice")], include_primary=False,
                        group_count=1, last_group_count=None, max_group_drop=0.10)
        assert not result.aborted

    def test_force_overrides_group_guard(self):
        current = {"alice": {"gidnumber": 10, "secondarygids": [20]}}
        result, updates = run(current, [sec("alice", [])], include_primary=False, force=True,
                              group_count=1, last_group_count=1000, max_group_drop=0.10)
        assert not result.aborted and "guard overridden by force" in result.reason
        assert updates == [("alice", 10, [])]


class TestModels:

    def test_user_gids_info_defaults(self):
        info = UserGidsInfo()
        assert info.uidnumber is None and info.primaryGid is None
        assert info.secondaryGidNumbers == [] and info.syncedAt is None

    def test_user_gids_info_synced(self):
        now = datetime.now(timezone.utc)
        info = UserGidsInfo(uidnumber=1, primaryGid=2, secondaryGidNumbers=[3], syncedAt=now)
        assert info.syncedAt == now

    def test_posix_fields_are_not_on_user_input(self):
        # gidnumber/secondarygids/ldapsyncedat are sync-owned and must not be settable via userUpsert/userUpdate
        names = {f.name for f in dataclasses.fields(User)}
        assert "uidnumber" in names
        assert not {"gidnumber", "secondarygids", "ldapsyncedat"} & names
