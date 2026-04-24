"""
Integration test to verify CLI can get purchased nodes data from Facility.computepurchases.

Since the CLI now queries purchased nodes via Facility.computepurchases instead of
facilityRecentComputeUsage, this test ensures that integration works end-to-end.
Requires: docker compose up (API + MongoDB running)
"""
from coact.client import CoactClient


async def test_facility_computepurchases_provides_cli_data(client: CoactClient):
    """Test that Facility.computepurchases provides the purchased nodes data CLI needs."""
    response = await client.execute(
        query="""
        query {
            facilities {
                name
                computepurchases {
                    clustername
                    purchased
                }
            }
        }
        """
    )
    data = client.get_data(response)
    facilities = data["facilities"]

    assert isinstance(facilities, list)

    for facility in facilities:
        assert "name" in facility

        if facility["computepurchases"] is not None:
            assert isinstance(facility["computepurchases"], list)

            for purchase in facility["computepurchases"]:
                # Verify CLI gets the fields it needs for purchased nodes
                assert "clustername" in purchase
                assert "purchased" in purchase
                assert isinstance(purchase["clustername"], str)

                # The "purchased" field is what CLI uses for purchased nodes count
                if purchase["purchased"] is not None:
                    assert isinstance(purchase["purchased"], (int, float))
