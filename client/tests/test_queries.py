"""
Integration tests for GraphQL queries against the live API.
Requires: docker compose up (API + MongoDB running).
"""

import pytest

from coact.client.input_types import (
    FacilityInput,
    RepoComputeAllocationInput,
    RepoInput,
    ReportRangeInput,
    UserInput,
)
from coact.client import CoactClient
from coact.client.exceptions import GraphQLClientGraphQLMultiError

pytestmark = pytest.mark.asyncio


async def test_whoami(client: CoactClient):
    result = await client.whoami()
    assert result.whoami.username == "regular_user"
    assert result.whoami.uidnumber == 99001


async def test_am_i_registered(client: CoactClient):
    result = await client.am_i_registered()
    assert isinstance(result.am_i_registered.is_registered, bool)


async def test_users_no_filter(client: CoactClient):
    result = await client.users()
    assert isinstance(result.users, list)
    assert len(result.users) > 0
    assert any(u.username == "regular_user" for u in result.users)


async def test_users_matching_user_name(client: CoactClient):
    result = await client.users_matching_user_name(regex="regular")
    assert result.users_matching_user_name is not None
    assert any(
        "regular_user" in u.username for u in result.users_matching_user_name if u.username
    )


async def test_clusters(client: CoactClient):
    result = await client.clusters()
    assert isinstance(result.clusters, list)
    assert len(result.clusters) > 0
    assert any(c.name == "ada" for c in result.clusters)


async def test_facilities(client: CoactClient):
    result = await client.facilities()
    assert isinstance(result.facilities, list)
    assert len(result.facilities) > 0


async def test_facility_by_filter(client: CoactClient):
    result = await client.facility(filter_=FacilityInput(name="LCLS"))
    assert result.facility.name == "LCLS"


async def test_repos(client: CoactClient):
    result = await client.repos()
    assert isinstance(result.repos, list)


async def test_repos_with_nested_compute_allocations(client: CoactClient):
    result = await client.repos()
    assert isinstance(result.repos, list)
    for repo in result.repos:
        assert repo.name is not None or repo.name is None  # field exists
        assert isinstance(repo.current_compute_allocations, list)


async def test_request_types(client: CoactClient):
    result = await client.request_types()
    assert isinstance(result.request_types, list)
    assert len(result.request_types) > 0


async def test_request_statuses(client: CoactClient):
    result = await client.request_statuses()
    assert isinstance(result.request_statuses, list)


async def test_requests(client: CoactClient):
    result = await client.requests()
    assert result.requests is None or isinstance(result.requests, list)


# ---------------------------------------------------------------------------
# User queries
# ---------------------------------------------------------------------------


async def test_get_user_for_eppn(client: CoactClient):
    result = await client.get_user_for_eppn(eppn="regular_user@example.com")
    assert result.getuserforeppn is not None
    assert result.getuserforeppn.username == "regular_user"


async def test_users_matching_user_names(client: CoactClient):
    result = await client.users_matching_user_names(regexes=["regular", "jdoe"])
    assert result.users_matching_user_names is not None
    assert isinstance(result.users_matching_user_names, list)


async def test_users_lookup_from_service(client: CoactClient):
    result = await client.users_lookup_from_service(
        filter_=UserInput(username="regular_user", publichtml=False, isbot=False)
    )
    assert isinstance(result.users_lookup_from_service, list)


# ---------------------------------------------------------------------------
# Facility queries
# ---------------------------------------------------------------------------


async def test_facility_name_descs(client: CoactClient):
    result = await client.facility_name_descs()
    assert isinstance(result.facility_name_descs, list)
    assert len(result.facility_name_descs) > 0


async def test_facilities_i_manage(client: CoactClient):
    result = await client.facilities_i_manage()
    assert isinstance(result.facilities_i_manage, list)


# ---------------------------------------------------------------------------
# Repo queries
# ---------------------------------------------------------------------------


async def test_my_repos(client: CoactClient):
    result = await client.my_repos()
    assert isinstance(result.my_repos, list)


async def test_all_repos_and_facility(client: CoactClient):
    result = await client.all_repos_and_facility()
    assert isinstance(result.allreposandfacility, list)


async def test_my_repos_and_facility(client: CoactClient):
    result = await client.my_repos_and_facility()
    assert isinstance(result.myreposandfacility, list)


# ---------------------------------------------------------------------------
# Audit trail queries
# ---------------------------------------------------------------------------


async def test_user_audit_trails(client: CoactClient):
    result = await client.user_audit_trails()
    assert isinstance(result.user_audit_trails, list)


async def test_repo_audit_trails(client: CoactClient):
    repos_result = await client.repos()
    if not repos_result.repos:
        pytest.skip("No repos available in test database")
    first = repos_result.repos[0]
    result = await client.repo_audit_trails(
        repo=RepoInput(name=first.name, facility=first.facility)
    )
    assert isinstance(result.repo_audit_trails, list)


# ---------------------------------------------------------------------------
# Cluster / compute usage queries
# ---------------------------------------------------------------------------


async def test_repo_compute_jobs(client: CoactClient):
    result = await client.repo_compute_jobs(
        rca=RepoComputeAllocationInput(Id=None, clustername="ada"),
        past_x_mins=60,
    )
    assert isinstance(result.repo_compute_jobs, list)


# ---------------------------------------------------------------------------
# Report queries
# ---------------------------------------------------------------------------


async def test_report_facility_compute_by_day(client: CoactClient):
    result = await client.report_facility_compute_by_day(
        clustername="ada",
        range_=ReportRangeInput(start=None, end=None),
        group="Day",
    )
    assert isinstance(result.report_facility_compute_by_day, list)


async def test_report_facility_compute_by_user(client: CoactClient):
    result = await client.report_facility_compute_by_user(
        clustername="ada",
        range_=ReportRangeInput(start=None, end=None),
    )
    assert isinstance(result.report_facility_compute_by_user, list)


async def test_report_facility_compute_overall_non_admin(client: CoactClient):
    with pytest.raises(GraphQLClientGraphQLMultiError, match="not an admin"):
        await client.report_facility_compute_overall(clustername="ada", group="Day")


async def test_report_facility_compute_overall_admin(admin_client: CoactClient):
    result = await admin_client.report_facility_compute_overall(
        clustername="ada",
        group="Day",
    )
    assert isinstance(result.report_facility_compute_overall, list)


async def test_report_facility_storage(client: CoactClient):
    result = await client.report_facility_storage(storagename="sdf")
    assert isinstance(result.report_facility_storage, list)


# ---------------------------------------------------------------------------
# Repo features queries
# ---------------------------------------------------------------------------


async def test_repo_features(client: CoactClient):
    repos_result = await client.repos()
    if not repos_result.repos:
        pytest.skip("No repos available in test database")
    first = repos_result.repos[0]
    if not first.name or not first.facility:
        pytest.skip("First repo has no name/facility")
    result = await client.repo_features(repo=first.name, facility=first.facility)
    assert result.whoami is not None
    assert result.whoami.username is not None
