"""
Test configuration and fixtures for CoAct API tests.
"""
import pytest
import os
from typing import AsyncGenerator
from coact.client import CoactClient

@pytest.fixture
async def integration_client() -> AsyncGenerator[CoactClient, None]:
    """GraphQL client for integration testing."""
    url = os.getenv("API_URL", "http://localhost:8000/graphql")
    headers = {"REMOTE_USER": "regular_user"}

    async with CoactClient(url=url, headers=headers) as client:
        yield client
