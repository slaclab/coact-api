"""
Integration tests for purchased nodes functionality - requires full stack.

Tests that facilityRecentComputeUsage returns the purchasedNodes field.
Requires: docker compose up (API + MongoDB running)
"""
from coact.client import CoactClient


async def test_facility_recent_compute_usage_purchased_nodes(client: CoactClient):
    """Test that facilityRecentComputeUsage returns purchasedNodes as an integer field."""
    response = await client.execute(
        query="""
        query {
            facilityRecentComputeUsage(pastMinutes: 60) {
                facility
                clustername
                resourceHours
                percentUsed
                purchasedNodes
            }
        }
        """
    )
    data = client.get_data(response)
    results = data["facilityRecentComputeUsage"]

    assert isinstance(results, list)

    for record in results:
        assert "purchasedNodes" in record
        if record["purchasedNodes"] is not None:
            assert isinstance(record["purchasedNodes"], int)
