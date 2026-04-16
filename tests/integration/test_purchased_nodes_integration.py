"""
Integration tests for purchased nodes functionality - requires full stack.

Tests the GraphQL contract and database integration.
Requires: docker compose up (API + MongoDB running)
"""
from coact.client import CoactClient


class TestPurchasedNodesIntegration:
    """Integration tests for purchased nodes GraphQL contract."""

    async def test_purchased_nodes_graphql_contract(self, client: CoactClient):
        """Test that purchasedNodes field works in GraphQL query."""
        result = await client.facility_recent_compute_usage(past_minutes=5)

        # Contract verification: query succeeds and returns expected structure
        assert isinstance(result.facility_recent_compute_usage, list)

        # If data exists, verify purchasedNodes field is accessible
        if result.facility_recent_compute_usage:
            usage_record = result.facility_recent_compute_usage[0]
            assert hasattr(usage_record, 'purchased_nodes')

            # Basic type contract
            if usage_record.purchased_nodes is not None:
                assert isinstance(usage_record.purchased_nodes, int)
