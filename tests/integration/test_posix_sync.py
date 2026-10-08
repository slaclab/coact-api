"""
Integration tests for the LDAP posix sync mutations and myGids read path.
Requires: API + MongoDB running (see conftest.py) with
  POSIX_SYNC_USERNAMES=user-lookup-bot  POSIX_SYNC_MIN_COVERAGE=0  ADMIN_USERNAMES includes "admin"
(the hand-built snapshot covers only a few of the test database's users, so the coverage guard is disabled)
and the seeded users in scripts/dev/00-test-users.mongodb: "user-lookup-bot" (a plain user, as in the real
deployments) and "test-bot" (isbot).
No LDAP is needed: the snapshot is hand-built. user-lookup (myGids fallback, userPosixInit) is served by
tests/stubs/user_lookup_stub.py via the API's USER_LOOKUP_URL; never point it at a real service.
"""

from collections.abc import AsyncGenerator
from datetime import datetime

import pytest
import pytest_asyncio

from coact.client import CoactClient
from coact.client.exceptions import GraphQLClientGraphQLMultiError
from coact.client.input_types import UserPosixInput

from tests.conftest import GRAPHQL_URL

SYNC_USER = "user-lookup-bot"

SNAPSHOT = [
    UserPosixInput(username="regular_user", uidnumber=99001, gidnumber=1001, secondarygids=[3049, 2113, 3049]),
    UserPosixInput(username="admin", uidnumber=99002, gidnumber=1002, secondarygids=[]),
    UserPosixInput(username="not-in-coact", uidnumber=5, gidnumber=5, secondarygids=[1]),
]


@pytest_asyncio.fixture
async def sync_client() -> AsyncGenerator[CoactClient, None]:
    async with CoactClient(url=GRAPHQL_URL, headers={"REMOTE_USER": SYNC_USER}) as c:
        yield c


async def test_regular_user_cannot_sync(client: CoactClient):
    with pytest.raises(GraphQLClientGraphQLMultiError, match="not a posix sync service account"):
        await client.users_posix_sync(entries=SNAPSHOT, dry_run=True)


async def test_admin_cannot_sync(admin_client: CoactClient):
    with pytest.raises(GraphQLClientGraphQLMultiError, match="not a posix sync service account"):
        await admin_client.users_posix_sync(entries=SNAPSHOT, dry_run=True)


POSIX_SYNC_USERNAMES = "query { posixSyncUsernames(includeUnsynced: true) }"
# force: with only two synced test users, changing one is 50% churn, above the default max churn guard
SECONDARY_SYNC = """mutation S($entries: [UserSecondaryGidsInput!]!, $groupCount: Int!, $dryRun: Boolean!) {
  usersSecondaryGidsSync(entries: $entries, groupCount: $groupCount, dryRun: $dryRun, force: true) { changed aborted reason unsynced }
}"""


async def test_regular_user_cannot_list_sync_usernames(client: CoactClient):
    with pytest.raises(GraphQLClientGraphQLMultiError, match="not a posix sync service account"):
        client.get_data(await client.execute(query=POSIX_SYNC_USERNAMES))


async def test_sync_usernames_are_non_bot_coact_users(sync_client: CoactClient):
    names = sync_client.get_data(await sync_client.execute(query=POSIX_SYNC_USERNAMES))["posixSyncUsernames"]
    assert {"regular_user", "admin"} <= set(names)
    assert "test-bot" not in names  # bots are never read from LDAP
    assert SYNC_USER in names  # the sync account is a plain user, not a bot
    assert names == sorted(names)


async def test_dry_run_reports_diff(sync_client: CoactClient):
    res = (await sync_client.users_posix_sync(entries=SNAPSHOT, dry_run=True)).users_posix_sync
    assert res.dry_run is True
    assert res.total == 3
    assert res.matched >= 2
    assert "not-in-coact" not in res.unknown_users  # snapshot-only entries are ignored, not reported
    status = (await sync_client.posix_sync_status()).posix_sync_status
    assert status is not None and status.dry_run is True


async def test_force_writes_and_is_idempotent(sync_client: CoactClient, client: CoactClient):
    # first real run for a fresh database changes every matched user and trips the churn guard
    res = (await sync_client.users_posix_sync(entries=SNAPSHOT, dry_run=False, force=True)).users_posix_sync
    assert res.aborted is False
    assert res.synced_at is not None

    gids = (await client.my_gids()).my_gids
    assert gids.uidnumber == 99001
    assert gids.primary_gid == 1001
    assert gids.secondary_gid_numbers == [2113, 3049]  # deduped and sorted
    assert gids.synced_at is not None

    again = (await sync_client.users_posix_sync(entries=SNAPSHOT, dry_run=False)).users_posix_sync
    assert again.changed == 0 and again.aborted is False

    status = (await sync_client.posix_sync_status()).posix_sync_status
    assert status.aborted is False and status.changed == 0 and status.lastsuccess is not None


async def test_secondary_sync_changes_only_secondaries(sync_client: CoactClient, client: CoactClient):
    # runs after test_force_writes_and_is_idempotent, so regular_user/admin are initialised
    before = (await client.my_gids()).my_gids
    entries = [{"username": "regular_user", "secondarygids": [2113, 3049, 4000]}, {"username": "admin", "secondarygids": []}]
    res = sync_client.get_data(await sync_client.execute(
        query=SECONDARY_SYNC, variables={"entries": entries, "groupCount": 3, "dryRun": False}))["usersSecondaryGidsSync"]
    assert res["aborted"] is False and res["changed"] == 1 and res["unsynced"] is not None
    after = (await client.my_gids()).my_gids
    assert after.secondary_gid_numbers == [2113, 3049, 4000]
    assert after.primary_gid == before.primary_gid and after.uidnumber == before.uidnumber
    status = (await sync_client.posix_sync_status()).posix_sync_status
    assert status.changed == 1
    # restore for the following tests
    entries[0]["secondarygids"] = [2113, 3049]
    sync_client.get_data(await sync_client.execute(
        query=SECONDARY_SYNC, variables={"entries": entries, "groupCount": 3, "dryRun": False}))


