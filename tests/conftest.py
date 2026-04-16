"""
Test configuration and fixtures for CoAct API tests.
"""
import pytest_asyncio
from typing import AsyncGenerator
from coact.client import CoactClient

GRAPHQL_URL = "http://localhost:8000/graphql"
GRAPHQL_USER = "regular_user"
GRAPHQL_ADMIN_USER = "admin"

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[CoactClient, None]:
    async with CoactClient(
        url=GRAPHQL_URL,
        headers={"REMOTE_USER": GRAPHQL_USER},
    ) as c:
        yield c


@pytest_asyncio.fixture
async def admin_client() -> AsyncGenerator[CoactClient, None]:
    async with CoactClient(
        url=GRAPHQL_URL,
        headers={"REMOTE_USER": GRAPHQL_ADMIN_USER},
    ) as c:
        yield c
