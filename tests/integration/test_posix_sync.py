"""
Integration tests for the LDAP posix sync mutations and myGids read path.
Requires: API + MongoDB running (see conftest.py) with
  POSIX_SYNC_USERNAMES=user-lookup-bot  POSIX_SYNC_MIN_ENTRIES<=2  ADMIN_USERNAMES includes "admin"
and a users document {username: "user-lookup-bot", isbot: true}.
No LDAP or user-lookup service is needed: the snapshot is hand-built.
"""

from collections.abc import AsyncGenerator

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


async def test_user_posix_refresh_requires_admin(client: CoactClient):
    with pytest.raises(GraphQLClientGraphQLMultiError, match="not an admin"):
        await client.user_posix_refresh(username="regular_user")


async def test_user_posix_refresh_unknown_user(admin_client: CoactClient):
    with pytest.raises(GraphQLClientGraphQLMultiError, match="does not exist in coact"):
        await admin_client.user_posix_refresh(username="no-such-user")