async def test_churn_guard_aborts_without_force(sync_client: CoactClient, client: CoactClient):
    before = (await client.my_gids()).my_gids
    changed = [UserPosixInput(username=e.username, uidnumber=e.uidnumber, gidnumber=(e.gidnumber or 0) + 500, secondarygids=e.secondarygids)
               for e in SNAPSHOT]
    res = (await sync_client.users_posix_sync(entries=changed, dry_run=False)).users_posix_sync
    assert res.aborted is True and "max churn" in (res.reason or "")
    after = (await client.my_gids()).my_gids
    assert after.primary_gid == before.primary_gid  # nothing written


async def test_uid_mismatch_is_reported_not_written(sync_client: CoactClient, client: CoactClient):
    entries = [UserPosixInput(username="regular_user", uidnumber=42, gidnumber=1001, secondarygids=[2113, 3049])] + SNAPSHOT[1:]
    res = (await sync_client.users_posix_sync(entries=entries, dry_run=False)).users_posix_sync
    assert any(m.startswith("regular_user: coact=99001 ldap=42") for m in res.uid_mismatches)
    gids = (await client.my_gids()).my_gids
    assert gids.uidnumber == 99001


async def test_user_posix_group_update_requires_admin(client: CoactClient):
    with pytest.raises(GraphQLClientGraphQLMultiError, match="not an admin"):
        await client.user_posix_group_update(username="regular_user", gidnumber=5000, present=True)


async def test_user_posix_group_update_unknown_user(admin_client: CoactClient):
    with pytest.raises(GraphQLClientGraphQLMultiError, match="does not exist in coact"):
        await admin_client.user_posix_group_update(username="no-such-user", gidnumber=5000, present=True)


async def test_user_posix_group_update_is_idempotent(admin_client: CoactClient, client: CoactClient):
    before = (await client.my_gids()).my_gids.secondary_gid_numbers
    assert 5000 not in before

    for _ in range(2):
        res = (await admin_client.user_posix_group_update(username="regular_user", gidnumber=5000, present=True)).user_posix_group_update
        assert res.secondary_gid_numbers == sorted(set(before) | {5000})
    assert (await client.my_gids()).my_gids.secondary_gid_numbers == sorted(set(before) | {5000})

    for _ in range(2):
        res = (await admin_client.user_posix_group_update(username="regular_user", gidnumber=5000, present=False)).user_posix_group_update
        assert res.secondary_gid_numbers == before
    assert (await client.my_gids()).my_gids.secondary_gid_numbers == before


# userPosixInit: coactd initialises a newly provisioned user's posix data from user-lookup.
# The generated client has no method for it yet (regenerating needs a running API), so use raw execute/get_data.
# The permission and unknown-user tests need nothing extra. The success test needs the API's USER_LOOKUP_URL to
# resolve "regular_user" with a primary gid (the stub does) and skips otherwise; it is last because it overwrites
# regular_user's gid data with whatever user-lookup returns.

USER_POSIX_INIT = """
mutation userPosixInit($username: String!) {
    userPosixInit(username: $username) { uidnumber primaryGid secondaryGidNumbers syncedAt }
}
"""


async def user_posix_init(c: CoactClient, username: str) -> dict:
    return c.get_data(await c.execute(query=USER_POSIX_INIT, variables={"username": username}))["userPosixInit"]


async def test_user_posix_init_requires_admin(client: CoactClient):
    with pytest.raises(GraphQLClientGraphQLMultiError, match="not an admin"):
        await user_posix_init(client, "regular_user")


async def test_user_posix_init_unknown_user(admin_client: CoactClient):
    # checked before user-lookup is queried, so this needs no user-lookup data
    with pytest.raises(GraphQLClientGraphQLMultiError, match="does not exist in coact"):
        await user_posix_init(admin_client, "no-such-user")


async def coact_uidnumber(c: CoactClient):
    return c.get_data(await c.execute(query="query { whoami { uidnumber } }"))["whoami"]["uidnumber"]


async def test_user_posix_init_initialises_and_is_idempotent(admin_client: CoactClient, client: CoactClient):
    uidnumber = await coact_uidnumber(client)
    try:
        first = await user_posix_init(admin_client, "regular_user")
    except GraphQLClientGraphQLMultiError as e:
        if "user-lookup" in str(e):
            pytest.skip(f"user-lookup cannot resolve regular_user on this stack: {e}")
        raise
    assert first["primaryGid"] is not None
    assert first["secondaryGidNumbers"] == sorted(set(first["secondaryGidNumbers"]))
    assert first["syncedAt"] is not None
    assert first["uidnumber"] == uidnumber  # uidnumber is owned by userUpsert, never written here
    assert await coact_uidnumber(client) == uidnumber

    gids = (await client.my_gids()).my_gids  # now served from the users collection
    assert gids.synced_at is not None
    assert gids.uidnumber == uidnumber
    assert gids.primary_gid == first["primaryGid"]
    assert gids.secondary_gid_numbers == first["secondaryGidNumbers"]

    again = await user_posix_init(admin_client, "regular_user")  # re-running just refreshes
    assert again["uidnumber"] == first["uidnumber"]
    assert again["primaryGid"] == first["primaryGid"]
    assert again["secondaryGidNumbers"] == first["secondaryGidNumbers"]
    assert datetime.fromisoformat(again["syncedAt"]) >= datetime.fromisoformat(first["syncedAt"])
