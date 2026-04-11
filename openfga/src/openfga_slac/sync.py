import os
import json
import asyncio
import logging
from typing import TypeVar, Type, Any

from openfga_sdk.client import OpenFgaClient, ClientConfiguration
from openfga_sdk.client.models import ClientTuple, ClientWriteRequest
from openfga_sdk.models.create_store_request import CreateStoreRequest
from openfga_sdk.models.read_request_tuple_key import ReadRequestTupleKey
from openfga_sdk.models.write_authorization_model_request import (
    WriteAuthorizationModelRequest,
)

from coact.client.client import CoactClient
from coact.client.facilities import Facilities
from coact.client.repos import Repos

from .models import Facility, Repo, PosixGroup
from .gen.models import (
    ListStoresResponse,
    CreateStoreResponse,
    WriteAuthorizationModelResponse,
    ReadResponse,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BATCH_SIZE = 100
SYNC_INTERVAL = 60
READY_POLL_INTERVAL = 2
SAMPLE_LOG_LIMIT = 5

# openfga SDK doesn't have any real typing information...
# we then validate it with the pydantic models we generated from the OpenAPI spec to ensure we have the right
# data and to get nice attribute access instead of dicts

T = TypeVar("T")


def parse_sdk_response(model: Type[T], response: Any) -> T:
    """Converts an OpenFGA SDK response to a Pydantic model."""
    if hasattr(response, "to_dict"):
        return model(**response.to_dict())
    return model(**response)


def _is_posix_tuple(t: tuple[str, str, str]) -> bool:
    user, relation, obj = t
    return obj.startswith("posix_group:") or user.startswith("posix_group:")


def _log_sample_tuples(label: str, tuples: set[tuple[str, str, str]], limit: int = SAMPLE_LOG_LIMIT) -> None:
    if not tuples:
        return
    sample = sorted(tuples)[:limit]
    for user, relation, obj in sample:
        logger.info("%s tuple: user=%s relation=%s object=%s", label, user, relation, obj)


async def get_current_tuples(fga_client: OpenFgaClient) -> set[tuple[str, str, str]]:
    all_tuples = set()
    continuation_token = None
    while True:
        options = {}
        if continuation_token:
            options["continuation_token"] = continuation_token

        # Passing an empty ReadRequestTupleKey reads all tuples
        resp = await fga_client.read(body=ReadRequestTupleKey(), options=options)
        parsed_resp = parse_sdk_response(ReadResponse, resp)

        for t in parsed_resp.tuples:
            all_tuples.add((t.key.user, t.key.relation, t.key.object))

        continuation_token = parsed_resp.continuation_token
        if not continuation_token:
            break
    return all_tuples


async def _batch_write(
    fga_client: OpenFgaClient,
    tuples: list[tuple[str, str, str]],
    *,
    writes: bool,
) -> None:
    items = [ClientTuple(user=u, relation=r, object=o) for u, r, o in tuples]
    for i in range(0, len(items), BATCH_SIZE):
        chunk = items[i : i + BATCH_SIZE]
        if writes:
            await fga_client.write(ClientWriteRequest(writes=chunk))
        else:
            await fga_client.write(ClientWriteRequest(deletes=chunk))


async def init_openfga(fga_client: OpenFgaClient, schema_path: str):
    logger.info("Initializing OpenFGA store and schema...")
    list_stores = parse_sdk_response(ListStoresResponse, await fga_client.list_stores())
    store_id = None
    for store in list_stores.stores:
        if store.name == "coact":
            store_id = store.id
            break

    if not store_id:
        create_store_resp = parse_sdk_response(
            CreateStoreResponse,
            await fga_client.create_store(CreateStoreRequest(name="coact")),
        )

        store_id = create_store_resp.id
        logger.info(f"Created new OpenFGA store 'coact' with ID: {store_id}")
    else:
        logger.info(f"Found existing OpenFGA store 'coact' with ID: {store_id}")

    fga_client.set_store_id(store_id)

    with open(schema_path) as f:
        model = WriteAuthorizationModelRequest(**json.load(f))

    resp = parse_sdk_response(
        WriteAuthorizationModelResponse,
        await fga_client.write_authorization_model(model),
    )
    fga_client.set_authorization_model_id(resp.authorization_model_id)
    logger.info(f"Set authorization model ID: {resp.authorization_model_id}")


async def run_sync_cycle(fga_client: OpenFgaClient, coact_client: CoactClient):
    logger.info("Starting sync cycle...")
    try:
        # 1. Fetch Facilities and Repos
        facs: Facilities = await coact_client.facilities()
        reps: Repos = await coact_client.repos()
        logger.info(
            f"Fetched {len(facs.facilities or [])} facilities and {len(reps.repos or [])} repos from Coact API."
        )

        desired_tuples = set()
        repos_with_access_groups = 0
        posix_groups_seen = 0
        posix_groups_missing_name = 0
        posix_groups_invalid = 0
        posix_member_edges_seen = 0
        posix_groups_emitted = 0
        posix_raw_samples: list[tuple[str, str, str, int]] = []
        repos_with_group_field = 0
        repos_with_group_field_nonempty = 0
        group_field_samples: list[tuple[str, str, str]] = []

        if facs.facilities:
            for f_data in facs.facilities:
                desired_tuples.update(Facility.from_coact(f_data).get_tuples())

        if reps.repos:
            for r_data in reps.repos:
                group_name_from_repo = (r_data.group or "").strip() if r_data.group is not None else ""
                if r_data.group is not None:
                    repos_with_group_field += 1
                if group_name_from_repo:
                    repos_with_group_field_nonempty += 1
                    if len(group_field_samples) < SAMPLE_LOG_LIMIT and r_data.facility and r_data.name:
                        group_field_samples.append((r_data.facility, r_data.name, group_name_from_repo))
                    if r_data.facility and r_data.name:
                        pg = PosixGroup(
                            facility=r_data.facility,
                            repo_name=r_data.name,
                            group_name=group_name_from_repo,
                            members=[],
                        )
                        desired_tuples.update(pg.get_tuples())
                desired_tuples.update(Repo.from_coact(r_data).get_tuples())
                if r_data.facility and r_data.name and r_data.access_group_objs:
                    repos_with_access_groups += 1
                    for grp in r_data.access_group_objs:
                        posix_groups_seen += 1
                        if not grp.name:
                            posix_groups_missing_name += 1
                            continue

                        members = grp.members or []
                        posix_member_edges_seen += len(members)
                        if len(posix_raw_samples) < SAMPLE_LOG_LIMIT:
                            posix_raw_samples.append(
                                (r_data.facility, r_data.name, grp.name, len(members))
                            )

                        pg = PosixGroup(
                            facility=r_data.facility,
                            repo_name=r_data.name,
                            group_name=grp.name,
                            members=members,
                        )
                        pg_tuples = set(pg.get_tuples())
                        if not pg_tuples:
                            posix_groups_invalid += 1
                            continue
                        posix_groups_emitted += 1
                        desired_tuples.update(pg_tuples)

        # 2. Get current state from OpenFGA
        current_tuples = await get_current_tuples(fga_client)

        # 3. Calculate diff
        to_add = desired_tuples - current_tuples
        to_remove = current_tuples - desired_tuples

        desired_posix = {t for t in desired_tuples if _is_posix_tuple(t)}
        current_posix = {t for t in current_tuples if _is_posix_tuple(t)}
        to_add_posix = {t for t in to_add if _is_posix_tuple(t)}
        to_remove_posix = {t for t in to_remove if _is_posix_tuple(t)}

        logger.info(
            f"Syncing: {len(to_add)} tuples to add, {len(to_remove)} tuples to remove."
        )
        logger.info(
            "POSIX source: repos_with_groups=%s groups_seen=%s groups_missing_name=%s groups_invalid=%s groups_emitted=%s members_seen=%s",
            repos_with_access_groups,
            posix_groups_seen,
            posix_groups_missing_name,
            posix_groups_invalid,
            posix_groups_emitted,
            posix_member_edges_seen,
        )
        logger.info(
            "POSIX source: repos_with_group_field=%s repos_with_group_field_nonempty=%s",
            repos_with_group_field,
            repos_with_group_field_nonempty,
        )
        for facility, repo, group, member_count in posix_raw_samples:
            logger.info(
                "POSIX source sample: facility=%s repo=%s group=%s members=%s",
                facility,
                repo,
                group,
                member_count,
            )
        for facility, repo, group in group_field_samples:
            logger.info(
                "POSIX repo.group sample: facility=%s repo=%s group=%s",
                facility,
                repo,
                group,
            )
        logger.info(
            "POSIX tuples: desired=%s current=%s to_add=%s to_remove=%s",
            len(desired_posix),
            len(current_posix),
            len(to_add_posix),
            len(to_remove_posix),
        )
        _log_sample_tuples("POSIX to_add", to_add_posix)

        # 4. Perform updates
        if to_add:
            await _batch_write(fga_client, list(to_add), writes=True)
        if to_remove:
            await _batch_write(fga_client, list(to_remove), writes=False)

        logger.info("Sync cycle complete.")

    except Exception as e:
        logger.error(f"Error during sync cycle: {e}")


async def sync_loop():
    fga_url = os.environ.get("OPENFGA_API_URL", "http://openfga:8080")
    coact_url = os.environ.get("COACT_API_URL", "http://coact-api:8000/graphql")
    schema_path = os.environ.get("OPENFGA_SCHEMA_PATH", "schema/schema.json")

    config = ClientConfiguration(api_url=fga_url)

    async with OpenFgaClient(config) as fga_client:
        # Wait for OpenFGA to be ready
        while True:
            try:
                await fga_client.list_stores()
                break
            except Exception:
                logger.info("Waiting for OpenFGA...")
                await asyncio.sleep(READY_POLL_INTERVAL)

        await init_openfga(fga_client, schema_path)

        # The Coact API uses this header to identify the user.
        headers = {"REMOTE_USER": "ytl"}
        async with CoactClient(url=coact_url, headers=headers) as coact_client:
            while True:
                await run_sync_cycle(fga_client, coact_client)
                await asyncio.sleep(SYNC_INTERVAL)
